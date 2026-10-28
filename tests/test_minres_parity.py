"""Opt-in differential tests against the official 2.0.21 release.

Set COREDSL_VALIDATOR_JAR to the release JAR. Never trust its exit status:
ValidatorMain can report validation errors while returning zero.
"""
import logging
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo

# Each negative case isolates the named semantic check with resolvable names.
CASES = [
    ('MissingReturnStatement', 'ERROR', 'Not all execution paths return a value',
     'functions { int f() {} }'),
    ('ReturnWithValueInVoidFunction', 'ERROR', 'Void functions may not return a value',
     'functions { void f() { return 1; } }'),
    ('ReturnWithoutValueInNonVoidFunction', 'ERROR', 'Non-void functions must return a value',
     'functions { int f() { return; } }'),
    ('VoidDeclaration', 'ERROR', 'Declarations may not use type void',
     'functions { void f() { void x; } }'),
    ('DuplicateQualifier', 'ERROR', 'Duplicate qualifier',
     'functions { void f() { const const int x = 1; } }'),
    ('MultipleStorageClassSpecifiers', 'ERROR', 'more than one storage class',
     'architectural_state { extern register int x; }'),
    ('UninitializedConstant', 'ERROR', 'declared as const must be initialized',
     'functions { void f() { const int x; } }'),
    ('AliasLocalVariable', 'ERROR', 'local variable may not be declared as alias',
     'functions { void f() { int y = 1; int &x = y; } }'),
    ('ReferenceParameterDeclaration', 'ERROR', 'parameters may not be passed by reference',
     'functions { int f(int &a) { return 1; } }'),
    ('StrayControlFlowStatement', 'ERROR', 'Unexpected break statement',
     'functions { void f() { break; } }'),
    ('StrayControlFlowStatement', 'ERROR', 'Unexpected continue statement',
     'functions { void f() { continue; } }'),
    ('InvalidStatementExpression', 'ERROR', 'Invalid expression in expression statement',
     'functions { void f() { 1+2; } }'),
    ('UnreachableCode', 'WARNING', 'Unreachable code',
     'functions { void f() { return; int x; } }'),
    ('LikelyAccidentalAssignment', 'WARNING', 'Likely accidental assignment',
     'functions { void f() { int x; if(x=1) {} } }'),
    ('LikelyAccidentalAssignment', 'WARNING', 'Likely accidental assignment',
     'functions { void f() { int x; while(x=1) {} } }'),
    ('LikelyAccidentalAssignment', 'WARNING', 'Likely accidental assignment',
     'functions { void f() { int x; do {} while(x=1); } }'),
    ('LikelyAccidentalAssignment', 'WARNING', 'Likely accidental assignment',
     'functions { void f() { int x; for(;x=1;) {} } }'),
    ('SwitchMultipleDefaultSections', 'ERROR', 'Multiple default sections',
     'functions { void f() { switch(1) { default: break; default: break; } } }'),
    ('InvalidSpawnStatementPlacement', 'ERROR', 'spawn statement must be the last statement',
     'functions { void f() { spawn {} } }'),
    ('UnknownAttribute', 'WARNING', "Unknown attribute 'custom'",
     'functions { void f() [[custom]] {} }'),
    ('InvalidAttributePlacement', 'ERROR', "Attribute 'no_cont' cannot be placed here",
     'functions { void f() [[no_cont]] {} }'),
    ('InvalidAttributePlacement', 'ERROR', 'requires exactly 1 parameter, but got 0',
     "instructions { I [[expected_encoding_size]] { encoding: 8'h01; behavior: {} } }"),
    ('InvalidAttributePlacement', 'ERROR', 'requires exactly 0 parameters, but got 1',
     "instructions { I [[cond(1)]] { encoding: 8'h01; behavior: {} } }"),
    ('UnexpectedInstructionSize', 'WARNING', 'Expected an encoding size of 16, but got 8',
     "instructions [[expected_encoding_size(16)]] { I { encoding: 8'h01; behavior: {} } }"),
    ('UnexpectedInstructionSize', 'WARNING', 'Expected an encoding size of 16, but got 1',
     'instructions [[expected_encoding_size(16)]] { I { encoding: 0x01; behavior: {} } }'),
    ('UnexpectedInstructionSize', 'WARNING', 'Expected an encoding size of 16, but got 9',
     'instructions [[expected_encoding_size(16)]] { I { encoding: a[7:0] :: a[8:8]; behavior: {} } }'),
    ('InvalidIntegerTypeSize', 'ERROR', 'Integer type size must be greater than 0',
     'functions { void f() { unsigned<0> x; } }'),
    ('InvalidIntegerTypeSize', 'ERROR', 'Integer type size must be greater than 0',
     'functions { void f() { unsigned<(-1)> x; } }'),
    ('InvalidIntegerTypeSize', 'ERROR', 'Integer type size must not exceed Integer.MAX_VALUE',
     'functions { void f() { unsigned<2147483648> x; } }'),
    ('InvalidArraySize', 'ERROR', 'Negative array size is invalid',
     'functions { void f() { int x[-1]; } }'),
    ('InvalidArraySize', 'ERROR', 'Negative array size is invalid',
     "functions { void f() { int x[8'shff]; } }"),
    ('InvalidArraySize', 'ERROR', 'Negative array size is invalid',
     'functions { void f() { int x[1-2]; } }'),
    ('ArraySizeIsZero', 'WARNING', 'Array size is zero',
     'functions { void f() { int x[1-1]; } }'),
    ('DivisionByZero', 'ERROR', 'Division by zero',
     'functions { void f() { int x[1/0]; } }'),
    ('IndexOutOfRange', 'ERROR', 'Index out of range',
     'instructions { I { encoding: a[2147483648:0]; behavior: {} } }'),

]


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class MinresParityTest(unittest.TestCase):
    def test_semantic_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            for number, (issue, severity, message, sections) in enumerate(CASES):
                with self.subTest(issue=issue, number=number):
                    path = Path(directory) / f'case_{number}.core_desc'
                    path.write_text('Core C { ' + sections + ' }')
                    result = subprocess.run(
                        ['java', '-jar', os.environ['COREDSL_VALIDATOR_JAR'], '-v', str(path)],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, timeout=30, check=False)
                    oracle = result.stdout
                    self.assertIn(severity + ':', oracle, oracle)
                    self.assertIn(message, oracle, oracle)
                    self.assertNotIn('internal error', oracle.lower(), oracle)
                    tree = make_parser(path).description_content()
                    if severity == 'ERROR':
                        with self.assertRaises(M2ValidationError) as exc:
                            validate_source(tree, WarningsInfo())
                        self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
                    else:
                        self.assertNotIn('ERROR:', oracle, oracle)
                        with self.assertLogs('validate_source', level=logging.WARNING) as logs:
                            validate_source(tree, WarningsInfo())
                        self.assertTrue(any('com.minres.coredsl.' + issue in log for log in logs.output))

    def test_release_direct_encoding_attribute_bug(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'direct_attribute.core_desc'
            path.write_text("Core C { instructions { I [[expected_encoding_size(16)]] { encoding: 8'h01; behavior: {} } } }")
            result = subprocess.run(
                ['java', '-jar', os.environ['COREDSL_VALIDATOR_JAR'], '-v', str(path)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, timeout=30, check=False)
            self.assertIn('ERROR:An internal error occurred during analysis', result.stdout)
            self.assertIn('Value has not been set for node Encoding', result.stdout)
            # Native validation follows the intended release source rule. This
            # case records an oracle defect, not agreement on runtime outcome.
            tree = make_parser(path).description_content()
            with self.assertLogs('validate_source', level=logging.WARNING) as logs:
                validate_source(tree, WarningsInfo())
            self.assertTrue(any('UnexpectedInstructionSize' in log for log in logs.output))
