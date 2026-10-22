import unittest
from types import SimpleNamespace
from unittest.mock import patch

from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.validate import validate_behav, run, main
from m2isar.diagnostics import M2WarningError
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsInfo, WarningsManager


def literal(value, kind, size):
    return behav.Literal(value, type_info.PrimitiveType(kind, size))


class BehaviorValidatorTest(unittest.TestCase):
    def test_shifts_in_function_bodies_of_cores_and_sets(self):
        for scope in ('cores', 'sets'):
            for op, width in (('<<', 8), ('>>', 8), ('<<', arch.Parameter('XLEN', 8, {}))):
                with self.subTest(scope=scope, op=op):
                    shift = behav.BinaryOperation(literal(1, type_info.TypeKind.UINT, width),
                                                 behav.Operator(op),
                                                 literal(8, type_info.TypeKind.UINT, 4))
                    function = SimpleNamespace(name='f', extern=False, ty=type_info.FunctionType(0, type_info.TypeKind.VOID),
                                               operation=behav.Operation([shift]))
                    definition = SimpleNamespace(name='C', functions={'f': function},
                                                 instructions={}, always_blocks={})
                    model = SimpleNamespace(cores={}, sets={})
                    getattr(model, scope)['C'] = definition
                    info = WarningsInfo(as_error={'shift-overflow'})
                    with self.assertLogs('validate_behav', level='ERROR'), self.assertRaises(RuntimeError) as exc:
                        validate_behav(model, info)
                    self.assertIn('com.minres.coredsl.ShiftAlwaysZero', str(exc.exception))
                    self.assertIsInstance(exc.exception, M2WarningError)
                    self.assertEqual(exc.exception.warning_name, 'shift-overflow')
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.ShiftAlwaysZero')

    def test_both_zero_comparison_exemptions(self):
        for zero_left in (True, False):
            signed_zero = literal(0, type_info.TypeKind.INT, 1)
            unsigned_value = literal(1, type_info.TypeKind.UINT, 8)
            lhs, rhs = (signed_zero, unsigned_value) if zero_left else (unsigned_value, signed_zero)
            comparison = behav.BinaryOperation(lhs, behav.Operator('=='), rhs)
            info = WarningsInfo(as_error={'sign-compare'})
            # A promoted warning would make either erroneous path fail.
            ValidateBehavVisitor().generate(comparison, WarningsManager(info))

    def test_standalone_cli_run_validates_loaded_model(self):
        args = SimpleNamespace(log='info', top_level='model.m2isarmodel', warnings=WarningsInfo())
        model = SimpleNamespace(cores={}, sets={})
        with patch('m2isar.transforms.validate_behav.validate.load_model', return_value=model):
            run(args)

    def test_standalone_cli_warning_promotion_and_suppression(self):
        shift = behav.BinaryOperation(literal(1, type_info.TypeKind.UINT, 8),
                                     behav.Operator('>>'),
                                     literal(8, type_info.TypeKind.UINT, 4))
        function = SimpleNamespace(name='f', extern=False, ty=type_info.FunctionType(0, type_info.TypeKind.VOID),
                                   operation=behav.Operation([shift]))
        definition = SimpleNamespace(name='C', functions={'f': function},
                                     instructions={}, always_blocks={})
        model = SimpleNamespace(cores={'C': definition}, sets={})
        with patch('m2isar.transforms.validate_behav.validate.load_model', return_value=model):
            with self.assertLogs('validate_behav', level='ERROR') as logs:
                with self.assertRaises(SystemExit) as exc:
                    main(['model.m2isarmodel', '-Werror=shift-overflow'])
            self.assertEqual(exc.exception.code, 1)
            self.assertIn('Validation failed:', logs.output[-1])
            self.assertIn('com.minres.coredsl.ShiftAlwaysZero', logs.output[-1])
            with self.assertNoLogs('validate_behav', level='WARNING'):
                main(['model.m2isarmodel', '-Werror=shift-overflow', '-Wno-shift-overflow'])
