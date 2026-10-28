"""Prepared regression fixture: first duplicate member controls nested lookup."""
import os
import unittest
import test_source_validator as helpers
import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError

def source(kind, field):
    return ('Core C {architectural_state {struct T {int x;} struct U {int y;} '
            + kind + ' S {struct T a; struct U a;} register ' + kind + ' S R;} '
            'functions {void f(){int z=R.a.' + field + ';}}}')

class DuplicateMemberNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    def test_first_member_is_visible(self):
        for kind in ('struct', 'union'):
            with self.subTest(kind=kind):
                self.validate(source(kind, 'x'))
    def test_later_duplicate_does_not_supply_members(self):
        for kind in ('struct', 'union'):
            with self.subTest(kind=kind):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(kind, 'y'))
                self.assertEqual(caught.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking')
                self.assertIn("Declarator 'y'", str(caught.exception))
                self.assertEqual(caught.exception.related_diagnostics, [])

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR')
class DuplicateMemberOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe
    def test_release_first_member_is_visible(self):
        for kind in ('struct', 'union'):
            with self.subTest(kind=kind):
                output, _ = self.probe(source(kind, 'x'))
                self.assertNotIn('ERROR:', output)
    def test_release_later_duplicate_is_hidden(self):
        for kind in ('struct', 'union'):
            with self.subTest(kind=kind):
                output, _ = self.probe(source(kind, 'y'))
                self.assertEqual(output.count('ERROR:'), 1, output)
                self.assertIn("Couldn't resolve reference to Declarator 'y'", output)

