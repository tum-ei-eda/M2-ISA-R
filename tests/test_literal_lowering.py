"""Lowered literals retain release values, widths and signedness."""
from pathlib import Path
import tempfile
import unittest

from m2isar.frontends.coredsl2.architecture_model_builder import ArchitectureModelBuilder
from m2isar.frontends.coredsl2.behavior_model_builder import BehaviorModelBuilder
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.metamodel.type_info import TypeKind
from m2isar.diagnostics import M2ValidationError


class LiteralLoweringTest(unittest.TestCase):
    def expression(self, text, directory):
        path = Path(directory) / 'literal.core_desc'
        path.write_text('Core C { architectural_state { int N = ' + text + '; } }')
        return make_parser(path).description_content().definitions[0].sections[0].declarations[0].declarations[0].init.expr

    def test_both_builders(self):
        cases = [('0', 0, 1, TypeKind.UINT), ('0x0001', 1, 1, TypeKind.UINT),
                 ('077', 63, 6, TypeKind.UINT), ("8'shff", -1, 8, TypeKind.INT),
                 ("8'sh7f", 127, 8, TypeKind.INT), ("8'hff", 255, 8, TypeKind.UINT)]
        builders = [ArchitectureModelBuilder(), BehaviorModelBuilder({}, {}, {}, {}, {}, {}, {}, set())]
        with tempfile.TemporaryDirectory() as directory:
            for text, value, width, kind in cases:
                for builder in builders:
                    with self.subTest(text=text, builder=type(builder).__name__):
                        literal = builder.visit(self.expression(text, directory))
                        self.assertEqual((literal.value, literal.ty.size, literal.ty.kind), (value, width, kind))

    def test_overflow_has_shared_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            for builder in [ArchitectureModelBuilder(), BehaviorModelBuilder({}, {}, {}, {}, {}, {}, {}, set())]:
                with self.subTest(builder=type(builder).__name__):
                    with self.assertRaises(M2ValidationError) as exc:
                        builder.visit(self.expression("3'hf", directory))
                    self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax')
