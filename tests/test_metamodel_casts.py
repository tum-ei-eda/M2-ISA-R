"""Standalone cast diagnostics retain release result/recovery semantics."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest

import test_isa_alias_parity as harness
from test_metamodel_conditions import ARRAY, VOID, condition
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import M2Model, M2_METAMODEL_VERSION, arch, behav, dump_model, type_info
from m2isar.transforms.validate_behav.validate import ValidatorContext, validate_behav
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor


INT = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
CASES = [('a', ARRAY, 'signed', None), ('g()', VOID, 'signed', None),
         ('a', ARRAY, 'signed<8>', 8), ('g()', VOID, 'signed<8>', 8)]


def cast(operand, width, kind=type_info.TypeKind.INT):
    result = behav.TypeConv(kind, width, operand)
    result.ty = (operand.ty if width is None else type_info.PrimitiveType(kind, width))
    return result


def model(expression):
    function = SimpleNamespace(name='f', extern=False, ty=type_info.FunctionType(0, type_info.TypeKind.VOID),
                               operation=behav.Operation([expression]))
    core = SimpleNamespace(name='C', functions={'f': function}, instructions={}, always_blocks={})
    return M2Model(M2_METAMODEL_VERSION, {'C': core}, {}, {})


class MetamodelCastNativeTest(unittest.TestCase):
    def test_frontends_preserve_invalid_casts_for_saved_validation(self):
        for frontend, root_kind in (('coredsl2', 'Core'),
                                    ('coredsl2_set', 'InstructionSet')):
            for operand, source_type, spelling, width in CASES:
                with self.subTest(frontend=frontend, operand=operand, cast=spelling):
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / 'cast.core_desc'
                        path.write_text(root_kind + ' C { functions { void g() {} void f() { '
                                        'int a[2]; if ((' + spelling + ')' + operand + ') {} } } }')
                        parsed = subprocess.run(
                            [sys.executable, '-m', f'm2isar.frontends.{frontend}.parser', str(path)],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        self.assertEqual(parsed.returncode, 0, parsed.stdout)
                        checked = subprocess.run(
                            [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                             str(Path(directory) / 'gen_model' / 'cast.m2isarmodel')],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        self.assertEqual(checked.returncode, 1, checked.stdout)
                        self.assertEqual(checked.stdout.count('com.minres.coredsl.InvalidCast'), 1,
                                         checked.stdout)
                        self.assertNotIn('com.minres.coredsl.NonScalarCondition', checked.stdout)
                        self.assertNotIn('Traceback', checked.stdout)

    def test_known_invalid_casts(self):
        for operand, source_type, spelling, width in CASES:
            with self.subTest(operand=operand, cast=spelling):
                with self.assertRaises(M2ValidationError) as caught:
                    ValidateBehavVisitor().generate(cast(condition(source_type), width), ValidatorContext(None))
                self.assertEqual(codes(caught.exception), ['InvalidCast'])

    def test_integer_casts_and_unknown_providers(self):
        for source_type in (INT, type_info.PrimitiveType(type_info.TypeKind.UINT, 8),
                            None, type_info.ArrayType(INT, None), type_info.PointerType(INT)):
            for width in (None, 4, 64):
                with self.subTest(source=source_type, width=width):
                    ValidateBehavVisitor().generate(cast(condition(source_type), width), ValidatorContext(None))

    def test_child_errors_and_explicit_target_recovery(self):
        function = arch.Function('g', {}, 0, type_info.TypeKind.VOID, [], None, extern=True)
        for width in (None, 33):
            with self.subTest(width=width):
                child = behav.ProcedureCall(function, [behav.Literal(1)])
                child.ty = VOID
                expression = cast(child, width, type_info.TypeKind.UINT)
                context = ValidatorContext(None, function=SimpleNamespace(
                    ty=type_info.FunctionType(32, type_info.TypeKind.INT)))
                with self.assertRaises(M2ValidationError) as caught:
                    ValidateBehavVisitor().generate(behav.Return(expression), context)
                expected = ['InvalidArgumentCount', 'InvalidCast']
                if width is not None:
                    expected.append('ReturnTypeNotConvertible')
                self.assertEqual(codes(caught.exception), expected)

    def test_saved_model_api_and_cli(self):
        for operand, source_type, spelling, width in CASES:
            with self.subTest(operand=operand, cast=spelling), tempfile.TemporaryDirectory() as directory:
                saved = model(cast(condition(source_type), width))
                with self.assertRaises(M2ValidationError) as caught:
                    validate_behav(saved, None)
                self.assertEqual(codes(caught.exception), ['InvalidCast'])
                path = Path(directory) / 'cast.m2isarmodel'
                dump_model(saved, path)
                checked = subprocess.run(
                    [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(path)],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(checked.returncode, 1, checked.stdout)
                self.assertIn('com.minres.coredsl.InvalidCast', checked.stdout)
                self.assertNotIn('Traceback', checked.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelCastOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_cast_diagnostics_and_recovery(self):
        for operand, source_type, spelling, width in CASES:
            with self.subTest(operand=operand, cast=spelling):
                output, _ = self.probe('Core C { functions { void g() {} void f() { '
                                       'int a[2]; if ((' + spelling + ')' + operand + ') {} } } }')
                self.assertEqual(output.count('ERROR:'), 1, output)
                with self.assertRaises(M2ValidationError) as caught:
                    ValidateBehavVisitor().generate(cast(condition(source_type), width), ValidatorContext(None))
                self.assertIn('ERROR:' + str(caught.exception).split(' [', 1)[0], output)
        for spelling, count in (('unsigned', 2), ('unsigned<33>', 3)):
            output, _ = self.probe('Core C { functions { void g() {} '
                                   'int f() { return (' + spelling + ')g(1); } } }')
            self.assertEqual(output.count('ERROR:'), count, output)
            self.assertEqual(output.count('ERROR:Incorrect argument count.'), 1, output)
            cast_errors = output.count('ERROR:Cannot cast from') + output.count('ERROR:Cannot apply signedness cast')
            self.assertEqual(cast_errors, 1, output)
            self.assertEqual(output.count('ERROR:Cannot convert from'), count - 2, output)
