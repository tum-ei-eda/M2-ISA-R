"""Local initializer scope follows declaration order and outer bindings."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo

LINKING = 'org.eclipse.xtext.diagnostics.Diagnostic.Linking'
ASSIGNMENT = 'com.minres.coredsl.InvalidAssignmentType'
CASES = [
    ('int x = y; int y = 1;', LINKING, "Couldn't resolve reference to NamedEntity 'y'"),
    ('int x = x;', LINKING, "Couldn't resolve reference to NamedEntity 'x'"),
    ('unsigned<8> x = 1; { unsigned<2> x = x; }', ASSIGNMENT, 'Cannot implicitly convert unsigned<8> to unsigned<2>'),
    ('unsigned<8> x = 1; { unsigned<2> x = 1; x = 4; }', ASSIGNMENT, 'Cannot implicitly convert unsigned<3> to unsigned<2>'),
    ('int x = 1; int x = 2;', None, ''),
    ('int x = 1, y = x;', None, ''),
    ('unsigned<8> x = 1; { unsigned<2> x = 1; } x = 255;', None, ''),
]

FUNCTION_CASES = [
    ('int target=1; target();', 'com.minres.coredsl.InvalidFunction', 'Expected a function name'),
    ('int target=1; int x=target();', 'com.minres.coredsl.InvalidFunction', 'Expected a function name'),
    ('int x=target;', 'com.minres.coredsl.ReferenceToFunction', 'Function used like a variable'),
    ('int target=target();', None, ''),
    ('{ int target=1; } target();', None, ''),
    ('target(); int target=1;', None, ''),
]


def source(body):
    return 'Core C { functions { void f() { ' + body + ' } } }'


def function_source(body):
    return 'Core C { functions { int target() { return 1; } void f() { ' + body + ' } } }'


class LocalScopingNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_declaration_scope(self):
        for body, issue, message in CASES:
            with self.subTest(body=body):
                if issue is None:
                    self.validate(source(body))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        self.validate(source(body))
                    self.assertEqual(exc.exception.issue_code, issue)
                    self.assertIn(message, str(exc.exception))

    def test_function_shadowing(self):
        for body, issue, message in FUNCTION_CASES:
            with self.subTest(body=body):
                if issue is None:
                    self.validate(function_source(body))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        self.validate(function_source(body))
                    self.assertEqual(exc.exception.issue_code, issue)
                    self.assertIn(message, str(exc.exception))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class LocalScopingOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_function_shadowing(self):
        for body, issue, message in FUNCTION_CASES:
            with self.subTest(body=body):
                output, tree = self.probe(function_source(body))
                if issue is None:
                    self.assertNotIn('ERROR:', output, output)
                    validate_source(tree, WarningsInfo())
                else:
                    self.assertIn(message, output, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_source(tree, WarningsInfo())
                    self.assertEqual(exc.exception.issue_code, issue)

    def test_declaration_scope(self):
        for body, issue, message in CASES:
            with self.subTest(body=body):
                output, tree = self.probe(source(body))
                if issue is None:
                    self.assertNotIn('ERROR:', output, output)
                    validate_source(tree, WarningsInfo())
                else:
                    self.assertIn(message, output, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_source(tree, WarningsInfo())
                    self.assertEqual(exc.exception.issue_code, issue)
