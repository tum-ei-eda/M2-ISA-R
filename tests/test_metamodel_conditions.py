"""Standalone condition diagnostics compared with MINRES source behavior."""
import os
import unittest
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info
from m2isar.transforms.validate_behav.validate import main
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsInfo, WarningsManager


def conditional(x):
    return behav.Conditional([x], [behav.Block([])])


CASES = [
    ('if (x) {}', conditional),
    ('while (x) {}', lambda x: behav.Loop(x, [], False)),
    ('do {} while (x);', lambda x: behav.Loop(x, [], True)),
    ('int y = x ? 1 : 0;', lambda x: behav.Ternary(x, behav.Literal(1), behav.Literal(0))),
]
ARRAY = type_info.ArrayType(type_info.PrimitiveType(type_info.TypeKind.INT, 32), 2)
VOID = type_info.PrimitiveType(type_info.TypeKind.VOID, 0)


def condition(ty):
    value = behav.NamedReference(None)
    value.ty = ty
    return value


class MetamodelConditionNativeTest(unittest.TestCase):
    def test_parser_roundtrip_and_standalone_void_condition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'condition.core_desc'
            path.write_text('Core C { functions { void g() {} void f() { if (g()) {} } } }')
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            model = Path(directory) / 'gen_model' / 'condition.m2isarmodel'
            result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(model)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('The condition must be a scalar type, but was void', result.stdout)
            self.assertIn('com.minres.coredsl.NonScalarCondition', result.stdout)
            self.assertNotIn('Traceback', result.stdout)
            path.write_text('Core C { functions { void g() {} void f() { g(); } } }')
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(model)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_known_non_scalar_conditions(self):
        for ty, name in ((ARRAY, 'signed<32>[2]'), (VOID, 'void')):
            for _, build in CASES:
                with self.subTest(type=name, node=build):
                    with self.assertRaises(M2ValidationError) as exc:
                        ValidateBehavVisitor().generate(build(condition(ty)), WarningsManager(WarningsInfo()))
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.NonScalarCondition')
                    self.assertIn('The condition must be a scalar type, but was ' + name, str(exc.exception))

    def test_integer_conditions_and_deferred_providers(self):
        for ty in (None, type_info.PrimitiveType(type_info.TypeKind.INT, 32),
                   type_info.PrimitiveType(type_info.TypeKind.UINT, 1),
                   type_info.PointerType(ARRAY), type_info.FloatType(8, 23, 32),
                   type_info.ArrayType(type_info.PrimitiveType(type_info.TypeKind.INT, None), 2)):
            for _, build in CASES:
                with self.subTest(type=ty, node=build):
                    ValidateBehavVisitor().generate(build(condition(ty)), WarningsManager(None))

    def test_standalone_cli_reports_condition_error(self):
        function = SimpleNamespace(name='f', extern=False, ty=type_info.FunctionType(0, type_info.TypeKind.VOID),
                                   operation=behav.Operation([conditional(condition(ARRAY))]))
        core = SimpleNamespace(name='C', functions={'f': function}, instructions={}, always_blocks={})
        model = SimpleNamespace(cores={'C': core}, sets={})
        with patch('m2isar.transforms.validate_behav.validate.load_model', return_value=model):
            with self.assertLogs('validate_behav', level='ERROR') as logs:
                with self.assertRaises(SystemExit) as exc:
                    main(['model.m2isarmodel'])
            self.assertEqual(exc.exception.code, 1)
            self.assertIn('com.minres.coredsl.NonScalarCondition', logs.output[-1])


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelConditionOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_conditions_and_metamodel_diagnostics(self):
        for statement, build in CASES:
            with self.subTest(statement=statement):
                output, _ = self.probe('Core C { functions { void f() { int x[2]; ' + statement + ' } } }')
                with self.assertRaises(M2ValidationError) as exc:
                    ValidateBehavVisitor().generate(build(condition(ARRAY)), WarningsManager(None))
                self.assertIn('ERROR:' + str(exc.exception).split(' [', 1)[0], output, output)
        output, _ = self.probe('Core C { functions { void g() {} void f() { if (g()) {} } } }')
        with self.assertRaises(M2ValidationError) as exc:
            ValidateBehavVisitor().generate(conditional(condition(VOID)), WarningsManager(None))
        self.assertIn('ERROR:' + str(exc.exception).split(' [', 1)[0], output, output)
