"""Check local binding identities after source validation and model lowering."""
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from m2isar.frontends.coredsl2.behavior_model_builder import BehaviorModelBuilder
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
from m2isar.backends.etiss.instruction_utils import TransformerContext
from m2isar.metamodel import load_model
from m2isar.metamodel import arch, type_info


class LocalScopeLoweringTest(unittest.TestCase):
    def lower(self, statements):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scope.core_desc'
            path.write_text('Core C { functions { int f() { ' + statements + ' } } }')
            tree = make_parser(path).description_content()
            validate_source(tree, None)
            builder = BehaviorModelBuilder({}, {}, {}, {}, {}, {}, {}, set())
            function = tree.definitions[0].sections[0].functions[0]
            block = builder.visit(function.behavior)
            self.assertEqual(builder._vars, {})
            self.assertEqual(len(builder._all_vars), len({id(v) for v in builder._all_vars.values()}))
            self.assertTrue(all(name == var.name for name, var in builder._all_vars.items()))
            return block.statements

    def test_inner_initializer_and_block_exit(self):
        statements = self.lower('int x=1; { int x=x; x=2; } return x;')
        outer = statements[0].target.var
        inner_block = statements[1].statements
        inner = inner_block[0].target.var
        self.assertIsNot(inner, outer)
        self.assertNotEqual(inner.name, outer.name)
        self.assertIs(inner_block[0].expr.reference, outer)
        self.assertIs(inner_block[1].target.reference, inner)
        self.assertIs(statements[2].expr.reference, outer)

    def test_same_block_redeclaration_and_multiple_declarators(self):
        statements = self.lower('int x=1; int x=x, y=x; return y;')
        previous = statements[0].target.var
        current = statements[1].target.var
        self.assertIs(statements[1].expr.reference, previous)
        self.assertIs(statements[2].expr.reference, current)
        self.assertIs(statements[3].expr.reference, statements[2].target.var)

    def test_for_initializer_restores_outer_binding(self):
        statements = self.lower('int x=1; for (int x=x; x<3; x+=1) { x=2; } return x;')
        outer = statements[0].target.var
        loop = statements[1]
        loop_local = loop.init[0].target.var
        self.assertIs(loop.init[0].expr.reference, outer)
        self.assertIs(loop.cond.left.reference, loop_local)
        self.assertIs(statements[2].expr.reference, outer)

    def test_declarators_keep_independent_types(self):
        statements = self.lower('unsigned<8> x, y=1; return y;')
        for declaration in statements[:2]:
            self.assertEqual(declaration.target.var.ty.kind, type_info.TypeKind.UINT)
            self.assertEqual(declaration.target.var.ty.size, 8)
        self.assertIsNot(statements[0].target.var.ty, statements[1].target.var.ty)
        statements = self.lower('unsigned<8> a[2], b[3], c; return c;')
        first, second, scalar = [stmt.target.var.ty for stmt in statements[:3]]
        self.assertIsInstance(first, type_info.ArrayType)
        self.assertIsInstance(second, type_info.ArrayType)
        self.assertIsInstance(scalar, type_info.PrimitiveType)
        self.assertEqual(arch.get_const_or_val(first.length), 2)
        self.assertEqual(arch.get_const_or_val(second.length), 3)
        self.assertEqual(first.element_type.kind, type_info.TypeKind.UINT)
        self.assertEqual(second.element_type.kind, type_info.TypeKind.UINT)
        self.assertEqual(scalar.kind, type_info.TypeKind.UINT)

    def test_emitted_declarations_use_distinct_names(self):
        statements = self.lower('int x=1; int x=x; int x_2=x; return x_2;')
        variables = [stmt.target.var for stmt in statements[:3]]
        self.assertEqual([var.name for var in variables], ['x', 'x_2', 'x_2_2'])
        visitor = InstructionTransformVisitor()
        context = TransformerContext({}, {}, {}, {}, {}, {}, [], {}, 32, 32,
                                     'C', False, {}, False)
        for index, statement in enumerate(statements[:3]):
            declaration = visitor.generate(statement.target, context).code
            self.assertIn(' ' + variables[index].name, declaration)
            if index:
                initializer = visitor.generate(statement.expr, context).code
                self.assertEqual(initializer, variables[index - 1].name)

    def test_cli_roundtrip_keeps_all_local_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'scope.core_desc'
            path.write_text('Core C { functions { int f() { int x=1; '
                            '{ int x=x; x=2; } return x; } } }')
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser',
                                     str(path), '--validate'], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            model = load_model(Path(directory) / 'gen_model' / 'scope.m2isarmodel')
            function = model.cores['C'].functions['f']
            self.assertEqual(set(function.vars), {'x', 'x_2'})
            statements = function.operation.statements[0].statements
            self.assertIs(statements[0].target.var, function.vars['x'])
            self.assertIs(statements[1].statements[0].target.var, function.vars['x_2'])
            self.assertIs(statements[1].statements[0].expr.reference, function.vars['x'])


if __name__ == '__main__':
    unittest.main()
