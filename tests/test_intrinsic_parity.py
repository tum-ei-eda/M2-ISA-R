"""Intrinsic syntax, source sizing and release 2.0.21 diagnostics."""
import os
import unittest
import subprocess
import sys
import tempfile
from pathlib import Path
from m2isar.metamodel import load_model

from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo
import test_isa_alias_parity as harness
import test_source_validator as helpers


def function(body):
    return 'Core C { functions { void f() { ' + body + ' } } }'


ERRORS = [
    ('InvalidConstantExpressionNode', 'Intrinsic function offsetof is not allowed in constant expression', harness.state('int N = offsetof(int);')),
    ('InvalidArgumentCount', 'expects exactly one argument', function('int x = sizeof();')),
    ('InvalidArgumentCount', 'expects exactly one argument', function('int x = bitsizeof(1,2);')),
    ('InvalidArgumentCount', 'expects no arguments', function('int x = __encoding_size(1);')),
    ('InvalidIntrinsicFunction', 'can only be used within an instruction behavior', function('int x = __encoding_size();')),
    ('UnknownIntrinsicFunction', 'Unknown intrinsic function offsetof', function('int x = offsetof(int);')),
    ('UnknownIntrinsicFunction', 'Unknown intrinsic function bitoffsetof', function('int x = bitoffsetof(int);')),
    ('UnsupportedSizeOfDuringElaboration', 'Size of expression can not be determined during elaboration', harness.state('int N = bitsizeof(1+1);')),
    ('InvalidAssignmentType', 'Cannot implicitly convert', function('unsigned<1> x = bitsizeof(unsigned<8>);')),
]
POSITIVES = [
    function('int x = bitsizeof(unsigned<8>);'),
    function('int x = sizeof(unsigned<16>);'),
    function('int x[bitsizeof(unsigned<8>)];'),
    function('int x = bitsizeof(1+1);'),
    function('unsigned<8> a[4]; int x = bitsizeof(a);'),
    harness.state('int N = bitsizeof(unsigned<8>); register unsigned<N> R;'),
    harness.state('extern unsigned<8> M[1024]; int N = bitsizeof(M);'),
    "Core C { instructions { I { encoding: 8'h00; behavior: { int x = __encoding_size(); } } } }",
    'Core C { always { A { int x = __encoding_size; } } }',
]
WARNING = function('int x = sizeof(unsigned<3>);')


class IntrinsicNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_errors(self):
        for issue, _, source in ERRORS:
            with self.subTest(issue=issue, source=source):
                self.error(source, issue)

    def test_positives(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                self.validate(source)

    def test_rounding_warning(self):
        with self.assertLogs('validate_source') as logs:
            self.validate(WARNING)
        self.assertTrue(any('com.minres.coredsl.SizeOfNotExact' in line for line in logs.output))
        with self.assertNoLogs('validate_source', level='WARNING'):
            self.validate(WARNING, WarningsInfo(disabled={'size-of-not-exact'}))

    def test_model_lowering(self):
        source = """Core C {
          architectural_state {
            int W = bitsizeof(unsigned<8>);
            register unsigned<W> R;
          }
          instructions {
            I { encoding: 8'h00; behavior: { R = __encoding_size(); } }
          }
        }"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'intrinsic_flow.core_desc'
            path.write_text(source)
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser',
                                     str(path), '--validate', '--output', directory],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout)
            model = load_model(Path(directory) / 'intrinsic_flow.m2isarmodel')
            self.assertEqual(model.cores['C'].parameters['W'].value, 8)



@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class IntrinsicOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_errors(self):
        for issue, message, source in ERRORS:
            with self.subTest(issue=issue, source=source):
                output, tree = self.probe(source)
                self.assertIn('ERROR:', output)
                self.assertIn(message, output)
                with self.assertRaises(M2ValidationError) as exc:
                    validate_source(tree, WarningsInfo())
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)

    def test_positives(self):
        for source in POSITIVES:
            with self.subTest(source=source):
                output, tree = self.probe(source)
                self.assertNotIn('ERROR:', output, output)
                validate_source(tree, WarningsInfo())

    def test_rounding_warning(self):
        output, tree = self.probe(WARNING)
        self.assertNotIn('ERROR:', output, output)
        self.assertIn('The size (3 bits) is not an exact multiple of 8', output)
        with self.assertLogs('validate_source'):
            validate_source(tree, WarningsInfo())
