"""Named type lookup failures keep Xtext linking diagnostic identity."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo

CASES = [
    ('enum', "Core C { architectural_state { register enum Missing R; } }"),
    ('struct', "Core C { architectural_state { register struct Missing R; } }"),
    ('union', "Core C { architectural_state { register union Missing R; } }"),
    ('enum', "Core C { architectural_state { struct Missing { int x; } register enum Missing R; } }"),
    ('struct', "Core C { architectural_state { union Missing { int x; } register struct Missing R; } }"),
    ('struct', "Core C { functions { void f() { struct Missing x; } } }"),
    ('union', "Core C { architectural_state { struct S { union Missing x; } } }"),
]


class NamedTypeLinkingNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_linking_failures(self):
        for kind, source in CASES:
            with self.subTest(source=source), self.assertRaises(M2ValidationError) as exc:
                self.validate(source)
            self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking')
            self.assertIn(kind.capitalize() + "TypeDeclaration 'Missing'", str(exc.exception))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class NamedTypeLinkingOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_linking_failures(self):
        for kind, source in CASES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertIn("Couldn't resolve reference to " + kind.capitalize() + "TypeDeclaration 'Missing'.", output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking')
