"""ETISS concatenations widen narrow operands before shifting in C."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
from m2isar.metamodel import behav, type_info


@unittest.skipUnless(shutil.which('cc'), 'C compiler required')
class EtissConcatTest(unittest.TestCase):
    def test_narrow_casts_shift_in_result_width(self):
        cases = [
            # The RV64 MISA read that regressed in rv64mi-p-mcsr.
            (2, 2, 62, 0x14112d, 0x800000000014112d, False),
            (1, 2, 30, 0x14112d, 0x4014112d, False),
            (0xff, 8, 56, 1, 0xff00000000000001, False),
            (-1, 8, 56, 1, 0xff00000000000001, True),
            (2, 2, 126, 1, (2 << 126) | 1, False),
        ]
        checks = []
        for value, left_width, right_width, right_value, expected, signed in cases:
            kind = type_info.TypeKind.INT if signed else type_info.TypeKind.UINT
            left = behav.TypeConv(kind, left_width, behav.Literal(
                value, type_info.PrimitiveType(kind, 64)))
            right = behav.Literal(right_value, type_info.PrimitiveType(
                type_info.TypeKind.UINT, right_width))
            expression = behav.ConcatOperation(left, right)
            generated = InstructionTransformVisitor().generate(expression, None)
            self.assertEqual(generated.size, left_width + right_width)
            expected_c = (f'(((etiss_uint128){expected >> 64}ULL << 64)'
                          f' | {expected & ((1 << 64) - 1)}ULL)')
            checks.append(f'if ((etiss_uint128)({generated.code}) != {expected_c}) return {len(checks) + 1};')

        source = '''#include <stdint.h>
typedef uint8_t etiss_uint8;
typedef int8_t etiss_int8;
typedef uint32_t etiss_uint32;
typedef uint64_t etiss_uint64;
typedef unsigned __int128 etiss_uint128;
int main(void) {
''' + '\n'.join(checks) + '\nreturn 0;\n}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'concat.c'
            path.write_text(source)
            executable = Path(directory) / 'concat'
            compiled = subprocess.run(
                ['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                 '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
                 str(path), '-o', str(executable)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(compiled.returncode, 0, compiled.stdout)
            executed = subprocess.run([str(executable)], text=True,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(executed.returncode, 0, executed.stdout)
