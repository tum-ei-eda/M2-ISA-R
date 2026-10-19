"""Signature failures retain body diagnostics and lexical reference types."""
import os
import unittest
import test_source_validator as helpers
import test_isa_alias_parity as harness
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError

CASES = [(first, second, body, extra) for first, second in ((8,16), (16,8))
         for body, extra in (('', []), ('g(1);', ['InvalidArgumentCount']),
                             ('unsigned<1> x=P;', ['InvalidAssignmentType']))]

def source(first, second, body):
    return ('InstructionSet A {architectural_state{unsigned<' + str(first) + '> P=1;}} '
            'InstructionSet B {architectural_state{unsigned<' + str(second) + '> P=2;}} '
            'Core C provides A,B {functions{void g(){} void f(){' + body + '}}}')

class SignatureMismatchNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_body_errors_after_signature_mismatch(self):
        for first, second, body, extra in CASES:
            with self.subTest(first=first, body=body):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(first,second,body))
                self.assertEqual(codes(caught.exception), ['MismatchingIsaStateElementSignatures'] + extra)
                if extra == ['InvalidAssignmentType']:
                    self.assertIn('unsigned<' + str(first) + '> to unsigned<1>', str(caught.exception))

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class SignatureMismatchOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_signature_and_independent_body_errors(self):
        for first, second, body, extra in CASES:
            with self.subTest(first=first, body=body):
                output, _ = self.probe(source(first,second,body))
                self.assertEqual(output.count('ERROR:'), 1 + len(extra), output)
                self.assertEqual(output.count('with mismatching signatures'), 1, output)
                if extra == ['InvalidArgumentCount']:
                    self.assertIn('ERROR:Incorrect argument count.', output)
                if extra == ['InvalidAssignmentType']:
                    self.assertIn('ERROR:Cannot implicitly convert unsigned<' + str(first) + '> to unsigned<1>', output)
