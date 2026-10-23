"""Representative models for Spike plugin generation and execution."""
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from m2isar.metamodel import arch as a, behav as b
from m2isar.metamodel.type_info import TypeKind
from m2isar.metamodel.attribute_info import RegisterAttribute
from m2isar.backends.spike.plugin import Unsupported, generate_plugin


def example_set():
    x = a.RegisterBank('X', 32, TypeKind.UINT, 32, {RegisterAttribute.IS_MAIN_REG: []})
    acc = a.RegisterBank('ACC', 4, TypeKind.UINT, 32, {})
    insns = {}
    for funct, kind in enumerate(['add', 'sub', 'xor', 'and', 'or', 'set', 'get', 'accumulate']):
        enc = [a.BitVal(7, funct), a.BitField('rs2', a.RangeSpec(5), TypeKind.UINT),
               a.BitField('rs1', a.RangeSpec(5), TypeKind.UINT), a.BitVal(3, 0),
               a.BitField('rd', a.RangeSpec(5), TypeKind.UINT), a.BitVal(7, 0x0b)]
        insn = a.Instruction(kind, {}, enc, None, None, None, None)
        field = lambda key: b.NamedReference(insn.fields[key])
        reg = lambda key: b.IndexedReference(x, field(key))
        state = b.IndexedReference(acc, b.Literal(0))
        target = reg('rd')
        if funct < 5:
            value = b.BinaryOperation(reg('rs1'), b.Operator(['+', '-', '^', '&', '|'][funct]), reg('rs2'))
        elif kind == 'set':
            target, value = state, reg('rs1')
        elif kind == 'get':
            value = state
        else:
            target, value = state, b.BinaryOperation(state, b.Operator('+'), reg('rs1'))
        insn.operation = b.Operation([b.Assignment(target, value)])
        insns[(insn.code, insn.mask)] = insn
    return a.InstructionSet('Example', [], {}, {}, {}, {'X': x, 'ACC': acc}, {}, {}, insns)


class PluginTests(unittest.TestCase):
    def test_coredsl_cli_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(Path(__file__).parent / 'fixtures' / 'spike.core_desc', root)
            for module, input_path in [
                ('m2isar.frontends.coredsl2.parser', root / 'spike.core_desc'),
                ('m2isar.backends.spike.writer', root / 'gen_model' / 'spike.m2isarmodel'),
            ]:
                result = subprocess.run([sys.executable, '-m', module, str(input_path)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn('skipping instruction', result.stderr)
            source = (root / 'gen_output' / 'spike' / 'Example' / 'extension.cc').read_text()
            self.assertEqual(source.count('static reg_t m2_'), 8)
            self.assertTrue((root / 'gen_output' / 'spike' / 'Example' / 'Makefile').exists())

    def test_representative_instructions(self):
        source = generate_plugin(example_set())
        for name in ['add', 'sub', 'xor', 'and', 'or', 'set', 'get', 'accumulate']:
            self.assertIn('static reg_t m2_' + name, source)
        self.assertIn('return new m2_Example', source)
        self.assertIn('m2_ACC.fill(0)', source)
        self.assertIn('XPR.write', source)

    def test_rv64_model_and_initial_value(self):
        model = example_set()
        model.register_banks['X'].ty.element_type.size = 64
        model.register_banks['ACC'].ty.element_type.size = 64
        model.register_banks['ACC']._initval[1] = 0xfedcba9876543210
        source = generate_plugin(model)
        self.assertIn('static constexpr unsigned xlen = 64;', source)
        self.assertIn('std::array<uint64_t, 4>', source)
        self.assertIn('UINT64_C(18364758544493064720)', source)
        self.assertIn('uint64_t(read_x(p, m2_rs1))', source)

    def test_unsupported_register_width_fails(self):
        model = example_set()
        model.register_banks['X'].ty.element_type.size = 128
        with self.assertRaisesRegex(Unsupported, '32- or 64-bit width'):
            generate_plugin(model)

    def test_unsupported_encoding_warns_and_skips(self):
        model = example_set()
        insn = next(iter(model.instructions.values()))
        insn._size = 16
        with self.assertLogs('m2isar.backends.spike.plugin', logging.WARNING) as logs:
            source = generate_plugin(model)
        self.assertIn('skipping instruction add', logs.output[0])
        self.assertNotIn('static reg_t m2_add(', source)
        self.assertIn('static reg_t m2_sub(', source)

    def test_unsupported_operand_warns(self):
        model = example_set()
        first = next(iter(model.instructions.values()))
        first.fields['rd'].ty.size = 33
        with self.assertLogs('m2isar.backends.spike.plugin', logging.WARNING) as logs:
            source = generate_plugin(model)
        self.assertIn('operand rd: requires 1..32 bits', logs.output[0])
        self.assertNotIn('static reg_t m2_add(', source)

    def test_overlapping_encoding_warns(self):
        model = example_set()
        broad = a.Instruction('broad', {},
                              [a.BitField('payload', a.RangeSpec(25), TypeKind.UINT), a.BitVal(7, 0xb)],
                              None, None, None, None)
        model.instructions[(broad.code, broad.mask)] = broad
        with self.assertLogs('m2isar.backends.spike.plugin', logging.WARNING) as logs:
            generate_plugin(model)
        self.assertIn('overlaps', logs.output[0])

    def test_duplicate_names_warn(self):
        model = example_set()
        list(model.instructions.values())[1].name = 'add'
        with self.assertLogs('m2isar.backends.spike.plugin', logging.WARNING) as logs:
            source = generate_plugin(model)
        self.assertIn('duplicate instruction name', logs.output[0])
        self.assertEqual(source.count('static reg_t m2_add('), 1)

    def test_unsupported_behavior_warns(self):
        model = example_set()
        next(iter(model.instructions.values())).operation = b.Operation([b.CodeLiteral('unsafe();')])
        with self.assertLogs('m2isar.backends.spike.plugin', logging.WARNING) as logs:
            generate_plugin(model)
        self.assertIn('CodeLiteral', logs.output[0])


if __name__ == '__main__':
    unittest.main()
