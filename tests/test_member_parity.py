"""Member syntax and the release's linking-before-analysis behavior."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo

CASES = [
    'Core C { functions { void f() { int x; int y = x.foo; } } }',
    'Core C { functions { void f() { int x[2]; int y = x.foo; } } }',
    'Core C { functions { void f() { int x[2]; int y = x[0].foo; } } }',
    'Core C { architectural_state { extern int M[4]; } functions { void f() { int y = M.foo; } } }',
]
ISSUE = 'org.eclipse.xtext.diagnostics.Diagnostic.Linking'


class MemberNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_invalid_members(self):
        for source in CASES:
            with self.subTest(source=source), self.assertRaises(M2ValidationError) as exc:
                self.validate(source)
            self.assertEqual(exc.exception.issue_code, ISSUE)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MemberOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_invalid_members(self):
        for source in CASES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertIn("Couldn't resolve reference to Declarator 'foo'", output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, ISSUE)
