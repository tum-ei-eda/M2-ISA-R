"""Standalone break scope, including nested loops and validator reuse."""
import os
import pickle
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info, load_model
from m2isar.metamodel.utils.control_flow import preserve_break_scope
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.transforms.validate_behav.validate import validate_behav
from m2isar.transforms.infer_types.transform import infer_types
from m2isar.warnings import WarningsManager


CASES = [('break;', True), ('{ break; }', True), ('if (1) break;', True),
         ('while (1) { break; }', False), ('do { break; } while (0);', False),
         ('while (1) { if (1) { break; } }', False),
         ('while (1) { while (1) { break; } break; }', False),
         ('while (1) { break; } break;', True),
         ('if (0) break;', True),
         ('if (1) {} else break;', True),
         ('while (0) { break; }', False),
         ('while (1) { if (0) break; break; }', False)]


class MetamodelBreakNativeTest(unittest.TestCase):
    def test_multiple_preserved_break_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'multiple.core_desc'
            path.write_text('Core C { functions { void f() {\n if (0) {\n break;\n } else if (0) {\n break;\n }\n} } }')
            parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(parsed.returncode, 0, parsed.stdout)
            saved = Path(directory) / 'gen_model' / 'multiple.m2isarmodel'
            model = load_model(saved)
            with self.assertRaises(M2ValidationError) as caught:
                validate_behav(model, None)
            errors = [caught.exception] + caught.exception.related_diagnostics
            self.assertEqual([error.line_info.start_line_no for error in errors], [3, 5])
            self.assertTrue(all(error.issue_code == 'com.minres.coredsl.StrayControlFlowStatement' for error in errors))
            self.assertTrue(all(error.line_info.file_path == path for error in errors))
            self.assertNotIn('\n', caught.exception.args[0])
            result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertEqual(result.stdout.count('Unexpected break statement'), 2, result.stdout)
            self.assertIn(str(path) + ':3', result.stdout)
            self.assertIn(str(path) + ':5', result.stdout)
            self.assertNotIn('Traceback', result.stdout)

    def test_preserved_breaks_in_all_inference_scopes(self):
        for scope in ('cores', 'sets'):
            for owner in ('functions', 'instructions', 'always_blocks'):
                for invalid in (False, True):
                    with self.subTest(scope=scope, owner=owner, invalid=invalid):
                        zero = behav.Literal(0, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
                        branch = behav.Conditional([zero], [behav.Block([behav.Break()])])
                        if not invalid:
                            branch = behav.Loop(zero, [branch], False)
                        body = behav.Operation([branch])
                        member = SimpleNamespace(name='body', operation=body, extern=False,
                                                 ty=type_info.FunctionType(0, type_info.TypeKind.VOID))
                        definition = SimpleNamespace(name='C', functions={}, instructions={}, always_blocks={})
                        getattr(definition, owner)['body'] = member
                        model = SimpleNamespace(cores={}, sets={})
                        getattr(model, scope)['C'] = definition
                        infer_types(model)
                        self.assertEqual(body._stray_break_locations, [None] if invalid else [])
                        restored = pickle.loads(pickle.dumps(model))
                        infer_types(restored)
                        if invalid:
                            with self.assertRaises(M2ValidationError) as caught:
                                validate_behav(restored, None)
                            self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.StrayControlFlowStatement')
                        else:
                            validate_behav(restored, None)

    def test_preserved_scope_survives_repeated_inference_and_legacy_models(self):
        root = behav.Operation([behav.Break()])
        preserve_break_scope(root)
        root.statements.clear()
        preserve_break_scope(root)
        self.assertEqual(root._stray_break_locations, [None])
        with self.assertRaises(M2ValidationError):
            ValidateBehavVisitor().generate(root, WarningsManager(None))
        # Legacy models have no evidence field and still use retained nodes.
        ValidateBehavVisitor().generate(behav.Operation([]), WarningsManager(None))

    def test_loop_depth_restored_after_success_and_failure(self):
        visitor, context = ValidateBehavVisitor(), WarningsManager(None)
        condition = behav.Literal(1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
        visitor.generate(behav.Loop(condition, [behav.Loop(condition, [behav.Break()], False), behav.Break()], False), context)
        with self.assertRaises(M2ValidationError) as caught:
            visitor.generate(behav.Break(), context)
        self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.StrayControlFlowStatement')
        with self.assertRaises(M2ValidationError):
            visitor.generate(behav.Loop(condition, [behav.Return(None)], False), context)
        with self.assertRaises(M2ValidationError):
            visitor.generate(behav.Break(), context)

    def test_saved_break_scope(self):
        for body, invalid in CASES:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'break.core_desc'
                path.write_text('Core C { functions { void f() { ' + body + ' } } }')
                parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(Path(directory) / 'gen_model' / 'break.m2isarmodel')],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, int(invalid), result.stdout)
                if invalid:
                    self.assertIn('Unexpected break statement', result.stdout)
                    self.assertIn('com.minres.coredsl.StrayControlFlowStatement', result.stdout)
                self.assertNotIn('Traceback', result.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelBreakOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_multiple_release_breaks(self):
        output, _ = self.probe('Core C { functions { void f() {\n if (0) {\n break;\n } else if (0) {\n break;\n }\n} } }')
        self.assertEqual(output.count('ERROR:Unexpected break statement'), 2, output)
        self.assertIn('line : 3', output)
        self.assertIn('line : 5', output)

    def test_release_break_scope(self):
        for body, invalid in CASES:
            with self.subTest(body=body):
                output, _ = self.probe('Core C { functions { void f() { ' + body + ' } } }')
                if invalid:
                    self.assertIn('ERROR:Unexpected break statement', output, output)
                else:
                    self.assertNotIn('ERROR:', output, output)
