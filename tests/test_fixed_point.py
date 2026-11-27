"""Binary fixed-point types: ``fixed<W, I>``, decimal literals, and ac_fixed's arithmetic rules."""
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.constant_expressions import fixed_literal
from m2isar.frontends.coredsl2.parser import main as parse
from m2isar.metamodel import behav, load_model, type_info
from m2isar.metamodel.type_info import TypeKind
from m2isar.metamodel.utils import fixed_point
from m2isar.metamodel.utils.fixed_point import FixedFormat
from m2isar.metamodel.utils.fixed_point import fixed_point_uses
from m2isar.transforms.infer_types.transform import infer_types
from m2isar.transforms.validate_behav.validate import validate_behav

# ac_fixed<W, I, S>::rt<W2, I2, S2> from ac_fixed.h, as (op, left, right, result).
RESULT_FORMATS = [
    ('*', FixedFormat(16, 4, True), FixedFormat(8, 1, True), FixedFormat(24, 5, True)),
    ('+', FixedFormat(16, 4, True), FixedFormat(8, 1, True), FixedFormat(17, 5, True)),
    ('+', FixedFormat(8, 2, False), FixedFormat(8, 2, True), FixedFormat(10, 4, True)),
    ('-', FixedFormat(8, 2, False), FixedFormat(8, 2, False), FixedFormat(9, 3, True)),
    ('+', FixedFormat(32, 13, True), FixedFormat(1, -1, False), FixedFormat(33, 14, True)),
    ('/', FixedFormat(16, 4, True), FixedFormat(8, 2, True), FixedFormat(23, 11, True)),
    ('/', FixedFormat(16, 4, False), FixedFormat(4, 6, False), FixedFormat(16, 2, False)),
    ('*', FixedFormat(8, 8, False), FixedFormat(8, 1, True), FixedFormat(16, 9, True)),
]

LITERALS = [
    ('0.75', Fraction(3, 4), 2, 0),
    ('1.5', Fraction(3, 2), 2, 1),
    ('2.0', Fraction(2), 2, 2),
    ('0.125', Fraction(1, 8), 1, -2),
    ('0.0', Fraction(0), 1, 1),
    ('1.5e3', Fraction(1500), 11, 11),
    ('1.25E+1', Fraction(25, 2), 5, 4),
]

# Function bodies valid at the source level.
VALID = [
    'void f() { fixed<16, 4> x = 0; fixed<16, 4> y = -0.5; }',
    'void f() { fixed<8, -2, false> x = 0.0625; }',
    'void f(fixed<8, 1> a, fixed<16, 4> b) { fixed<24, 5> p = a * b; }',
    'void f(fixed<8, 1> a, fixed<8, 1> b) { fixed<9, 2> s = a + b; fixed<9, 2> d = a - b; }',
    'void f(fixed<8, 1> a) { fixed<9, 2> n = -a; fixed<8, 1> p = +a; }',
    'void f(fixed<8, 1> a) { fixed<8, 1> s = a >> 1; s = a << 2; }',
    'void f(fixed<8, 1> a, signed<8> i) { bool b = a < 0.5 && a != i; if (a) {} }',
    'void f(fixed<8, 1> a, bool c) { fixed<9, 2> t = c ? a : 1.0; }',
    'void f(fixed<8, 1> a) { signed<4> i = (signed<4>)a; unsigned<8> bits = a[7:0]; unsigned<1> bit = a[7]; }',
    'void f(fixed<16, 4> a, unsigned<16> bits) { a[15:0] = bits; a = (fixed<16, 4>)bits; }',
    'void f(fixed<24, 8> acc, fixed<16, 8> p) { acc += p; acc -= p; acc *= p; acc >>= 2; }',
    'fixed<16, 8> f(fixed<8, 4> a) { return a; }',
    'void f(signed<8> i) { fixed<16, 12> x = i; }',
    'void f() { fixed<16, 4, true, AC_RND_CONV, AC_SAT> x = 0; fixed<8, 1, false, AC_RND> y = 0.5; fixed<8, 4, 1> z = 1; }',
    'void f(fixed<16, 4> a) { fixed<8, 2, true, AC_RND, AC_SAT> s = (fixed<8, 2, true, AC_RND, AC_SAT>)a; }',
    'void f(fixed<8, 1, true, AC_RND, AC_SAT_SYM> a) { fixed<8, 1> b = a; a = b; }',
]

# (function body, issue)
INVALID = [
    ('void f(fixed<8, 1> a) { fixed<8, 1> x = a & a; }', 'InvalidOperationType'),
    ('void f(fixed<8, 1> a) { fixed<8, 1> x = a % 2; }', 'InvalidOperationType'),
    ('void f(fixed<8, 1> a) { fixed<8, 1> x = ~a; }', 'InvalidOperationType'),
    ('void f(fixed<8, 1> a) { a++; }', 'InvalidOperationType'),
    ('void f(fixed<8, 1> a) { fixed<8, 1> x = a << a; }', 'InvalidOperationType'),
    ('void f(fixed<8, 1> a) { fixed<8, 1> x = (signed)a; }', 'InvalidCast'),
    ('void f(fixed<8, 1> a) { a <<= a; }', 'InvalidOperationType'),
    ('void f(fixed<8, 1> a, fixed<8, 1> b) { a = a + b; }', 'InvalidAssignmentType'),
    ('void f(fixed<16, 4> a) { fixed<16, 8> x = a; }', 'InvalidAssignmentType'),
    ('void f(fixed<8, 1> a) { fixed<8, 1, false> x = a; }', 'InvalidAssignmentType'),
    ('void f(fixed<8, 1> a) { signed<8> x = a; }', 'InvalidAssignmentType'),
    ('void f() { fixed<8, 1> x = 1.0; }', 'InvalidAssignmentType'),
    ('void f() { fixed<8, 4> x = 0.1; }', 'InvalidFixedPointLiteral'),
    ('void f() { fixed<8, 4> x = 0.5f; }', 'InvalidFixedPointLiteral'),
    ('void f() { fixed<0, 0> x = 0; }', 'InvalidIntegerTypeSize'),
    ('void f() { fixed<16, 4, true, AC_ROUND> x = 0; }', 'InvalidFixedPointType'),
    ('void f() { fixed<16, 4, true, AC_RND, AC_TRN> x = 0; }', 'InvalidFixedPointType'),
    ('void f() { fixed<16, 4, 2> x = 0; }', 'InvalidFixedPointType'),
]

MODEL = '''
Core FX {
    architectural_state {
        register unsigned<32> X[32] [[is_main_reg]];
        register fixed<8, 1> weight_q[4] = {0.5, -0.25, -1.0, 0};
        register fixed<16, 4> bias = -0.5;
        register fixed<12, 4, true, AC_RND, AC_SAT> scale = 1.5;
        register fixed<8, 0, false> gain[2];
    }
    functions {
        fixed<9, 2> mac(fixed<8, 1> a, fixed<8, 1> b) { return a + b; }
    }
    instructions {
        DENSEFX {
            encoding: 7'b0000101 :: rs2[4:0] :: rs1[4:0] :: 3'b000 :: rd[4:0] :: 7'b0001011;
            behavior: {
                fixed<32, 13> acc = bias;
                for (int i = 0; i < 4; i++) {
                    fixed<16, 4> elem;
                    elem[15:0] = X[rs1][15:0];
                    acc += elem * weight_q[i];
                }
                fixed<33, 13> half = acc * 0.5;
                X[rd] = (unsigned<32>)(signed<32>)(acc - 0.25);
            }
        }
    }
}
'''


def fixed(kind, size, int_bits):
    return type_info.FixedType(kind, size, int_bits)


def nodes(node):
    """Every behavior node below ``node``, depth first."""
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from nodes(item)
    elif isinstance(node, behav.BaseNode):
        yield node
        for value in vars(node).values():
            yield from nodes(value)


class FixedPointRulesTest(unittest.TestCase):
    def test_result_formats_follow_ac_fixed(self):
        for op, left, right, result in RESULT_FORMATS:
            with self.subTest(op=op, left=left, right=right):
                self.assertEqual(fixed_point.fixed_result(op, left, right), result)

    def test_integers_read_as_fixed_point(self):
        self.assertEqual(fixed_point.fixed_format(type_info.PrimitiveType(TypeKind.INT, 8)), FixedFormat(8, 8, True))
        self.assertEqual(fixed_point.fixed_format(fixed(TypeKind.UFIXED, 8, -2)), FixedFormat(8, -2, False))
        self.assertIsNone(fixed_point.fixed_format(type_info.PrimitiveType(TypeKind.VOID, 0)))

    def test_convertible_only_without_loss(self):
        convertible = fixed_point.fixed_convertible
        self.assertTrue(convertible(FixedFormat(8, 1, True), FixedFormat(16, 4, True)))
        self.assertTrue(convertible(FixedFormat(8, 1, False), FixedFormat(9, 2, True)))
        self.assertFalse(convertible(FixedFormat(8, 1, False), FixedFormat(8, 1, True)))  # integer bit
        self.assertFalse(convertible(FixedFormat(8, 1, True), FixedFormat(8, 1, False)))  # sign
        self.assertFalse(convertible(FixedFormat(24, 5, True), FixedFormat(24, 8, True)))  # fraction bits

    def test_holds_value(self):
        fmt = FixedFormat(8, 1, True)
        self.assertTrue(fixed_point.fixed_holds_value(fmt, Fraction(-1)))
        self.assertTrue(fixed_point.fixed_holds_value(fmt, Fraction(127, 128)))
        self.assertFalse(fixed_point.fixed_holds_value(fmt, 1))
        self.assertFalse(fixed_point.fixed_holds_value(fmt, Fraction(1, 256)))
        self.assertTrue(fixed_point.fixed_holds_value(FixedFormat(4, 6, False), 60))
        self.assertFalse(fixed_point.fixed_holds_value(FixedFormat(4, 6, False), 2))

    def test_names_leave_out_default_arguments(self):
        trn, rnd = type_info.QuantizationMode.AC_TRN, type_info.QuantizationMode.AC_RND
        wrap, sat = type_info.OverflowMode.AC_WRAP, type_info.OverflowMode.AC_SAT
        for ty, source, model in [
            (fixed(TypeKind.FIXED, 16, 4), 'fixed<16, 4>', 'FIXED<16,4>'),
            (fixed(TypeKind.UFIXED, 8, -2), 'fixed<8, -2, false>', 'UFIXED<8,-2>'),
            (type_info.FixedType(TypeKind.FIXED, 16, 4, rnd), 'fixed<16, 4, true, AC_RND>', 'FIXED<16,4,AC_RND>'),
            (type_info.FixedType(TypeKind.FIXED, 16, 4, trn, sat), 'fixed<16, 4, true, AC_TRN, AC_SAT>',
             'FIXED<16,4,AC_TRN,AC_SAT>'),
            (type_info.FixedType(TypeKind.UFIXED, 16, 4, rnd, wrap), 'fixed<16, 4, false, AC_RND>', 'UFIXED<16,4,AC_RND>'),
        ]:
            with self.subTest(source=source):
                self.assertEqual((ty.source_name(), str(ty)), (source, model))

    def test_literals(self):
        for text, value, width, int_bits in LITERALS:
            with self.subTest(text=text):
                self.assertEqual(fixed_literal(text), (value, width, int_bits))
        for text in ('0.1', '1.5f', '2.0L'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                fixed_literal(text)


class FixedPointSourceTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_valid_functions(self):
        for body in VALID:
            with self.subTest(body=body):
                self.validate('Core C { functions { ' + body + ' } }')

    def test_invalid_functions(self):
        for body, issue in INVALID:
            with self.subTest(body=body):
                self.error('Core C { functions { ' + body + ' } }', issue)

    def test_state(self):
        self.validate('Core C { architectural_state { register fixed<8, 1> W[2] = {0.5, -1.0}; } }')
        self.validate('Core C { architectural_state { register fixed<8, 0, false, AC_RND_INF, AC_SAT_ZERO> G = 0.5; } }')
        self.validate('Core C { architectural_state { unsigned int N = 12; register fixed<N, 4> R; } }')
        self.error('Core C { architectural_state { register fixed<8, 1> R = 1.0; } }', 'InvalidAssignmentType')
        self.error('Core C { architectural_state { fixed<8, 1> P = 0.5; } }', 'InvalidIsaParameterType')


class FixedPointModelTest(unittest.TestCase):
    def build(self, source, *arguments):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'fx.core_desc'
        path.write_text(source)
        parse([str(path), *arguments])
        return load_model(Path(directory.name) / 'gen_model' / 'fx.m2isarmodel')

    def test_lowered_types(self):
        model = self.build(MODEL, '--validate')
        core = model.cores['FX']
        self.assertEqual(str(core.register_banks['weight_q'].ty), 'ARRAY<FIXED<8,1>, 4>')
        self.assertEqual(core.register_banks['weight_q']._initval,
                         {0: Fraction(1, 2), 1: Fraction(-1, 4), 2: Fraction(-1), 3: 0})
        self.assertEqual(core.register_banks['bias']._initval, {None: Fraction(-1, 2)})
        self.assertEqual(str(core.register_banks['scale'].ty), 'FIXED<12,4,AC_RND,AC_SAT>')
        self.assertEqual(str(core.register_banks['gain'].ty), 'ARRAY<UFIXED<8,0>, 2>')
        self.assertEqual(str(core.functions['mac'].ty.return_type), 'FIXED<9,2>')

        operation = next(iter(core.instructions.values())).operation
        types = {str(node.ty) for node in nodes(operation) if isinstance(node, behav.BinaryOperation)}
        self.assertLessEqual({'FIXED<24,5>', 'FIXED<33,14>', 'FIXED<33,13>'}, types)
        literals = {node.value: str(node.ty) for node in nodes(operation)
                    if isinstance(node, behav.Literal) and isinstance(node.ty, type_info.FixedType)}
        self.assertEqual(literals, {Fraction(1, 2): 'UFIXED<1,0>', Fraction(1, 4): 'UFIXED<1,-1>'})
        slices = [node for node in nodes(operation) if isinstance(node, behav.SliceOperation)
                  and isinstance(node.expr.ty, type_info.FixedType)]
        self.assertEqual([str(node.ty) for node in slices], ['UINT<16>'])

    def test_value_conversion_carries_the_target_type(self):
        model = self.build('Core C { functions { fixed<16, 4, true, AC_RND, AC_SAT> f(unsigned<16> x) '
                           '{ return (fixed<16, 4, true, AC_RND, AC_SAT>)x; } } }', '--validate')
        function = model.cores['C'].functions['f']
        self.assertEqual(str(function.ty.return_type), 'FIXED<16,4,AC_RND,AC_SAT>')
        conversion = next(node for node in nodes(function.operation) if isinstance(node, behav.TypeConv))
        self.assertEqual((conversion.data_type, conversion.size), (TypeKind.FIXED, 16))
        self.assertEqual(str(conversion.fixed_type), 'FIXED<16,4,AC_RND,AC_SAT>')
        self.assertEqual(str(conversion.ty), 'FIXED<16,4,AC_RND,AC_SAT>')

    def test_operation_results_use_default_modes(self):
        model = self.build('Core C { functions { void f(fixed<8, 1, true, AC_RND, AC_SAT> a, signed<4> i) '
                           '{ fixed<9, 2> s = a + a; fixed<8, 1, true, AC_RND, AC_SAT> t = a >> i; } } }', '--validate')
        operations = {node.op.value: str(node.ty) for node in nodes(model.cores['C'].functions['f'].operation)
                      if isinstance(node, behav.BinaryOperation)}
        self.assertEqual(operations, {'+': 'FIXED<9,2>', '>>': 'FIXED<8,1,AC_RND,AC_SAT>'})

    def test_model_validation_without_source_validation(self):
        for body, issue in [
            ('void f(fixed<8, 1> a, fixed<8, 1> b) { a = a + b; }', 'InvalidAssignmentType'),
            ('void f(fixed<8, 1> a) { signed<8> x = a; }', 'InvalidAssignmentType'),
            ('void f(fixed<8, 1> a) { fixed<8, 1> x = (signed)a; }', 'InvalidCast'),
            ('void f(fixed<8, 1> a) { a++; }', 'InvalidOperationType'),
        ]:
            with self.subTest(body=body):
                model = self.build('Core C { functions { ' + body + ' } }')
                with self.assertRaises(M2ValidationError) as caught:
                    validate_behav(model, None)
                self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.' + issue)
        for body in VALID:
            with self.subTest(body=body):
                validate_behav(self.build('Core C { functions { ' + body + ' } }'), None)

    def test_type_inference_rejects_invalid_operators(self):
        for body in ('void f(fixed<8, 1> a) { fixed<8, 1> x = a & a; }',
                     'void f(fixed<8, 1> a) { fixed<8, 1> x = ~a; }',
                     'void f(fixed<8, 1> a) { fixed<8, 1> x = a << a; }'):
            with self.subTest(body=body):
                model = self.build('Core C { functions { ' + body + ' } }', '--no-infer-types')
                with self.assertRaises(M2ValidationError) as caught:
                    infer_types(model)
                self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.InvalidOperationType')

    def test_fixed_point_uses(self):
        model = self.build(MODEL)
        self.assertEqual(fixed_point_uses(model.cores['FX']),
                         ['register weight_q', 'register bias', 'register scale', 'register gain', 'function mac',
                          'instruction DENSEFX'])
        plain = self.build('Core C { architectural_state { register unsigned<32> X[32]; } }')
        self.assertEqual(fixed_point_uses(plain.cores['C']), [])


if __name__ == '__main__':
    unittest.main()
