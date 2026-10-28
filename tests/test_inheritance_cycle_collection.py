"""Collect cycle errors per participating ISA without reference crash noise."""
import os
import unittest
import test_source_validator as helpers
import test_isa_alias_parity as harness
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

CASES = [
    ('InstructionSet A extends A {}', ['A -> A'], 0),
    ('InstructionSet A extends A {} InstructionSet B extends B {}', ['A -> A', 'B -> B'], 0),
    ('InstructionSet A extends B {} InstructionSet B extends A {}', ['A -> B -> A', 'B -> A -> B'], 2),
    ('InstructionSet A extends A {} InstructionSet B extends A {}', ['A -> A'], 0),
    ('InstructionSet A extends B {} InstructionSet B extends A {} Core C provides A {}',
     ['A -> B -> A', 'B -> A -> B'], 3),
]

class InheritanceCycleNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_all_participants_and_independent_cycles(self):
        for text, chains, _ in CASES:
            with self.subTest(source=text):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(text)
                self.assertEqual(codes(caught.exception), ['CyclicInstructionSetInheritance'] * len(chains))
                diagnostics = [caught.exception, *caught.exception.related_diagnostics]
                for diagnostic, chain in zip(diagnostics, chains):
                    self.assertIn(chain, str(diagnostic))
        self.validate('InstructionSet A {} InstructionSet B extends A {} Core C provides B {}')

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class InheritanceCycleOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_cycles_and_known_internal_errors(self):
        for text, chains, internal_count in CASES:
            with self.subTest(source=text):
                output, _ = self.probe(text, allow_internal_error=True)
                self.assertEqual(output.count('ERROR:Cyclic instruction set inheritance:'), len(chains), output)
                self.assertEqual(output.count('ERROR:An internal error occurred during analysis:'), internal_count, output)
                self.assertEqual(output.count('ERROR:'), len(chains) + internal_count, output)
                for chain in chains:
                    self.assertIn('ERROR:Cyclic instruction set inheritance: ' + chain, output)
