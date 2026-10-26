"""Coverage reporting must retain instruction source metadata from parsing."""
from pathlib import Path
import os
import pickle
import subprocess
import sys
import tempfile
import unittest


class CoverageTests(unittest.TestCase):
    def test_parsed_instruction_function_coverage(self):
        repository = Path(__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=str(repository))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Coverage.core_desc"
            source.write_text("""Core Coverage {
    instructions {
        NOP {
            encoding: 32'h13;
            behavior: {}
        }
    }
}
""")

            def run_module(module, *args):
                result = subprocess.run(
                    [sys.executable, "-m", module, *map(str, args)],
                    cwd=root, env=env, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            run_module("m2isar.frontends.coredsl2.parser", source)
            model_path = root / "gen_model/Coverage.m2isarmodel"
            model = pickle.loads(model_path.read_bytes())
            instruction = next(iter(model.cores["Coverage"].instructions.values()))
            info = instruction.function_info
            self.assertIsNotNone(info)
            self.assertEqual(info.fn_name, "instr_NOP_00000013:ffffffff")
            self.assertEqual((info.start_line_no, info.stop_line_no), (3, 6))
            self.assertEqual(Path(info.file_path), source)
            self.assertEqual(model.code_infos[info.id], info)

            counters = root / "lines.csv"
            counters.write_text(f"Coverage\nid;count\n{info.id};7\n")
            run_module("m2isar.backends.coverage.coverage_lcov", model_path,
                       counters, "--legacy", "-j", "1", "-o", "coverage.info")
            report = (root / "Coverage.coverage.info").read_text()
            self.assertIn(f"FN:3,{info.fn_name}\n", report)
            self.assertIn(f"FNDA:7,{info.fn_name}\n", report)
            self.assertIn("FNF:1\nFNH:1\n", report)
