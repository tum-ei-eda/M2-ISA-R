"""Architectural initializers retain validation and constant cast semantics."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.metamodel import load_model
from m2isar.backends.etiss.architecture_writer import write_arch_cpp


class ArchitecturalInitializerTest(unittest.TestCase):
    def run_parser(self, directory, state, *flags, set_parser=False):
        source = Path(directory) / 'initializers.core_desc'
        kind = 'InstructionSet' if set_parser else 'Core'
        source.write_text(f'{kind} C {{ architectural_state {{ {state} }} }}')
        module = 'm2isar.frontends.coredsl2_set.parser' if set_parser else 'm2isar.frontends.coredsl2.parser'
        result = subprocess.run([sys.executable, '-m', module, str(source), '--output', directory, *flags],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return result, Path(directory) / 'initializers.m2isarmodel'

    def test_explicit_cast_values(self):
        cases = [
            ('(unsigned<W>)(signed<W>)(-1)', 255),
            ('(signed<8>)255', -1),
            ('(unsigned<4>)31', 15),
            ('(unsigned)(signed<8>)(-1)', 255),
            ('(unsigned<8>)(1 + 2)', 3),
        ]
        for expression, expected in cases:
            for validate in (False, True):
                with self.subTest(expression=expression, validate=validate), tempfile.TemporaryDirectory() as directory:
                    flags = ('--validate',) if validate else ()
                    result, path = self.run_parser(directory, f'int W=8; register unsigned<8> R={expression};', *flags)
                    # The signed cast result cannot be assigned to an unsigned register.
                    if expression == '(signed<8>)255' and validate:
                        self.assertEqual(result.returncode, 1, result.stdout)
                        self.assertIn('InvalidAssignmentType', result.stdout)
                    else:
                        self.assertEqual(result.returncode, 0, result.stdout)
                        self.assertEqual(load_model(path).cores['C'].register_banks['R']._initval[None], expected)
                    self.assertNotIn('Traceback', result.stdout)

    def test_scalar_initializer_validation_in_source_and_saved_model(self):
        for state in ('register unsigned<8> R=-1;', 'unsigned<8> P=256;',
                      'unsigned<8> P; P=-1;'):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as directory:
                result, path = self.run_parser(directory, state, '--validate')
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('InvalidAssignmentType', result.stdout)
                result, path = self.run_parser(directory, state)
                self.assertEqual(result.returncode, 0, result.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(path)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertIn('InvalidAssignmentType', result.stdout)
                self.assertNotIn('Traceback', result.stdout)

    def test_list_initializers(self):
        for values, expected in (('(unsigned<8>)(-1), 2', None), ('256, 2', 'Cannot implicitly convert'),
                                 ('1', 'List initializer size does not match')):
            with self.subTest(values=values), tempfile.TemporaryDirectory() as directory:
                result, path = self.run_parser(directory, f'register unsigned<8> R[2]={{{values}}};')
                self.assertEqual(result.returncode, 0, result.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(path)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                self.assertEqual(result.returncode, int(expected is not None), result.stdout)
                if expected:
                    self.assertIn(expected, result.stdout)
                else:
                    self.assertEqual(load_model(path).cores['C'].register_banks['R']._initval, {0: 255, 1: 2})

    def test_set_cast_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _ = self.run_parser(directory, 'register unsigned<8> R=(unsigned<8>)(-1);',
                                        '--validate', set_parser=True)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_initializer_width_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            result, _ = self.run_parser(directory, "register unsigned<16> R=8'd1;",
                                        '--validate', '-Werror=implicit-extend')
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn('implicit-extend', result.stdout)
            self.assertNotIn('Traceback', result.stdout)

    def test_etiss_initializer_suffixes_follow_register_type(self):
        with tempfile.TemporaryDirectory() as directory:
            result, path = self.run_parser(directory, '''
                register unsigned<8> X[2];
                register unsigned<8> U=-1;
                register signed<8> S=1;
                register unsigned<8> A[2]={0, 1};
            ''')
            self.assertEqual(result.returncode, 0, result.stdout)
            write_arch_cpp(load_model(path).cores['C'], '', Path(directory))
            code = (Path(directory) / 'CArch.cpp').read_text()
            self.assertIn('->U = -1ULL;', code)
            self.assertIn('->S = 1LL;', code)
            self.assertIn('->A[0] = 0ULL;', code)


if __name__ == '__main__':
    unittest.main()
