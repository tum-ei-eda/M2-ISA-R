"""Compile-time instruction enable attributes are resolved from parameters."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.metamodel import load_model


class InstructionEnableTest(unittest.TestCase):
    def test_parameterized_enable_selects_only_matching_encoding(self):
        for xlen in (32, 64):
            with self.subTest(xlen=xlen), tempfile.TemporaryDirectory() as directory:
                self._assert_enabled_instruction(directory, xlen)

    def _assert_enabled_instruction(self, directory, xlen):
        source = '''Core C {
    architectural_state { unsigned int XLEN = REPLACE_XLEN; }
    instructions {
        RV32_ONLY [[enable=XLEN==32]] {
            encoding: 8'h00;
            behavior: {}
        }
        RV64_ONLY [[enable=XLEN==64]] {
            encoding: 8'h00;
            behavior: {}
        }
    }
}'''.replace('REPLACE_XLEN', str(xlen))
        path = Path(directory) / 'enable.core_desc'
        path.write_text(source)
        result = subprocess.run(
            [sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path), '--output', directory],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        model = load_model(Path(directory) / 'enable.m2isarmodel')
        expected = 'RV32_ONLY' if xlen == 32 else 'RV64_ONLY'
        self.assertEqual({instr.name for instr in model.cores['C'].instructions.values()}, {expected})


if __name__ == '__main__':
    unittest.main()
