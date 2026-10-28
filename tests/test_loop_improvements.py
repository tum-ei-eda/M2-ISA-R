"""Source loops retain their structure without losing existing backend semantics."""
from pathlib import Path
import tempfile
import unittest

from test_continue_regression import parse_model, source
from m2isar.backends.coredsl2.writer import write_cdsl_default
from m2isar.metamodel import behav, attribute_info as ai, arch, type_info
from m2isar.metamodel.utils.scalar_staticness import VarAccessVisitor
from m2isar.transforms.lower_loops import lower_loops


class LoopImprovementsTest(unittest.TestCase):
    def test_source_loop_kinds_and_increment_values_survive_lowering(self):
        with tempfile.TemporaryDirectory() as directory:
            model, _ = parse_model(source(
                'for(int i=0;i<3;i++){if(i==1)continue;}'
                'while(0){continue;}do{break;}while(0);'), directory, validated=True)
            loops = model.cores['C'].functions['f'].operation.statements[0].statements
            self.assertEqual([type(loop) for loop in loops],
                             [behav.ForLoop, behav.WhileLoop, behav.DoWhileLoop])
            update = loops[0].updates[0]
            self.assertIsInstance(update, behav.UnaryOperation)
            self.assertTrue(update.postfix)
            lower_loops(model)
            lowered = model.cores['C'].functions['f'].operation.statements[0].statements
            self.assertTrue(all(type(loop) is behav.Loop for loop in lowered))
            self.assertIs(lowered[0].updates[0], update)

    def test_attributed_blocks_and_multiple_initializers_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            model, _ = parse_model(source(
                'for(int i=0,j=0;i<3;i++,j++){ [[access=STATIC]] '
                'if(i==1)continue;}for(;;){break;}'), directory, validated=True)
            out = Path(directory) / 'roundtrip.core_desc'
            write_cdsl_default(model, out, writer_kwargs={'reduced': False})
            emitted = out.read_text()
            self.assertIn('[[access=STATIC]]', emitted)
            self.assertIn('i++', emitted)
            parsed, _ = parse_model(emitted, directory, validated=True)
            self.assertIn('f', parsed.cores['C'].functions)

    def test_runtime_continue_demotes_for_iterator_and_body(self):
        ty = type_info.PrimitiveType(type_info.TypeKind.INT, 32)
        iterator = arch.Variable('i', ty)
        init = behav.Assignment(behav.VarDefinition(iterator), behav.Literal(0))
        runtime_condition = behav.NamedReference(arch.Variable(
            'runtime_condition', ty, attributes={'static': ai.AccessAttribute.NONE}))
        loop = behav.ForLoop([init], behav.Literal(1), [], behav.Block([
            behav.Conditional([runtime_condition], [behav.Block([behav.Continue()])])]))
        access = VarAccessVisitor().generate(loop, ai.AccessContext())
        self.assertEqual(access, ai.AccessAttribute.NONE)
        self.assertEqual(iterator.attributes['static'], ai.AccessAttribute.NONE)
        self.assertEqual(loop.body.attributes[ai.BlockAttribute.ACCESS], ai.AccessAttribute.NONE)
