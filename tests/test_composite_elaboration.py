"""Proven composite cycles report the release's ISA type aggregate."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo

CASES = [
    'Core C { architectural_state { struct S { struct S s; } register struct S R; } }',
    'Core C { architectural_state { struct S { struct S s; } register struct S R[2]; } }',
    'Core C { architectural_state { union U { union U u; } register union U R; } }',
]
POSITIVES = [
    'Core C { architectural_state { struct S { struct S s; } } }',
    'Core C { architectural_state { struct S { unsigned<8> s; } register struct S R; } }',
]


class CompositeElaborationNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_cycles(self):
        for source in CASES:
            with self.subTest(source=source):
                self.error(source, 'IndeterminableIsaStateElementType')

    def test_unused_and_acyclic_types(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                self.validate(source)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class CompositeElaborationOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_cycles(self):
        for source in CASES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertIn('The types of the following state elements could not be determined because they depend on other indeterminable values: R', output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.IndeterminableIsaStateElementType')

    def test_unused_and_acyclic_types(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertNotIn('ERROR:', output)
                validate_source(tree, WarningsInfo())
