"""Independent source definitions retain diagnostics and restore contexts."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

C = 'InvalidArgumentCount'
O = 'ReturnStatementOutsideFunction'
FUNCTIONS = 'functions { void g() {} void f() { g(0); } void h() { g(1); } }'
INSTRUCTIONS = "instructions { I { encoding: 8'h00; behavior: { g(0); } } J { encoding: 8'h01; behavior: { g(1); } } }"
ALWAYS = 'always { A { g(0); } B { g(1); } }'
CASES = [
    ('Core C { ' + FUNCTIONS + ' }', [C, C]),
    ('Core C { functions { void g() {} } ' + INSTRUCTIONS + ' }', [C, C]),
    ('Core C { functions { void g() {} } ' + ALWAYS + ' }', [C, C]),
    ('Core C { ' + FUNCTIONS + INSTRUCTIONS + ALWAYS + ' }', [C] * 6),
    ('Core C { ' + FUNCTIONS + ' } Core D { ' + FUNCTIONS + ' }', [C] * 4),
    ('Core C { functions { void g() {} void f() { int x=1; g(0); } '
     'void h() { int x[2]; x[0]=1; g(1); } } }', [C, C]),
    ('Core C { functions { void g() {} void f(unsigned<(g())> x) {} } '
     "instructions { I { encoding: 8'h00; behavior: { return g(0); } } } }",
     ['InvalidConstantExpressionNode', C, O]),
    ('Core C { always { A { return g(0); } } '
     'functions { void g() {} void f() { return g(1); } } '
     "instructions { I { encoding: 8'h00; behavior: { g(2); } } } }",
     [C, 'ReturnWithValueInVoidFunction', C, C, O]),
    ('Core C { functions { void g() {} void f() { g(0); } } } '
     'Core D { architectural_state { int N; } }', [C, 'UnassignedIsaParameter']),
    ('Core D { architectural_state { int N; } } '
     'Core C { functions { void g() {} void f() { g(0); } } }', ['UnassignedIsaParameter', C]),
    ('Core D { architectural_state { int N; } } '
     'Core E { architectural_state { int N; } }', ['UnassignedIsaParameter'] * 2),

    ('Core C { architectural_state { int N; } '
     'functions { void g() {} void f() { g(0); } } }', ['UnassignedIsaParameter', C]),
    ('Core C { architectural_state { int N; } functions { void g() {} } '
     "instructions { I { encoding: 8'h00; behavior: { g(0); } } } "
     'always { A { g(1); } } }', ['UnassignedIsaParameter', C, C]),

    ('Core C { architectural_state { unsigned<1> N=2; unsigned<1> M=3; } '
     'functions { void g() {} void f() { g(0); } } }', ['InvalidAssignmentType'] * 2 + [C]),
    ('Core C { architectural_state { register unsigned<1> R=2; register unsigned<1> S=3; } '
     'functions { void g() {} void f() { g(0); } } }', ['InvalidAssignmentType'] * 2 + [C]),

    ('Core C { architectural_state { int N=1; int &A=N; int &B=N; } '
     'functions { void g() {} void f() { g(0); } } }', ['InvalidAliasSource'] * 2 + [C]),

    ('Core C { functions { void g() {} int f() { g(0); } void h() { g(1); } } }',
     [C, 'MissingReturnStatement', C]),
    ('Core C { functions { void g() {} int f() { if (1) { g(0); return 1; } } } }',
     [C, 'MissingReturnStatement']),

    ('Core C { functions { void g() {} void f() { const const const unsigned<1> x=2; g(0); } } }',
     ['DuplicateQualifier'] * 2 + ['InvalidAssignmentType', C]),
    ('Core C { functions { void g() {} void f() { register extern unsigned<1> x=2; g(0); } } }',
     ['MultipleStorageClassSpecifiers', 'InvalidAssignmentType', 'StorageClassSpecifierOnLocalVariable', C]),

    ('Core C { functions { void g() {} void f() { void x=g(0); g(1); } } }',
     ['VoidDeclaration', C, C]),
    ('Core C { functions { void g() {} void f() { const int x, y; g(1); } } }',
     ['UninitializedConstant'] * 2 + [C]),
    ('Core C { functions { void g() {} void f() { const const void x; g(1); } } }',
     ['VoidDeclaration', 'DuplicateQualifier', 'UninitializedConstant', C]),

    ('Core C { functions { void g() {} void f() { int &x; g(0); } } }',
     ['AliasLocalVariable', 'UninitializedAlias', C]),
    ('Core C { functions { void g() {} void f() { const int &x; g(0); } } }',
     ['UninitializedConstant', 'AliasLocalVariable', 'UninitializedAlias', C]),
    ('Core C { functions { void g() {} void f() { int &x={1}; g(0); } } }',
     ['AliasLocalVariable', 'InvalidListInitializer', C]),
    ('Core C { functions { void g() {} void f() { int x; int &y=x; g(0); } } }',
     ['AliasLocalVariable', 'InvalidAliasSource', C]),

]


class SourceDefinitionCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_independent_definition_diagnostic_order(self):
        for text, expected in CASES:
            with self.subTest(source=text):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(text)
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_siblings_and_roots(self):
        self.validate(CASES[3][0].replace('g(0)', 'g()').replace('g(1)', 'g()'))
        self.validate(CASES[4][0].replace('g(0)', 'g()').replace('g(1)', 'g()'))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceDefinitionCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_independent_definition_counts(self):
        for text, expected in CASES:
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertEqual(output.count('ERROR:Incorrect argument count.'), expected.count(C), output)
                self.assertEqual(output.count('ERROR:Return statement is only valid in a function'), expected.count(O), output)
                self.assertEqual(output.count('ERROR:Void functions may not return a value'),
                                 expected.count('ReturnWithValueInVoidFunction'), output)
                self.assertEqual(output.count('ERROR:FunctionCallExpression is not allowed in constant expression'),
                                 expected.count('InvalidConstantExpressionNode'), output)
                self.assertEqual(output.count('ERROR:The following ISA parameters are never assigned:'),
                                 expected.count('UnassignedIsaParameter'), output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert'),
                                 expected.count('InvalidAssignmentType'), output)
                self.assertEqual(output.count('ERROR:Cannot define an alias to'),
                                 expected.count('InvalidAliasSource'), output)
                self.assertEqual(output.count('ERROR:Not all execution paths return a value'),
                                 expected.count('MissingReturnStatement'), output)
                for issue, message in (('DuplicateQualifier', 'Duplicate qualifier const'),
                                       ('MultipleStorageClassSpecifiers', 'A declaration may not specify more than one storage class'),
                                       ('StorageClassSpecifierOnLocalVariable', 'Storage class specifiers are only allowed on ISA level declarations')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(issue), output)
                for issue, message in (('VoidDeclaration', 'Declarations may not use type void'),
                                       ('UninitializedConstant', 'An identifier declared as const must be initialized')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(issue), output)
                for issue, message in (('AliasLocalVariable', 'A local variable may not be declared as alias'),
                                       ('UninitializedAlias', 'An identifier declared as alias must be initialized'),
                                       ('InvalidListInitializer', 'An identifier declared as alias must not use a list initializer')):
                    self.assertEqual(output.count('ERROR:' + message), expected.count(issue), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)
                if 'UnassignedIsaParameter' in expected and C in expected:
                    messages = {'UnassignedIsaParameter': 'ERROR:The following ISA parameters',
                                C: 'ERROR:Incorrect argument count.'}
                    self.assertLess(output.index(messages[expected[0]]),
                                    output.index(messages[expected[1]]), output)


    def test_release_valid_siblings_and_roots(self):
        for text in (CASES[3][0], CASES[4][0]):
            with self.subTest(source=text):
                output, _ = self.probe(text.replace('g(0)', 'g()').replace('g(1)', 'g()'))
                self.assertEqual(output.count('ERROR:'), 0, output)
