"""Function call diagnostics in standalone models and the release validator."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager


def unsigned(width):
    return type_info.PrimitiveType(type_info.TypeKind.UINT, width)


def reference(width):
    node = behav.NamedReference(None)
    node.ty = unsigned(width)
    return node


CASES = [
    ('g();', [], 'InvalidArgumentCount', 'Incorrect argument count. Expected 1, got 0'),
    ('g(1,2);', [behav.Literal(1, unsigned(1)), behav.Literal(2, unsigned(2))],
     'InvalidArgumentCount', 'Incorrect argument count. Expected 1, got 2'),
    ('unsigned<16> x; g(x);', [reference(16)], 'InvalidArgumentType',
     'Cannot implicitly convert unsigned<16> to unsigned<8>'),
    ("g(16'd255);", [behav.Literal(255, unsigned(16))], None, None),
    ("g(16'd256);", [behav.Literal(256, unsigned(16))], 'InvalidArgumentType',
     'Cannot implicitly convert unsigned<16> to unsigned<8>'),
    ('unsigned<4> x; g(x);', [reference(4)], None, None),
]


def call(arguments):
    function = arch.Function('g', {}, 0, type_info.TypeKind.VOID,
                             [arch.FnParam('a', unsigned(8))], None, extern=True)
    return behav.ProcedureCall(function, arguments)


class MetamodelCallNativeTest(unittest.TestCase):
    def test_argument_count_and_conversion(self):
        for source, arguments, issue, message in CASES:
            with self.subTest(source=source):
                if issue:
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(call(arguments), WarningsManager(None))
                    self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.' + issue)
                    self.assertIn(message, str(caught.exception))
                else:
                    ValidateBehavVisitor().generate(call(arguments), WarningsManager(None))

    def test_saved_calls(self):
        for source, arguments, issue, message in CASES:
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'call.core_desc'
                path.write_text('Core C { functions { extern void g(unsigned<8> a); void f() { ' + source + ' } } }')
                parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(Path(directory) / 'gen_model' / 'call.m2isarmodel')],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, int(issue is not None), result.stdout)
                if issue:
                    self.assertIn('com.minres.coredsl.' + issue, result.stdout)
                    self.assertIn(message, result.stdout)
                self.assertNotIn('Traceback', result.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelCallOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_calls(self):
        for source, arguments, issue, message in CASES:
            with self.subTest(source=source):
                output, _ = self.probe('Core C { functions { extern void g(unsigned<8> a); void f() { ' + source + ' } } }')
                if issue:
                    self.assertIn('ERROR:' + message, output, output)
                    with self.assertRaises(M2ValidationError):
                        ValidateBehavVisitor().generate(call(arguments), WarningsManager(None))
                else:
                    self.assertNotIn('ERROR:', output, output)
                    ValidateBehavVisitor().generate(call(arguments), WarningsManager(None))
