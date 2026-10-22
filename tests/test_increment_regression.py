"""Increment lowering, saved-model diagnostics, and generated execution results."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
from string import Template
import tempfile
import unittest
import test_continue_regression as helpers
import test_source_unary_collection as unary_helpers
import test_isa_alias_parity as oracle_helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info, attribute_info as ai
from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
from m2isar.backends.etiss.instruction_utils import TransformerContext
from m2isar.transforms.validate_behav.validate import validate_behav

CASES = [
    ('unsigned<3> i=7;++i;return i;', 0),
    ('signed<3> i=3;++i;return i;', -4),
    ('signed<3> i=-4;--i;return i;', 3),
    ('unsigned<3> i=7;unsigned<3> n=i++;return n*10+i;', 70),
    ('signed<32> i=2147483647;++i;return i;', -2147483648),
    ('int i=1;int n=i++;return (int)(n*10+i);', 12),
    ('int i=1;int n=++i;return (int)(n*10+i);', 22),
    ('int i=2;int n=i--;return (int)(n*10+i);', 21),
    ('int i=2;int n=--i;return (int)(n*10+i);', 11),
    ('int n=0;for(int i=0;i<3;i++){if(i==1)continue;n++;}return n;', 2),
    ('int n=0;for(int i=0;i<3;i++){for(int j=0;j<2;j++){continue;}n++;}return n;', 3),
    ('unsigned<8> x=175;x[3:0]++;return x;', 160),
    ('unsigned<8> x=160;--x[3:0];return x;', 175),
    ('unsigned<8> x=175;unsigned<4> n=x[3:0]++;return n*16+x;', 400),
    ('unsigned<8> x=175;unsigned<4> n=++x[3:0];return n*16+x;', 160),
    ('unsigned<8> x=255;x[7:4]++;return x;', 15),
    ('int i=5;int n=0&&i++;return (int)(n*10+i);', 5),
    ('int i=5;int n=1&&i++;return (int)(n*10+i);', 16),
    ('int i=5;int n=0||i++;return (int)(n*10+i);', 16),
    ('int i=5;int n=1||i++;return (int)(n*10+i);', 15),
    ('int i=5;int n=i++&&0;return (int)(n*10+i);', 6),
    ('int i=5;int n=i++&&2;return (int)(n*10+i);', 16),
    ('int i=5;int n=i++||0;return (int)(n*10+i);', 16),
    ('int i=5;int n=i++||2;return (int)(n*10+i);', 16),
    ('unsigned<8> x=255;x[7:4][2:1]++;return x;', 159),
    ('unsigned<8> x=159;--x[7:4][2:1];return x;', 255),
    ('unsigned<8> x=255;unsigned<2> n=x[7:4][2:1]++;return n*256+x;', 927),
    ('unsigned<8> x=255;unsigned<2> n=++x[7:4][2:1];return n*256+x;', 159),
    ('unsigned<8> x=159;unsigned<2> n=x[7:4][2:1]--;return n*256+x;', 255),
    ('unsigned<8> x=159;unsigned<2> n=--x[7:4][2:1];return n*256+x;', 1023),
    ('unsigned<16> x=65535;x[15:8][6:3][2:1]++;return x;', 53247),
    ('signed<3> x=-1;++x[2:1];return x;', 1),
    ('signed<3> x=1;--x[2:1];return x;', -1),
]


def context(memories=None, functions=None):
    return TransformerContext({}, memories or {}, {}, {}, {}, {}, [], functions or {},
                              0, 32, 'C', False, {}, False, ignore_static=True)


def compile_run(case, program, directory):
    cpp = Path(directory) / 'increment.cpp'
    cpp.write_text('#include <cstdint>\n' + ''.join(
        'using etiss_' + kind + str(bits) + ' = ' + kind + str(bits) + '_t;\n'
        for kind in ('int', 'uint') for bits in (8, 16, 32, 64)) + program)
    binary = Path(directory) / 'increment'
    built = subprocess.run(['g++', '-std=c++11', str(cpp), '-o', str(binary)],
                           capture_output=True, text=True, timeout=30)
    case.assertEqual(built.returncode, 0, built.stderr + '\n' + program)
    case.assertEqual(subprocess.run([str(binary)], timeout=3).returncode, 0, program)


def memory_return_program(generated, initial, returned, stored, accesses):
    """Mock memory callbacks expose eager access and incorrect writeback."""
    program = '''
int addresses=0,reads=0,writes=0;etiss_uint8 value=INITIAL;
int next_address(){++addresses;return 7;}
struct CPU{int exception=0;};
int read(void*,CPU*,int address,etiss_uint8* out,int count){++reads;if(address!=7||count!=1)return 1;*out=value;return 0;}
int write(void*,CPU*,int address,etiss_uint8* in,int count){++writes;if(address!=7||count!=1)return 1;value=*in;return 0;}
struct System{void* handle=nullptr;decltype(&read) dread=read;decltype(&write) dwrite=write;};
void trap(int){throw 1;}
int f(){CPU c;CPU* cpu=&c;System s;System* system=&s;
'''.replace('INITIAL', str(initial)) + generated + '\n}\nint main(){int result=f();\n'
    return program + ('return result==' + str(returned) + '&&value==' + str(stored) +
                      '&&addresses==' + str(accesses) + '&&reads==' + str(accesses) +
                      '&&writes==' + str(accesses) + '?0:1;}')


class IncrementNativeTest(unittest.TestCase):
    def test_constant_logical_results_are_unsigned_one_bit_booleans(self):
        from m2isar.metamodel.utils.expr_simplifier import ExprSimplifierVisitor
        ty = type_info.PrimitiveType(type_info.TypeKind.INT, 8)
        for operator in ('&&', '||'):
            for left in (0, 2):
                for right in (0, 5):
                    with self.subTest(operator=operator, left=left, right=right):
                        expression = behav.BinaryOperation(behav.Literal(left, ty), behav.Operator(operator),
                                                           behav.Literal(right, ty))
                        simplified = ExprSimplifierVisitor().generate(expression, None)
                        expected = bool(left) and bool(right) if operator == '&&' else bool(left) or bool(right)
                        self.assertEqual(simplified.value, int(expected))
                        self.assertEqual(simplified.ty.kind, type_info.TypeKind.UINT)
                        self.assertEqual(simplified.ty.size, 1)

    def test_saved_invalid_targets_and_operand_types(self):
        cases = [
            ('void f(){++1;}', ['InvalidAssignmentTarget']),
            ('void f(){const int i=1;i++;}', ['InvalidAssignmentTarget']),
            ('void f(){int a[2];a++;}', ['InvalidOperationType']),
            ('void v(){} void f(){v()++;}', ['InvalidAssignmentTarget', 'InvalidOperationType']),
        ]
        for functions, expected in cases:
            with self.subTest(functions=functions), tempfile.TemporaryDirectory() as directory:
                model, _ = helpers.parse_model('Core C {functions {' + functions + '}}', directory)
                with self.assertRaises(M2ValidationError) as caught:
                    validate_behav(model, None)
                self.assertEqual(unary_helpers.codes(caught.exception), expected)

    def test_saved_models_validate_all_execution_cases(self):
        for body, _ in CASES:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                model, saved = helpers.parse_model(helpers.source(body, 'int'), directory, validated=True)
                validate_behav(model, None)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_saved_readonly_targets_remain_invalid_without_source_validation(self):
        for declaration, target in unary_helpers.READONLY_TARGETS:
            for operator, postfix in (('++', False), ('++', True), ('--', False), ('--', True)):
                with self.subTest(target=target, operator=operator, postfix=postfix), tempfile.TemporaryDirectory() as directory:
                    text = unary_helpers.readonly_source(declaration, target, operator, postfix)
                    model, _ = helpers.parse_model(text, directory)
                    with self.assertRaises(M2ValidationError) as caught:
                        validate_behav(model, None)
                    self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.InvalidAssignmentTarget')


@unittest.skipUnless(shutil.which('g++'), 'g++ required for generated-code execution')
class IncrementExecutionTest(unittest.TestCase):
    def test_nested_memory_slice_updates_write_underlying_cell_once(self):
        for operator in ('++', '--'):
            for postfix in (False, True):
                with self.subTest(operator=operator, postfix=postfix), tempfile.TemporaryDirectory() as directory:
                    memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                    ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                    base = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                    base.ty = ty
                    inner = behav.SliceOperation(base, behav.Literal(7, ty), behav.Literal(4, ty))
                    inner.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 4)
                    outer = behav.SliceOperation(inner, behav.Literal(2, ty), behav.Literal(1, ty))
                    outer.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 2)
                    update = behav.UnaryOperation(behav.Operator(operator), outer, postfix=postfix)
                    update.ty = outer.ty
                    trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                         0, type_info.TypeKind.VOID, [], None, extern=True)
                    generated = InstructionTransformVisitor().generate(behav.Operation([behav.Return(update)]),
                                                                      context({'M': memory}, {'trap': trap}))
                    initial, old, new, stored = (255, 3, 0, 159) if operator == '++' else (159, 0, 3, 255)
                    program = memory_return_program(generated.initial_required, initial, old if postfix else new, stored, 1)
                    compile_run(self, program, directory)

    def test_nested_memory_indices_preserve_access_and_writeback_order(self):
        self._check_nested_indices('memory')

    def test_array_and_register_bank_indices_preserve_memory_prerequisites(self):
        for outer_kind in ('array', 'register_bank'):
            self._check_nested_indices(outer_kind)

    def _check_nested_indices(self, outer_kind):
        inner_forms = [(None, False), ('++', False), ('++', True), ('--', False), ('--', True)]
        for inner_operator, inner_postfix in inner_forms:
            for outer_form in ('read', 'assign', 'slice_assign', 'prefix', 'postfix'):
                with self.subTest(outer_kind=outer_kind, inner_operator=inner_operator, inner_postfix=inner_postfix, outer_form=outer_form), tempfile.TemporaryDirectory() as directory:
                    memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                    ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                    inner = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                    inner.ty = ty
                    if inner_operator:
                        inner = behav.UnaryOperation(behav.Operator(inner_operator), inner, postfix=inner_postfix)
                        inner.ty = ty
                    if outer_kind == 'memory':
                        outer_reference = memory
                    elif outer_kind == 'array':
                        outer_reference = arch.Variable('bank', type_info.ArrayType(ty, 256))
                    else:
                        outer_reference = arch.RegisterBank('bank', 256, type_info.TypeKind.UINT, 8, {})
                    outer = behav.IndexedReference(outer_reference, inner)
                    outer.ty = ty
                    if outer_form == 'slice_assign':
                        slice_target = behav.SliceOperation(outer, behav.Literal(2, ty), behav.Literal(0, ty))
                        slice_target.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 3)
                        statements = [behav.Assignment(slice_target, behav.Literal(2, slice_target.ty)), behav.Return(behav.Literal(42, ty))]
                    elif outer_form == 'assign':
                        statements = [behav.Assignment(outer, behav.Literal(42, ty)), behav.Return(behav.Literal(42, ty))]
                    else:
                        value = outer
                        if outer_form != 'read':
                            value = behav.UnaryOperation(behav.Operator('++'), outer, postfix=outer_form == 'postfix')
                            value.ty = ty
                        statements = [behav.Return(value)]
                    trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                         0, type_info.TypeKind.VOID, [], None, extern=True)
                    generated = InstructionTransformVisitor().generate(behav.Operation(statements),
                                                                      context({'M': memory}, {'trap': trap}))
                    inner_stored = 5 if not inner_operator else 6 if inner_operator == '++' else 4
                    address = 5 if not inner_operator or inner_postfix else inner_stored
                    old = {4: 10, 5: 20, 6: 30}[address]
                    stored = (old & ~7) | 2 if outer_form == 'slice_assign' else 42 if outer_form == 'assign' else old if outer_form == 'read' else old + 1
                    returned = 42 if outer_form == 'slice_assign' else old if outer_form in ('read', 'postfix') else stored
                    trace = 'r7' + ('w7' if inner_operator else '')
                    if outer_kind == 'memory' and outer_form != 'assign':
                        trace += 'r' + str(address)
                    if outer_kind == 'memory' and outer_form != 'read':
                        trace += 'w' + str(address)
                    program = '''
#include <string>
std::string trace;int addresses=0;etiss_uint8 memory[256]={},bank[256]={};
int next_address(){++addresses;return 7;}
struct CPU{int exception=0;etiss_uint8* bank=::bank;};
int read(void*,CPU*,int address,etiss_uint8* out,int count){trace+="r"+std::to_string(address);if(address<0||address>=256||count!=1)return 1;*out=memory[address];return 0;}
int write(void*,CPU*,int address,etiss_uint8* in,int count){trace+="w"+std::to_string(address);if(address<0||address>=256||count!=1)return 1;memory[address]=*in;return 0;}
struct System{void* handle=nullptr;decltype(&read) dread=read;decltype(&write) dwrite=write;};
void trap(int){throw 1;}
int f(){CPU c;CPU* cpu=&c;System s;System* system=&s;
''' + Template(generated.initial_required).safe_substitute(ARCH_NAME='CPU') + '\n}\n'
                    program += 'int main(){memory[7]=5;memory[4]=bank[4]=10;memory[5]=bank[5]=20;memory[6]=bank[6]=30;int result=f();\n'
                    program += ('return result==' + str(returned) + '&&memory[7]==' + str(inner_stored) +
                                '&&' + ('memory' if outer_kind == 'memory' else 'bank') + '[' + str(address) + ']==' + str(stored) + '&&addresses==1&&trace=="' + trace + '"?0:1;}')
                    compile_run(self, program, directory)

    def test_logical_memory_operands_short_circuit_and_normalize_to_bool(self):
        for operator in ('&&', '||'):
            for left in (False, True):
                for initial in (0, 1, 5):
                    for postfix in (False, True):
                        for nested in (False, True):
                            with self.subTest(operator=operator, left=left, initial=initial, postfix=postfix, nested=nested), tempfile.TemporaryDirectory() as directory:
                                memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                                target = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                                target.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                                update = behav.UnaryOperation(behav.Operator('--'), target, postfix=postfix)
                                update.ty = target.ty
                                right = update
                                if nested:
                                    right = behav.Ternary(behav.Literal(1, target.ty), update, behav.Literal(42, target.ty))
                                expression = behav.BinaryOperation(behav.Literal(int(left), target.ty), behav.Operator(operator), right)
                                trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                                     0, type_info.TypeKind.VOID, [], None, extern=True)
                                generated = InstructionTransformVisitor().generate(behav.Operation([behav.Return(expression)]),
                                                                                  context({'M': memory}, {'trap': trap}))
                                selected = left if operator == '&&' else not left
                                updated = (initial - 1) & 255
                                right_value = initial if postfix else updated
                                returned = int(bool(right_value)) if selected else int(left)
                                program = memory_return_program(generated.initial_required, initial, returned,
                                                                updated if selected else initial, int(selected))
                                compile_run(self, program, directory)

    def test_ternary_memory_arms_are_lazy_including_nested_choices(self):
        for memory_then in (False, True):
            for condition in (False, True):
                for postfix in (False, True):
                    for nested in (False, True):
                        with self.subTest(memory_then=memory_then, condition=condition, postfix=postfix, nested=nested), tempfile.TemporaryDirectory() as directory:
                            memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                            target = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                            target.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                            update = behav.UnaryOperation(behav.Operator('--'), target, postfix=postfix)
                            update.ty = target.ty
                            constant = behav.Literal(42, target.ty)
                            arms = (update, constant) if memory_then else (constant, update)
                            expression = behav.Ternary(behav.Literal(int(condition), target.ty), *arms)
                            if nested:
                                expression = behav.Ternary(behav.Literal(1, target.ty), expression, constant)
                            trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                                 0, type_info.TypeKind.VOID, [], None, extern=True)
                            generated = InstructionTransformVisitor().generate(behav.Operation([behav.Return(expression)]),
                                                                              context({'M': memory}, {'trap': trap}))
                            selected = condition == memory_then
                            returned = (5 if postfix else 4) if selected else 42
                            program = memory_return_program(generated.initial_required, 5, returned,
                                                            4 if selected else 5, int(selected))
                            compile_run(self, program, directory)

    def test_memory_condition_writeback_and_lazy_else_if(self):
        cases = [
            (None, 0, True, 2, 255, 1),
            (None, 2, True, 1, 1, 1),
            (None, 0, False, 1, 255, 1),
            (1, 2, True, 1, 2, 0),
            (0, 2, True, 2, 1, 1),
            (0, 0, True, 3, 255, 1),
        ]
        for leading, initial, postfix, selected, stored, accesses in cases:
            with self.subTest(leading=leading, initial=initial, postfix=postfix), tempfile.TemporaryDirectory() as directory:
                memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                target = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                target.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                condition = behav.UnaryOperation(behav.Operator('--'), target, postfix=postfix)
                condition.ty = target.ty
                conditions = [condition, behav.CodeLiteral('1')] if leading is None else [behav.CodeLiteral(str(leading)), condition]
                branches = [[behav.CodeLiteral('selected=1;')], [behav.CodeLiteral('selected=2;')],
                            [behav.CodeLiteral('selected=3;')]]
                trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                     0, type_info.TypeKind.VOID, [], None, extern=True)
                generated = InstructionTransformVisitor().generate(behav.Operation([behav.Conditional(conditions, branches)]),
                                                                  context({'M': memory}, {'trap': trap}))
                program = '''
int addresses=0,reads=0,writes=0;etiss_uint8 value=INITIAL;
int next_address(){++addresses;return 7;}
struct CPU{int exception=0;};
int read(void*,CPU*,int address,etiss_uint8* out,int count){++reads;if(address!=7||count!=1)return 1;*out=value;return 0;}
int write(void*,CPU*,int address,etiss_uint8* in,int count){++writes;if(address!=7||count!=1)return 1;value=*in;return 0;}
struct System{void* handle=nullptr;decltype(&read) dread=read;decltype(&write) dwrite=write;};
void trap(int){throw 1;}
int main(){int selected=0;CPU c;CPU* cpu=&c;System s;System* system=&s;
'''.replace('INITIAL', str(initial)) + generated.initial_required + '\n'
                program += ('return selected==' + str(selected) + '&&value==' + str(stored) +
                            '&&addresses==' + str(accesses) + '&&reads==' + str(accesses) +
                            '&&writes==' + str(accesses) + '?0:1;}')
                compile_run(self, program, directory)

    def test_memory_loop_tests_write_back_final_false_condition(self):
        for post_test in (False, True):
            for postfix in (False, True):
                for nested_loop in (False, True):
                    with self.subTest(post_test=post_test, postfix=postfix, nested_loop=nested_loop), tempfile.TemporaryDirectory() as directory:
                        memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                        target = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                        target.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                        condition = behav.UnaryOperation(behav.Operator('--'), target, postfix=postfix)
                        condition.ty = target.ty
                        body = [behav.CodeLiteral('int scoped = 0; ++count;')]
                        if nested_loop:
                            body += [behav.CodeLiteral('int inner=0;'),
                                     behav.Loop(behav.CodeLiteral('inner++<1'), [behav.Continue()], False)]
                        body.append(behav.Continue())
                        trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                             0, type_info.TypeKind.VOID, [], None, extern=True)
                        generated = InstructionTransformVisitor().generate(
                            behav.Operation([behav.Loop(condition, body, post_test)]),
                            context({'M': memory}, {'trap': trap}))
                        evaluations = 3 if postfix else 2
                        iterations = evaluations if post_test else evaluations - 1
                        stored = 255 if postfix else 0
                        program = '''
int addresses=0,reads=0,writes=0;etiss_uint8 value=2;
int next_address(){++addresses;return 7;}
struct CPU{int exception=0;};
int read(void*,CPU*,int address,etiss_uint8* out,int count){++reads;if(address!=7||count!=1)return 1;*out=value;return 0;}
int write(void*,CPU*,int address,etiss_uint8* in,int count){++writes;if(address!=7||count!=1)return 1;value=*in;return 0;}
struct System{void* handle=nullptr;decltype(&read) dread=read;decltype(&write) dwrite=write;};
void trap(int){throw 1;}
int main(){int count=0;CPU c;CPU* cpu=&c;System s;System* system=&s;
''' + generated.initial_required + '\n'
                        program += ('return value==' + str(stored) + '&&count==' + str(iterations) +
                                    '&&addresses==' + str(evaluations) + '&&reads==' + str(evaluations) +
                                    '&&writes==' + str(evaluations) + '?0:1;}')
                        compile_run(self, program, directory)

    def test_coredsl_prefix_and_postfix_values(self):
        from m2isar.backends.coredsl2.visitor import CDSLWriterVisitor
        for body, expected in CASES[5:9]:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                model, _ = helpers.parse_model(helpers.source(body, 'int'), directory, validated=True)
                writer = helpers.CWriter()
                CDSLWriterVisitor().generate(model.cores['C'].functions['f'].operation, writer)
                compile_run(self, 'int f(){\n' + ''.join(writer.parts) + '\n}\n'
                            'int main(){return f()==' + str(expected) + '?0:1;}', directory)

    def test_etiss_scalar_and_slice_values(self):
        for body, expected in CASES:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                model, _ = helpers.parse_model(helpers.source(body, 'int'), directory, validated=True)
                generated = InstructionTransformVisitor().generate(model.cores['C'].functions['f'].operation, context())
                compile_run(self, 'int f(){\n' + generated.initial_required + '\n}\n'
                            'int main(){return f()==' + str(expected) + '?0:1;}', directory)

    def test_memory_expression_return_values_and_read_failure(self):
        for return_expression in (False, True):
            for read_failure in (False, True):
                for operator, postfix, initial, expected in [('++', False, 5, 6), ('++', True, 5, 6),
                                                             ('--', False, 0, 255), ('--', True, 0, 255)]:
                    with self.subTest(return_expression=return_expression, read_failure=read_failure,
                                      operator=operator, postfix=postfix), tempfile.TemporaryDirectory() as directory:
                        memory = arch.Memory('M', type_info.TypeKind.UINT, 8, 256, {ai.MemoryAttribute.IS_MAIN_MEM: []})
                        target = behav.IndexedReference(memory, behav.CodeLiteral('next_address()'))
                        target.ty = type_info.PrimitiveType(type_info.TypeKind.UINT, 8)
                        node = behav.UnaryOperation(behav.Operator(operator), target, postfix=postfix)
                        node.ty = target.ty
                        result = behav.NamedReference(arch.Variable('result', target.ty))
                        result.ty = target.ty
                        statement = behav.Return(node) if return_expression else behav.Assignment(result, node)
                        trap = arch.Function('trap', {ai.FunctionAttribute.ETISS_TRAP_TRANSLATE_FN: []},
                                             0, type_info.TypeKind.VOID, [], None, extern=True)
                        generated = InstructionTransformVisitor().generate(behav.Operation([statement]),
                                                                          context({'M': memory}, {'trap': trap}))
                        program = '''
int addresses=0,reads=0,writes=0;etiss_uint8 value=INITIAL;
int next_address(){++addresses;return 7;}
struct CPU{int exception=0;};
int read(void*,CPU*,int address,etiss_uint8* out,int count){++reads;if(address!=7||count!=1)return 1;*out=value;return FAILURE;}
int write(void*,CPU*,int address,etiss_uint8* in,int count){++writes;if(address!=7||count!=1)return 1;value=*in;return 0;}
struct System{void* handle=nullptr;decltype(&read) dread=read;decltype(&write) dwrite=write;};
void trap(int){throw 1;}
int f(){etiss_uint8 result=0;CPU c;CPU* cpu=&c;System s;System* system=&s;
'''.replace('INITIAL', str(initial)).replace('FAILURE', str(int(read_failure)))
                        program += generated.initial_required + '\nreturn result;\n}\n'
                        program += 'int main(){int result=0;bool trapped=false;try{result=f();}catch(int){trapped=true;}\n'
                        returned = 0 if read_failure else initial if postfix else expected
                        stored = initial if read_failure else expected
                        program += ('return value==' + str(stored) + '&&result==' + str(returned) +
                                    '&&trapped==' + str(int(read_failure)) + '&&addresses==1&&reads==1&&writes==' +
                                    str(int(not read_failure)) + '?0:1;}')
                        compile_run(self, program, directory)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class IncrementOracleTest(unittest.TestCase):
    probe = oracle_helpers.IsaAliasOracleTest.probe

    def test_release_accepts_scalar_and_slice_programs(self):
        for body, _ in CASES:
            with self.subTest(body=body):
                output, _ = self.probe(helpers.source(body, 'int'))
                self.assertNotIn('ERROR:', output)
