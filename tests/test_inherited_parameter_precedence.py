"""Elaborated duplicate parameter defaults follow provider order and overrides."""
import os
import unittest
import test_source_validator as helpers
import test_isa_alias_parity as harness
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


DEFINITIONS = ('InstructionSet A {architectural_state{unsigned<8> P=1;}} '
               'InstructionSet B {architectural_state{unsigned<8> P=2;}} ')
CASES = [
    ('A,B', '', True),
    ('B,A', '', False),
    ('A,B', 'P=1;', False),
    ('B,A', 'P=2;', True),
    ('A,B', 'unsigned<8> P=1;', False),
    ('B,A', 'unsigned<8> P=2;', True),
]


def source(providers, override):
    state = 'architectural_state{' + override + '}' if override else ''
    return (DEFINITIONS + 'Core C provides ' + providers + ' {' + state +
            'functions{void f(){unsigned<1> x=P;}}}')


class InheritedParameterPrecedenceNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_provider_order_and_explicit_overrides(self):
        for providers, override, invalid in CASES:
            with self.subTest(providers=providers, override=override):
                expected = (['DuplicateIsaStateElement'] if override.startswith('unsigned') else [])
                expected += ['InvalidAssignmentType'] if invalid else []
                with self.assertLogs('validate_source', level='WARNING') as logs:
                    if expected:
                        with self.assertRaises(M2ValidationError) as caught:
                            self.validate(source(providers, override))
                        self.assertEqual(codes(caught.exception), expected)
                    else:
                        self.validate(source(providers, override))
                self.assertEqual(sum('[-Wduplicate-isa-state-element]' in line for line in logs.output), 1)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class InheritedParameterPrecedenceOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_provider_order_and_overrides(self):
        for providers, override, invalid in CASES:
            with self.subTest(providers=providers, override=override):
                output, _ = self.probe(source(providers, override))
                duplicate = int(override.startswith('unsigned'))
                self.assertEqual(output.count('ERROR:'), int(invalid) + duplicate, output)
                self.assertEqual(output.count('ERROR:An identifier with the name P has already been declared'),
                                 duplicate, output)
                self.assertEqual(output.count('ERROR:Cannot implicitly convert unsigned<8> to unsigned<1>'),
                                 int(invalid), output)
                self.assertEqual(output.count('WARNING:'), 1, output)
