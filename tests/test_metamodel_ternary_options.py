"""Known ternary option types obey the release's equality/integer rules."""
import os
import unittest
from types import SimpleNamespace

import test_isa_alias_parity as harness
from test_metamodel_conditions import ARRAY, VOID, condition
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager


INT = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
UINT = type_info.PrimitiveType(type_info.TypeKind.UINT, 32)
OTHER_ARRAY = type_info.ArrayType(INT, 3)
CASES = [
    ('a', ARRAY, 'x', INT, True),
    ('x', INT, 'a', ARRAY, True),
    ('a', ARRAY, 'b', OTHER_ARRAY, True),
    ('g()', VOID, 'x', INT, True),
    ('x', INT, 'g()', VOID, True),
    ('a', ARRAY, 'a', ARRAY, False),
    ('g()', VOID, 'g()', VOID, False),
    ('x', INT, 'u', UINT, False),
]


def node(left, right, cond=INT):
    return behav.Ternary(condition(cond), condition(left), condition(right))


class MetamodelTernaryOptionsNativeTest(unittest.TestCase):
    def test_invalid_options_do_not_cascade_into_enclosing_checks(self):
        for grouped in (False, True):
            for enclosing in ('condition', 'option', 'return', 'assignment'):
                with self.subTest(grouped=grouped, enclosing=enclosing):
                    invalid = node(ARRAY, INT)
                    # Model inference may retain a concrete execution type even
                    # though semantic analysis has rejected the option pair.
                    invalid.ty = ARRAY
                    if grouped:
                        invalid = behav.Group(invalid)
                        invalid.ty = ARRAY
                    if enclosing == 'condition':
                        expression = behav.Ternary(invalid, condition(INT), condition(INT))
                    elif enclosing == 'option':
                        expression = behav.Ternary(condition(INT), invalid, condition(INT))
                    elif enclosing == 'return':
                        expression = behav.Return(invalid)
                    else:
                        expression = behav.Assignment(condition(INT), invalid)
                    context = WarningsManager(None)
                    context.function = SimpleNamespace(ty=type_info.FunctionType(32, type_info.TypeKind.INT))
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(expression, context)
                    self.assertEqual(codes(caught.exception), ['IncompatibleOptionTypes'])

    def test_known_options(self):
        for left, left_type, right, right_type, rejected in CASES:
            with self.subTest(left=left, right=right):
                visitor = ValidateBehavVisitor()
                if rejected:
                    with self.assertRaises(M2ValidationError) as caught:
                        visitor.generate(node(left_type, right_type), WarningsManager(None))
                    self.assertEqual(codes(caught.exception), ['IncompatibleOptionTypes'])
                else:
                    visitor.generate(node(left_type, right_type), WarningsManager(None))

    def test_condition_and_options_are_both_reported(self):
        with self.assertRaises(M2ValidationError) as caught:
            ValidateBehavVisitor().generate(node(ARRAY, INT, VOID), WarningsManager(None))
        self.assertEqual(codes(caught.exception),
                         ['NonScalarCondition', 'IncompatibleOptionTypes'])

    def test_unknown_option_types_defer(self):
        for unknown in (None, type_info.ArrayType(INT, None),
                        type_info.PointerType(INT)):
            for left, right in ((unknown, ARRAY), (ARRAY, unknown)):
                with self.subTest(left=left, right=right):
                    ValidateBehavVisitor().generate(node(left, right), WarningsManager(None))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelTernaryOptionsOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_invalid_options_do_not_cascade(self):
        for statement in ('if (1?a:x) {}', 'int y=(1?a:x)?1:2;',
                          'int y=1?(1?a:x):x;', 'return (1?a:x);', 'x=1?a:x;'):
            with self.subTest(statement=statement):
                source = ('Core C { functions { int f() { int a[2]; int x; '
                          + statement + ' return 0; } } }')
                output, _ = self.probe(source)
                self.assertEqual(output.count('ERROR:Incompatible option types:'), 1, output)
                self.assertEqual(output.count('ERROR:'), 1, output)

    def test_release_option_rules(self):
        for left, left_type, right, right_type, rejected in CASES:
            with self.subTest(left=left, right=right):
                source = ('Core C { functions { void g() {} void f() { '
                          'int a[2]; int b[3]; int x; unsigned int u; '
                          'if (1 ? ' + left + ' : ' + right + ') {} } } }')
                output, _ = self.probe(source)
                self.assertEqual(output.count('ERROR:Incompatible option types:'),
                                 int(rejected), output)
                # Equal arrays/void remain valid option pairs, but cannot be conditions.
                condition_error = not rejected and left_type in (ARRAY, VOID)
                self.assertEqual(output.count('ERROR:'), int(rejected) + int(condition_error), output)
                if rejected:
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(node(left_type, right_type), WarningsManager(None))
                    self.assertIn('ERROR:' + str(caught.exception).split(' [', 1)[0], output)
