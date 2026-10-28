"""Known invalid declaration sizes must survive standalone validation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager


def integer(width):
    return type_info.PrimitiveType(type_info.TypeKind.UINT, width)


CASES = [
    ('unsigned<0> x;', integer(0), 'InvalidIntegerTypeSize', 'Integer type size must be greater than 0'),
    ('unsigned<(0-1)> x;', integer(-1), 'InvalidIntegerTypeSize', 'Integer type size must be greater than 0'),
    ('unsigned<2147483648> x;', integer(2147483648), 'InvalidIntegerTypeSize',
     'Integer type size must not exceed Integer.MAX_VALUE'),
    ('unsigned<8> x[-1];', type_info.ArrayType(integer(8), -1), 'InvalidArraySize', 'Negative array size is invalid'),
]


class MetamodelSizeNativeTest(unittest.TestCase):
    def test_saved_zero_width_model(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'size.core_desc'
            path.write_text('Core C { functions { void f() { unsigned<0> x; } } }')
            parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(parsed.returncode, 0, parsed.stdout)
            result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                     str(Path(directory) / 'gen_model' / 'size.m2isarmodel')],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('com.minres.coredsl.InvalidIntegerTypeSize', result.stdout)
            self.assertNotIn('Traceback', result.stdout)

    def test_invalid_declaration_and_tensor_sizes(self):
        for source, ty, issue, message in CASES:
            for node in (behav.VarDefinition(SimpleNamespace(ty=ty)), behav.Tensor([], ty)):
                with self.subTest(source=source, node=type(node).__name__):
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(node, WarningsManager(None))
                    self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.' + issue)
                    self.assertIn(message, str(caught.exception))

    def test_nested_and_parameter_sizes(self):
        for ty in (type_info.ArrayType(type_info.ArrayType(integer(8), -1), None),
                   type_info.ArrayType(integer(0), None),
                   integer(arch.Parameter('N', 0, {})),
                   type_info.ArrayType(integer(8), arch.Parameter('N', -1, {}))):
            with self.subTest(ty=ty), self.assertRaises(M2ValidationError):
                ValidateBehavVisitor().generate(behav.VarDefinition(SimpleNamespace(ty=ty)), WarningsManager(None))

    def test_unknown_and_zero_dimensions_defer(self):
        cyclic = arch.Parameter('N', None, {})
        cyclic.value = cyclic
        for ty in (integer(None), integer(cyclic), type_info.ArrayType(integer(8), None),
                   type_info.ArrayType(integer(8), cyclic), type_info.ArrayType(integer(8), 0)):
            with self.subTest(ty=type(ty).__name__):
                visitor = ValidateBehavVisitor()
                visitor.generate(behav.VarDefinition(SimpleNamespace(ty=ty)), WarningsManager(None))
                visitor.generate(behav.Tensor([], ty), WarningsManager(None))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelSizeOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_invalid_sizes(self):
        for source, ty, issue, message in CASES:
            with self.subTest(source=source):
                output, _ = self.probe('Core C { functions { void f() { ' + source + ' } } }')
                self.assertIn('ERROR:' + message, output, output)
                with self.assertRaises(M2ValidationError) as caught:
                    ValidateBehavVisitor().generate(behav.VarDefinition(SimpleNamespace(ty=ty)), WarningsManager(None))
                self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.' + issue)
