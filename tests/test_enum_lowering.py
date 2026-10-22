"""Enums retain their resolved values and physical types through model lowering."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.metamodel import load_model
from m2isar.metamodel.type_info import TypeKind
from test_enum_inheritance import INHERITED


class EnumLoweringTest(unittest.TestCase):
    def test_inherited_enum_cli_and_model_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'independent.core_desc'
            path.write_text(INHERITED)
            result = subprocess.run([sys.executable, '-m',
                                     'm2isar.frontends.coredsl2.parser', str(path), '--validate'],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            core = load_model(Path(directory) / 'gen_model' / 'independent.m2isarmodel').cores['C']
            self.assertEqual(core.parameters['A'].value, 7)
            self.assertEqual(core.parameters['B'].value, 8)
            self.assertEqual(core.parameters['W'].value, 8)
            self.assertEqual((core.register_banks['R'].ty.size, core.register_banks['R'].ty.kind),
                             (4, TypeKind.UINT))

    def test_validated_cli_and_model_roundtrip(self):
        source = '''Core C {
          architectural_state {
            enum E { A = -1, B, D = 7, F }
            register enum E R;
            unsigned<4> W = F;
            register unsigned<W> X;
          }
          functions {
            enum E value() { enum E x = D; return x; }
            unsigned<4> width() { return bitsizeof(enum E); }
          }
        }'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'independent.core_desc'
            path.write_text(source)
            result = subprocess.run([sys.executable, '-m',
                                     'm2isar.frontends.coredsl2.parser', str(path), '--validate'],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            model = load_model(Path(directory) / 'gen_model' / 'independent.m2isarmodel')
            core = model.cores['C']
            self.assertEqual({name: core.parameters[name].value for name in ('A', 'B', 'D', 'F', 'W')},
                             {'A': -1, 'B': 0, 'D': 7, 'F': 8, 'W': 8})
            self.assertEqual(core.parameters['A']._coredsl_enum_name, 'E')
            self.assertEqual((core.parameters['A'].size, core.parameters['A'].signed), (5, True))
            self.assertEqual((core.register_banks['R'].ty.size, core.register_banks['R'].ty.kind),
                             (5, TypeKind.INT))
            self.assertEqual(core.register_banks['X'].ty.size, 8)


if __name__ == '__main__':
    unittest.main()
