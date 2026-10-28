"""Instruction-set CLI uses source validation and command-line parameter values."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo
from m2isar.diagnostics import M2ValidationError


class SetSourceValidationTest(unittest.TestCase):
    def run_cli(self, source, *flags):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'set.core_desc'
            path.write_text(source)
            return subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2_set.parser',
                                   str(path), '--validate', '--output', directory, *flags],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)

    def test_source_error_before_lowering(self):
        result = self.run_cli('InstructionSet A { functions { void f() { break; } } }')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('com.minres.coredsl.StrayControlFlowStatement', result.stdout)
        self.assertNotIn('Traceback', result.stdout)

    def test_define_used_for_type_validation(self):
        result = self.run_cli('InstructionSet A { architectural_state { int W = 8; register unsigned<W> R; } }', '-DW=0')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('com.minres.coredsl.InvalidIntegerTypeSize', result.stdout)
        self.assertNotIn('Traceback', result.stdout)

    def test_override_resolves_unassigned_parameter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'set.core_desc'
            path.write_text('InstructionSet A { architectural_state { int W; register unsigned<W> R; } }')
            tree = make_parser(path).description_content()
            validate_source(tree, WarningsInfo(), parameter_values={'W': 8})

    def test_promoted_metamodel_warning_is_clean(self):
        source = """InstructionSet A {
          architectural_state { register unsigned<16> R; register unsigned<8> S; }
          instructions { I { encoding: 8'h00; behavior: { R = S; } } }
        }"""
        result = self.run_cli(source, '-Werror=implicit-extend')
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn('implicit-extend', result.stdout)
        self.assertNotIn('Traceback', result.stdout)

    def test_supplied_core_parameter_is_assigned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'core.core_desc'
            path.write_text('Core C { architectural_state { int W; } }')
            tree = make_parser(path).description_content()
            for value in (0, 8):
                with self.subTest(value=value):
                    validate_source(tree, WarningsInfo(), parameter_values={'W': value})
            with self.assertRaises(M2ValidationError) as exc:
                validate_source(tree, WarningsInfo())
            self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.UnassignedIsaParameter')
