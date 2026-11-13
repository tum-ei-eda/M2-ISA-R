"""Constant folding preserves CDSL shift width semantics and diagnostics."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.metamodel import load_model, behav


class ConstantFoldingTest(unittest.TestCase):
    def test_shift_uses_left_width_and_warns_before_fold(self):
        source = '''Core C {
            functions {
                void f() {
                    unsigned<32> rv32 = 1 << 31;
                    unsigned<32> explicit_width = 32'b1 << 31;
                }
            }
        }'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'shift.core_desc'
            path.write_text(source)
            result = subprocess.run(
                [sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn('Shift count overflow for << operation (1 vs. 31)', result.stdout)
            self.assertIn('shift-overflow', result.stdout)
            self.assertIn('shift.core_desc:4', result.stdout)

            model = load_model(Path(directory) / 'gen_model' / 'shift.m2isarmodel')
            statements = model.cores['C'].functions['f'].operation.statements[0].statements
            rv32, explicit_width = (statement.expr for statement in statements)
            self.assertIsInstance(rv32, behav.Literal)
            self.assertIsInstance(explicit_width, behav.Literal)
            self.assertEqual(rv32.value, 0)
            self.assertEqual(explicit_width.value, 1 << 31)
            self.assertEqual(rv32.ty.size, 1)
            self.assertEqual(explicit_width.ty.size, 32)


if __name__ == '__main__':
    unittest.main()
