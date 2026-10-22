"""Return diagnostics after serialization and against MINRES 2.0.21."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.validate import ValidatorContext
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor


CASES = [
    ('void f() { return 1; }', 'ReturnWithValueInVoidFunction', 'Void functions may not return a value'),
    ('int f() { return; }', 'ReturnWithoutValueInNonVoidFunction', 'Non-void functions must return a value'),
    ("unsigned<8> f() { return 16'd1; }", 'ReturnTypeNotConvertible',
     'Cannot convert from unsigned<16> to unsigned<8>'),
    ('signed<8> f() { return 128; }', 'ReturnTypeNotConvertible',
     'Cannot convert from unsigned<8> to signed<8>'),
    ('void f() { return; }', None, None),
    ('signed<8> f() { return 127; }', None, None),
    ('unsigned<8> f() { return 1; }', None, None),
    ('int f() {}', 'MissingReturnStatement', 'Not all execution paths return a value'),
    ('int f() { if (1) return 1; }', 'MissingReturnStatement', 'Not all execution paths return a value'),
    ('int f() { if (1) return 1; else return 2; }', None, None),
    ('int f() { if (1) return 1; else if (0) return 2; else return 3; }', None, None),
    ('int f() { if (1) return 1; else if (0) return 2; }', 'MissingReturnStatement',
     'Not all execution paths return a value'),
    ('int f() { while (1) { return 1; } }', 'MissingReturnStatement', 'Not all execution paths return a value'),
    ('int f() { do { return 1; } while (0); }', 'MissingReturnStatement', 'Not all execution paths return a value'),
    ('int f() { return 1; int x; }', 'MissingReturnStatement', 'Not all execution paths return a value'),
    ('int f() { { return 1; } }', None, None),
    ('void f() {}', None, None),
]


class MetamodelReturnNativeTest(unittest.TestCase):
    def test_legacy_structural_return_termination(self):
        result = behav.Return(None)
        condition = behav.Literal(1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
        for statement, expected in ((behav.Block([]), False),
                                     (behav.Block([result]), True),
                                     (behav.Block([result, behav.Block([])]), False),
                                     (behav.Conditional([condition], [result]), False),
                                     (behav.Conditional([condition], [result, result]), True),
                                     (behav.Loop(condition, [result], True), False)):
            with self.subTest(statement=type(statement).__name__, expected=expected):
                self.assertEqual(ValidateBehavVisitor.is_return_terminated(statement), expected)

    def test_saved_returns(self):
        for function, issue, message in CASES:
            with self.subTest(function=function), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'return.core_desc'
                path.write_text('Core C { functions { ' + function + ' } }')
                parsed = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                result = subprocess.run([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                                         str(Path(directory) / 'gen_model' / 'return.m2isarmodel')],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, int(issue is not None), result.stdout)
                if issue:
                    self.assertIn('com.minres.coredsl.' + issue, result.stdout)
                    self.assertIn(message, result.stdout)
                self.assertNotIn('Traceback', result.stdout)

    def test_outside_function_and_unknown_type(self):
        with self.assertRaises(M2ValidationError) as caught:
            ValidateBehavVisitor().generate(behav.Return(None), ValidatorContext())
        self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.ReturnStatementOutsideFunction')
        function = arch.Function('f', {}, None, type_info.TypeKind.UINT, [], None)
        value = behav.Literal(1, type_info.PrimitiveType(type_info.TypeKind.UINT, 1))
        ValidateBehavVisitor().generate(behav.Return(value), ValidatorContext(function=function))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelReturnOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_returns(self):
        for function, issue, message in CASES:
            with self.subTest(function=function):
                output, _ = self.probe('Core C { functions { ' + function + ' } }')
                if issue:
                    self.assertIn('ERROR:' + message, output, output)
                else:
                    self.assertNotIn('ERROR:', output, output)
