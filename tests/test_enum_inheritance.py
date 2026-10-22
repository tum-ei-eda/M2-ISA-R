"""Inherited enum support and documented release collision failures."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers

INHERITED = ('InstructionSet I { architectural_state { enum E { A = 7, B } } } '
             'InstructionSet J extends I { architectural_state { register enum E R; unsigned<4> W = B; } } '
             'Core C provides J {}')
COLLISIONS = [
    'Core C { architectural_state { enum E { A, A } } }',
    'Core C { architectural_state { int A = 1; enum E { A } } }',
    ('InstructionSet I { architectural_state { enum E { A } } } '
     'InstructionSet J { architectural_state { enum F { A } } } Core C provides I, J {}'),
]


class EnumInheritanceNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_inherited_enum(self):
        self.validate(INHERITED)

    def test_collisions(self):
        for source in COLLISIONS:
            with self.subTest(source=source):
                self.error(source, 'DuplicateIsaStateElement')


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class EnumInheritanceOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_inherited_enum(self):
        output, _ = self.probe(INHERITED)
        self.assertNotIn('ERROR:', output, output)

    def test_collision_reference_limitations(self):
        for source in COLLISIONS:
            with self.subTest(source=source):
                output, _ = self.probe(source, allow_internal_error=True)
                self.assertIn('An internal error occurred during analysis', output, output)


if __name__ == '__main__':
    unittest.main()
