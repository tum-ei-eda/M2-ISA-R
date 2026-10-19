"""Casts change the inferred result kind without changing the operand type."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
from m2isar.metamodel import arch, behav, load_model, type_info
from m2isar.transforms.infer_types.visitor import InferTypesMutator
from m2isar.warnings import WarningsManager


KINDS = (type_info.TypeKind.INT, type_info.TypeKind.UINT)


def spelling(kind, width):
    name = 'signed' if kind == type_info.TypeKind.INT else 'unsigned'
    return name if width is None else f'{name}<{width}>'


def function(source, target, width):
    result_width = 8 if width is None else width
    return (f'{spelling(target, result_width)} f({spelling(source, 8)} x) '
            + '{ return (' + spelling(target, width) + ')x; }')


class CastSignednessLoweringNativeTest(unittest.TestCase):
    def test_inferred_kind_width_and_operand_are_independent(self):
        for source in KINDS:
            for target in KINDS:
                for width in (None, 4, 8, 16):
                    with self.subTest(source=source, target=target, width=width):
                        original = type_info.PrimitiveType(source, 8)
                        operand = behav.NamedReference(arch.Variable('x', original))
                        expression = behav.TypeConv(target, width, operand)
                        result = InferTypesMutator().generate(expression, WarningsManager(None))
                        self.assertEqual((result.ty.kind, result.ty.size),
                                         (target, 8 if width is None else width))
                        self.assertIsNot(result.ty, original)
                        self.assertEqual((original.kind, original.size), (source, 8))

    def test_frontend_and_saved_model_return_types(self):
        for frontend, root_kind, collection in (
                ('coredsl2', 'Core', 'cores'),
                ('coredsl2_set', 'InstructionSet', 'sets')):
            for source, target in ((KINDS[0], KINDS[1]), (KINDS[1], KINDS[0])):
                for width in (None, 4, 8, 16):
                    with self.subTest(frontend=frontend, source=source, width=width):
                        with tempfile.TemporaryDirectory() as directory:
                            path = Path(directory) / 'cast.core_desc'
                            path.write_text(root_kind + ' C { functions { '
                                            + function(source, target, width) + ' } }')
                            parsed = subprocess.run(
                                [sys.executable, '-m', f'm2isar.frontends.{frontend}.parser',
                                 str(path), '--validate'], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                            self.assertEqual(parsed.returncode, 0, parsed.stdout)
                            model_path = Path(directory) / 'gen_model' / 'cast.m2isarmodel'
                            model = load_model(model_path)
                            f = getattr(model, collection)['C'].functions['f']
                            returned = f.operation.statements[0].statements[0].expr
                            self.assertEqual((returned.ty.kind, returned.ty.size),
                                             (target, 8 if width is None else width))
                            validated = subprocess.run(
                                [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                 str(model_path)], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                            self.assertEqual(validated.returncode, 0, validated.stdout)
                            self.assertNotIn('Traceback', validated.stdout)

    def test_uncast_signedness_mismatch_still_fails(self):
        for source, target in ((KINDS[0], KINDS[1]), (KINDS[1], KINDS[0])):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'uncast.core_desc'
                path.write_text('Core C { functions { '
                                + function(source, target, None).replace(
                                    '(' + spelling(target, None) + ')x', 'x') + ' } }')
                parsed = subprocess.run(
                    [sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                checked = subprocess.run(
                    [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                     str(Path(directory) / 'gen_model' / 'uncast.m2isarmodel')],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(checked.returncode, 1, checked.stdout)
                self.assertIn('com.minres.coredsl.ReturnTypeNotConvertible', checked.stdout)
                self.assertNotIn('Traceback', checked.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class CastSignednessLoweringOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_cast_returns_and_uncast_controls(self):
        for source, target in ((KINDS[0], KINDS[1]), (KINDS[1], KINDS[0])):
            for width in (None, 4, 8, 16):
                with self.subTest(source=source, width=width):
                    text = 'Core C { functions { ' + function(source, target, width) + ' } }'
                    output, _ = self.probe(text)
                    self.assertNotIn('ERROR:', output)
            text = ('Core C { functions { ' + function(source, target, None).replace(
                '(' + spelling(target, None) + ')x', 'x') + ' } }')
            output, _ = self.probe(text)
            self.assertEqual(output.count('ERROR:Cannot convert from'), 1, output)
            self.assertEqual(output.count('ERROR:'), 1, output)
