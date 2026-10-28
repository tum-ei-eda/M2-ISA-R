"""Unresolved ISA dependencies use the release linking diagnostic."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo

CASES = [
    'Core C provides Missing {}',
    'InstructionSet A extends Missing {}',
    'InstructionSet A combines Missing;',
    'Core A {} Core C provides A {}',
]
ISSUE = 'org.eclipse.xtext.diagnostics.Diagnostic.Linking'


class DependencyNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_unresolved_dependencies(self):
        for source in CASES:
            with self.subTest(source=source):
                with self.assertRaises(M2ValidationError) as exc:
                    self.validate(source)
                self.assertEqual(exc.exception.issue_code, ISSUE)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class DependencyOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_unresolved_dependencies(self):
        for source in CASES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertIn("Couldn't resolve reference to InstructionSet", output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, ISSUE)
