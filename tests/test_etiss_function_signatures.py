"""ETISS function prototypes render pointer parameters as valid C types."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.backends.etiss.instruction_generator import generate_arg_str
from m2isar.metamodel import arch, type_info


def primitive(kind, size):
    return type_info.PrimitiveType(kind, size)


INT, UINT, VOID = type_info.TypeKind.INT, type_info.TypeKind.UINT, type_info.TypeKind.VOID

ARGS = (
    (primitive(UINT, 32), 'etiss_uint32 x'),
    (primitive(INT, 5), 'etiss_int8 x'),
    (type_info.PointerType(primitive(INT, 8)), 'etiss_int8* x'),
    (type_info.PointerType(primitive(UINT, 8)), 'etiss_uint8* x'),
    (type_info.PointerType(primitive(UINT, 32)), 'etiss_uint32* x'),
    (type_info.PointerType(primitive(INT, 12)), 'etiss_int16* x'),
    (type_info.PointerType(primitive(VOID, None)), 'void* x'),
)


class EtissFunctionSignatureTest(unittest.TestCase):
    def test_generate_arg_str(self):
        for ty, expected in ARGS:
            with self.subTest(ty=str(ty)):
                self.assertEqual(generate_arg_str(arch.FnParam('x', ty)), expected)

    def test_unnamed_pointer_arg(self):
        self.assertEqual(generate_arg_str(arch.FnParam(None, type_info.PointerType(primitive(UINT, 8)))),
                         'etiss_uint8*')

    def test_extern_prototypes_in_generated_header(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ext.core_desc'
            path.write_text('''Core C {
                architectural_state {
                    int XLEN=32; register unsigned<32> X[2]; register unsigned<32> PC [[is_pc]];
                }
                functions {
                    extern void print_str(char* msg);
                    extern unsigned<32> sum(unsigned<32>* values, signed<16>* other, void* opaque, unsigned<32> n);
                }
            }''')
            parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(parsed.returncode, 0, parsed.stdout)
            result = subprocess.run([sys.executable, '-m', 'm2isar.backends.etiss.writer',
                                     str(Path(directory) / 'gen_model' / 'ext.m2isarmodel')],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            header = '\n'.join(file.read_text() for file in (Path(directory) / 'gen_output').rglob('*Funcs.h'))
            self.assertIn('void print_str(etiss_int8* msg);', header)
            self.assertIn('etiss_uint32 sum(etiss_uint32* values, etiss_int16* other, void* opaque, etiss_uint32 n);',
                          header)
            self.assertNotIn('* 8', header)


if __name__ == '__main__':
    unittest.main()
