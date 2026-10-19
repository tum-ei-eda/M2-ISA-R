"""List shape errors retain independent element and later body diagnostics."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

C = 'InvalidArgumentCount'
A = 'InvalidAssignmentType'
U = 'UnsupportedLanguageFeature'
CASES = [
    ('int a[1]={g(0),g(1)}; g(2);', [A, C, A, C, A, C]),
    ('unsigned<1> a[2]={2,3};', [A, A]),
    ('int a[3]={{1},g(0),{2}};', [U, C, A, U]),
    ('int a={g(0)}; g(1);', ['InvalidListInitializer', C]),
    ('InstructionSet C { architectural_state { int N; } functions { void g() {} '
     'void f() { int a[N]={g(0),g(1)}; } } }', [C, A, C, A]),
]
VALID = ('unsigned<1> a[2]={0,1};', 'int a[2]={1,2}; a[0]=a[1];')

def source(body):
    if body.startswith('InstructionSet '):
        return body
    return 'Core C { functions { void g() {} void f() { ' + body + ' } } }'

class SourceListCollectionNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_list_diagnostics(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(body))
                self.assertEqual(codes(caught.exception), expected)

    def test_valid_lists_and_binding(self):
        for body in VALID:
            with self.subTest(body=body):
                self.validate(source(body))

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceListCollectionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_list_diagnostics(self):
        for body, expected in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                self.assertEqual(output.count('ERROR:Incorrect argument count.'), expected.count(C), output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert') +
                                 output.count('ERROR:List initializer size does not match LHS size'),
                                 expected.count(A), output)
                self.assertEqual(output.count('ERROR:Nested list initializers are unsupported'), expected.count(U), output)
                self.assertEqual(output.count('ERROR:Cannot use list initializer'),
                                 expected.count('InvalidListInitializer'), output)
                self.assertEqual(output.count('ERROR:'), len(expected), output)

    def test_release_valid_lists(self):
        for body in VALID:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                self.assertNotIn('ERROR:', output)
