"""Missing ISA dependencies do not hide independent linking failures."""
import os
import unittest
import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

CASES = [
    ('Core C provides A,B {}', [('InstructionSet', 'A'), ('InstructionSet', 'B')]),
    ('InstructionSet A extends X {} Core C provides Y {}', [('InstructionSet', 'X'), ('InstructionSet', 'Y')]),
    ('Core C provides A {functions{void f(){missing();}}}', [('InstructionSet', 'A'), ('NamedEntity', 'missing')]),
    ('Core Other {} Core C provides Other,Missing {}', [('InstructionSet', 'Other'), ('InstructionSet', 'Missing')]),
    ('InstructionSet I {} Core C provides I,Missing {functions{void f(){int x=absent;}}}',
     [('InstructionSet', 'Missing'), ('NamedEntity', 'absent')]),
]
VALID = 'InstructionSet A {} InstructionSet B extends A {} Core C provides A,B {}'

class DependencyLinkingNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_independent_dependency_and_body_errors(self):
        for text, expected in CASES:
            with self.subTest(source=text):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(text)
                self.assertEqual(codes(caught.exception), ['Linking'] * len(expected))
                for kind, name in expected:
                    self.assertIn(kind + " '" + name + "'", str(caught.exception))
        self.validate(VALID)

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class DependencyLinkingOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_dependency_and_body_error_counts(self):
        for text, expected in CASES + [(VALID, [])]:
            with self.subTest(source=text):
                output, _ = self.probe(text)
                self.assertEqual(output.count('ERROR:'), len(expected), output)
                for kind, name in expected:
                    self.assertIn("Couldn't resolve reference to " + kind + " '" + name + "'", output)
