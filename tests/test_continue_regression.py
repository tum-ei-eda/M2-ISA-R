"""Continue scope survives folding; lowered loop updates retain execution semantics."""
import os
import pickle
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, load_model, type_info, attribute_info
from m2isar.metamodel.utils.control_flow import preserve_break_scope
from m2isar.transforms.validate_behav.validate import validate_behav
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager

SCOPE_CASES = [('continue;', True), ('if(0) continue;', True),
               ('if(1){}else continue;', True), ('while(0){continue;}', False),
               ('do{continue;}while(0);', False),
               ('while(1){if(0)continue;break;}', False)]
MIXED = [('if(0){continue;break;continue;}', ['continue','break','continue']),
         ('if(1){}else{break;continue;break;}', ['break','continue','break'])]
EXECUTION = [
    ('int n=0;for(int i=0;i<3;i+=1){if(i==1)continue;n+=1;}return n;', 2),
    ('int n=3;do{n=(int)(n+1);continue;}while(n<3);return n;', 4),
    ('int n=0;for(int i=0;i<3;i=(int)(i+1),n=(int)(n+1))continue;return n;', 3),
    ('int n=0;for(int i=0;i<3;i=(int)(i+1)){if(i==1)continue;n=(int)(n+1);}return n;', 2),
    ('int n=0;for(int i=0;i<3;i=(int)(i+1)){for(int j=0;j<2;j=(int)(j+1)){continue;}n=(int)(n+1);}return n;', 3),
    ('int n=0;for(int i=0;i<3;i=(int)(i+1)){while(n<1){n=(int)(n+1);continue;}if(i==1)continue;n=(int)(n+1);}return n;', 3),
]

def source(body, returns='void'):
    return 'Core C {functions {' + returns + ' f(){' + body + '}}}'

def parse_model(case, directory, validated=False):
    path = Path(directory) / 'continue.core_desc'
    path.write_text(case)
    command = [sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)]
    if validated:
        command.append('--validate')
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    saved = Path(directory) / 'gen_model' / 'continue.m2isarmodel'
    return load_model(saved), saved

class ContinueNativeTest(unittest.TestCase):
    def test_saved_scope_and_cli_diagnostics(self):
        for body, invalid in SCOPE_CASES:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                model, saved = parse_model(source(body), directory)
                if invalid:
                    with self.assertRaises(M2ValidationError) as caught:
                        validate_behav(model, None)
                    self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.StrayControlFlowStatement')
                else:
                    validate_behav(model, None)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, int(invalid), result.stdout + result.stderr)
                if invalid:
                    self.assertIn('Unexpected continue statement', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_mixed_order_after_folding(self):
        for body, expected in MIXED:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                model, _ = parse_model(source(body), directory)
                with self.assertRaises(M2ValidationError) as caught:
                    validate_behav(model, None)
                errors = [caught.exception, *caught.exception.related_diagnostics]
                self.assertEqual([e.args[0].split(' [', 1)[0] for e in errors],
                                 ['Unexpected ' + kind + ' statement' for kind in expected])

    def test_pickle_repeated_preservation_and_legacy(self):
        root = behav.Operation([behav.Continue(), behav.Break(), behav.Continue()])
        preserve_break_scope(root)
        root.statements.clear()
        root = pickle.loads(pickle.dumps(root))
        preserve_break_scope(root)
        self.assertEqual([kind for kind, _ in root._stray_control_flow_locations], ['continue','break','continue'])
        legacy = behav.Operation([])
        legacy._stray_break_locations = [None, None]
        preserve_break_scope(legacy)
        for operation, count in [(root, 3), (legacy, 2)]:
            with self.assertRaises(M2ValidationError) as caught:
                ValidateBehavVisitor().generate(operation, WarningsManager(None))
            self.assertEqual(len(caught.exception.related_diagnostics), count - 1)

    def test_loop_scope_restored_after_error(self):
        visitor, context = ValidateBehavVisitor(), WarningsManager(None)
        condition = behav.Literal(1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
        visitor.generate(behav.Loop(condition, [behav.Continue()], False), context)
        with self.assertRaises(M2ValidationError):
            visitor.generate(behav.Loop(condition, [behav.Return(None)], False), context)
        with self.assertRaises(M2ValidationError) as caught:
            visitor.generate(behav.Continue(), context)
        self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.StrayControlFlowStatement')

    def test_continue_traversal_and_emission(self):
        from m2isar.metamodel.utils.ExprVisitor import ExprVisitor
        from m2isar.metamodel.utils.ExprMutator import ExprMutator
        from m2isar.metamodel.utils.expr_simplifier import ExprSimplifierVisitor
        from m2isar.metamodel.utils.function_staticness import FunctionStaticnessVisitor
        from m2isar.metamodel.utils.function_throws import FunctionThrowsVisitor
        from m2isar.metamodel.utils.scalar_staticness import VarAccessVisitor
        from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
        from m2isar.backends.coredsl2.visitor import CDSLWriterVisitor
        class Visitor(ExprVisitor):
            def generate(self, expr, context=None): return self.default_visit(expr, context)
        class Mutator(ExprMutator):
            def generate(self, expr, context=None): return self.default_visit(expr, context)
        node = behav.Continue()
        self.assertIsNone(Visitor().generate(node))
        self.assertIs(Mutator().generate(node), node)
        self.assertIs(ExprSimplifierVisitor().generate(node, None), node)
        self.assertTrue(FunctionStaticnessVisitor().generate(node, None))
        self.assertEqual(FunctionThrowsVisitor().generate(node, None), attribute_info.FunctionThrows.NO)
        self.assertEqual(VarAccessVisitor().generate(node, None), attribute_info.AccessAttribute.READ)
        self.assertEqual(InstructionTransformVisitor().generate(node, None).code, 'continue;')
        lines = []
        CDSLWriterVisitor().generate(node, SimpleNamespace(write_line=lines.append))
        self.assertEqual(lines, ['continue;'])


class CWriter:
    def __init__(self): self.parts = []
    def write(self, text): self.parts.append(str(text))
    def write_line(self, text=''): self.write(str(text) + '\n')
    def enter_block(self): self.write('{\n')
    def leave_block(self, nl=True): self.write('}\n' if nl else '}')
    def write_type(self, type_): self.write('int')

@unittest.skipUnless(shutil.which('g++'), 'Install g++ for emitted loop execution tests')
class ContinueExecutionTest(unittest.TestCase):
    def test_emitted_coredsl_and_etiss_control_flow(self):
        from m2isar.backends.coredsl2.visitor import CDSLWriterVisitor
        from m2isar.backends.etiss.instruction_transform import InstructionTransformVisitor
        from m2isar.backends.etiss.instruction_utils import TransformerContext
        for body, expected in EXECUTION:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                model, _ = parse_model(source(body, 'int'), directory, validated=True)
                operation = model.cores['C'].functions['f'].operation
                writer = CWriter()
                CDSLWriterVisitor().generate(operation, writer)
                outputs = {'coredsl': ''.join(writer.parts)}
                context = TransformerContext({}, {}, {}, {}, {}, {}, [], {}, 0, 32, 'C', False, {}, False, ignore_static=True)
                outputs['etiss'] = '{\n' + InstructionTransformVisitor().generate(operation, context).initial_required + '\n}'
                prefix = '#include <cstdint>\n' + ''.join(
                    'using etiss_' + kind + str(bits) + ' = ' + kind + str(bits) + '_t;\n'
                    for kind in ('int','uint') for bits in (8,16,32,64))
                for backend, text in outputs.items():
                    cpp, binary = Path(directory) / (backend + '.cpp'), Path(directory) / backend
                    cpp.write_text(prefix + 'int f()' + text + '\nint main(){return f()==' + str(expected) + '?0:1;}')
                    compiled = subprocess.run(['g++','-std=c++11',str(cpp),'-o',str(binary)], capture_output=True, text=True, timeout=30)
                    self.assertEqual(compiled.returncode, 0, compiled.stderr)
                    self.assertEqual(subprocess.run([str(binary)], timeout=3).returncode, 0, cpp.read_text())

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class ContinueOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe
    def test_release_scope(self):
        for body, invalid in SCOPE_CASES:
            with self.subTest(body=body):
                output, _ = self.probe(source(body))
                self.assertEqual(output.count('ERROR:'), int(invalid), output)
                if invalid: self.assertIn('Unexpected continue statement', output)
    def test_release_mixed_order_and_valid_execution_sources(self):
        for body, expected in MIXED:
            output, _ = self.probe(source(body))
            self.assertEqual(output.count('ERROR:'), len(expected), output)
            cursor = 0
            for kind in expected:
                cursor = output.index('ERROR:Unexpected ' + kind + ' statement', cursor) + 1
        for body, _ in EXECUTION:
            output, _ = self.probe(source(body, 'int'))
            self.assertNotIn('ERROR:', output)
