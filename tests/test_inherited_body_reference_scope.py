"""Inherited function references retain defining-ISA types and Core values."""
import os
import unittest
import test_source_validator as helpers
import test_isa_alias_parity as harness
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

CASES = [(width, value, redeclare) for width in (8,16) for value in (1,2) for redeclare in (False,True)]

def source(width, value, redeclare):
    override = ('unsigned<' + str(24-width) + '> ' if redeclare else '') + 'P=' + str(value) + ';'
    return ('InstructionSet A {architectural_state{unsigned<' + str(width) + '> P=1;} '
            'functions{void f(){unsigned<1> x=P;}}} Core C provides A {'
            'architectural_state{' + override + '}}')

class InheritedBodyScopeNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_defining_type_and_elaborated_value(self):
        for width, value, redeclare in CASES:
            with self.subTest(width=width,value=value,redeclare=redeclare):
                expected = ['DuplicateIsaStateElement','MismatchingIsaStateElementSignatures'] if redeclare else []
                if value == 2:
                    expected += ['InvalidAssignmentType']
                if expected:
                    with self.assertRaises(M2ValidationError) as caught:
                        self.validate(source(width,value,redeclare))
                    self.assertEqual(codes(caught.exception), expected)
                    if value == 2:
                        self.assertIn('unsigned<' + str(width) + '> to unsigned<1>', str(caught.exception))
                else:
                    self.validate(source(width,value,redeclare))

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class InheritedBodyScopeOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_inherited_body_context(self):
        for width, value, redeclare in CASES:
            with self.subTest(width=width,value=value,redeclare=redeclare):
                output, _ = self.probe(source(width,value,redeclare))
                self.assertEqual(output.count('ERROR:'), 2*int(redeclare) + int(value==2), output)
                if value == 2:
                    self.assertIn('Cannot implicitly convert unsigned<' + str(width) + '> to unsigned<1>', output)
                    self.assertIn('function A.f:', output)
