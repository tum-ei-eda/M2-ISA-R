"""Enum declaration syntax and list-initializer parity."""
import os
import tempfile
import unittest
from pathlib import Path

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.source_semantics import SemanticValidator
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo

ERRORS = [
    'Core C { architectural_state { enum E { A = {1} } } }',
    'Core C { architectural_state { enum E { A = {1,2}, B } } }',
]
POSITIVES = [
    'Core C { architectural_state { enum E { A, B = 3, C } } }',
    'Core C { architectural_state { enum E { A = -1, B, C = 7, } } }',
]
CONSTANT_ERRORS = [
    ('enum E { A = 8, B, C } unsigned<4> W = C; register unsigned<W> R;', None),
    ('enum E { A = -2, B } register unsigned<B> R;', 'InvalidIntegerTypeSize'),
    ('enum E { A = 4, B, C } unsigned<2> W = C;', 'InvalidAssignmentType'),
    ('register int R; enum E { A = R }', 'InvalidConstantExpressionIdentifier'),
    ('enum E { A = 1 / 0 }', 'DivisionByZero'),
]
TYPE_CASES = [
    ('enum E { A, B = 7 } register enum E R;', 'void f() { unsigned<3> x = R; enum E y = 7; }', None, ''),
    ('enum E { A, B = 7 } register enum E R;', 'void f() { unsigned<2> x = R; }', 'InvalidAssignmentType', 'Cannot implicitly convert'),
    ('enum E { A, B = 7 }', 'void f() { unsigned<2> x = A; }', None, ''),
    ('enum E { A } register enum E R;', 'void f() { int x = R + 1; }', 'InvalidOperationType', 'Addition is only valid'),
    ('enum E { A } register enum E R;', 'void f() { if (R) {} }', 'NonScalarCondition', 'must be a scalar type'),
    ('enum E { A } register enum E R;', 'void f() { int x = (int)R; }', 'InvalidCast', 'Cannot cast'),
    ('enum E { A } enum F { B } register enum E R; register enum F S;', 'void f() { R = S; }', None, ''),
    ('enum E { A } enum F { B = 7 } register enum E R; register enum F S;', 'void f() { R = S; }', 'InvalidAssignmentType', 'Cannot implicitly convert'),
    ('enum E { A = -1, B = 7 }', 'void f() { unsigned<4> x = bitsizeof(enum E); }', None, ''),
]


class EnumDeclarationNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_list_initializers(self):
        for source in ERRORS:
            with self.subTest(source=source):
                self.error(source, 'InvalidListInitializer')

    def test_standalone_declarations(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                self.validate(source)

    def test_enum_constant_evaluation(self):
        for body, issue in CONSTANT_ERRORS:
            source = 'Core C { architectural_state { ' + body + ' } }'
            with self.subTest(source=source):
                if issue is None:
                    self.validate(source)
                else:
                    self.error(source, issue)

    def test_enum_types(self):
        for state, functions, issue, _ in TYPE_CASES:
            source = 'Core C { architectural_state { ' + state + ' } functions { ' + functions + ' } }'
            with self.subTest(source=source):
                if issue is None:
                    self.validate(source)
                else:
                    self.error(source, issue)

    def test_common_base_type_and_identity(self):
        source = 'Core C { architectural_state { enum E { A = -1, B = 7 } enum F { D = 7 } register enum E R; } }'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'independent.core_desc'
            path.write_text(source)
            tree = make_parser(path).description_content()
            validator = SemanticValidator(tree, WarningsInfo())
            validator.visit(tree)
            first = validator.symbol_type(validator.lookup('A'))
            self.assertEqual(first.element.width, 4)
            self.assertTrue(first.element.signed)
            self.assertEqual(first, validator.symbol_type(validator.lookup('B')))
            self.assertEqual(first, validator.symbol_type(validator.lookup('R')))
            self.assertNotEqual(first, validator.symbol_type(validator.lookup('D')))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class EnumDeclarationOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_enum_types(self):
        for state, functions, issue, message in TYPE_CASES:
            source = 'Core C { architectural_state { ' + state + ' } functions { ' + functions + ' } }'
            with self.subTest(source=source):
                output, tree = self.probe(source)
                if issue is None:
                    self.assertNotIn('ERROR:', output, output)
                    validate_source(tree, WarningsInfo())
                else:
                    self.assertIn('ERROR:', output, output)
                    self.assertIn(message, output, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_source(tree, WarningsInfo())
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)

    def test_enum_constant_evaluation(self):
        for body, issue in CONSTANT_ERRORS:
            source = 'Core C { architectural_state { ' + body + ' } }'
            with self.subTest(source=source):
                output, tree = self.probe(source)
                if issue is None:
                    self.assertNotIn('ERROR:', output, output)
                    validate_source(tree, WarningsInfo())
                else:
                    self.assertIn('ERROR:', output, output)
                    message = {
                        'InvalidIntegerTypeSize': 'greater than 0',
                        'InvalidAssignmentType': 'Cannot implicitly convert',
                        'InvalidConstantExpressionIdentifier': 'ISA parameters or enum constants',
                        'DivisionByZero': 'Division by zero',
                    }[issue]
                    self.assertIn(message, output, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_source(tree, WarningsInfo())
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)

    def test_list_initializers(self):
        for source in ERRORS:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertIn('Enum members must not use list initializers', output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.InvalidListInitializer')

    def test_standalone_declarations(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertNotIn('ERROR:', output, output)
                validate_source(tree, WarningsInfo())
