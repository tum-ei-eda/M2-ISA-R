"""Default frontend inference simplifies logical-not expressions in functions."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from m2isar.metamodel import behav, load_model, type_info


class UnaryNotInferenceTest(unittest.TestCase):
    def test_unary_not_in_core_and_instruction_set_functions(self):
        for frontend, root, collection, name in (
                ('coredsl2', 'Core', 'cores', 'C'),
                ('coredsl2_set', 'InstructionSet', 'sets', 'I')):
            with self.subTest(root=root), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'unary_not.core_desc'
                source.write_text(
                    root + ' ' + name + ' { functions { int f() { return !0; } } }')
                parsed = subprocess.run(
                    [sys.executable, '-m', f'm2isar.frontends.{frontend}.parser', str(source)],
                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)

                model = load_model(Path(directory) / 'gen_model' / 'unary_not.m2isarmodel')
                definition = getattr(model, collection)[name]
                result = definition.functions['f'].operation.statements[0].statements[0].expr
                self.assertIsInstance(result, behav.Literal)
                self.assertEqual(result.value, 1)
                self.assertEqual(result.ty.kind, type_info.TypeKind.UINT)
                self.assertEqual(result.ty.size, 1)
