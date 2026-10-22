import tempfile
import unittest
from pathlib import Path

from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo


class SourceValidatorTest(unittest.TestCase):
    def validate(self, source, warnings=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'independent.core_desc'
            path.write_text(source)
            tree = make_parser(path).description_content()
            validate_source(tree, warnings or WarningsInfo())

    def error(self, source, issue):
        with self.assertRaises(M2ValidationError) as exc:
            self.validate(source)
        self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
        self.assertIn('independent.core_desc:1', str(exc.exception))

    def test_functions(self):
        for body, issue in [
            ('int f();', 'MissingFunctionBody'),
            ('int f() {}', 'MissingReturnStatement'),
            ('void f() { return 1; }', 'ReturnWithValueInVoidFunction'),
            ('int f() { return; }', 'ReturnWithoutValueInNonVoidFunction'),
            ('int f(int &a) { return 1; }', 'ReferenceParameterDeclaration'),
        ]:
            with self.subTest(issue=issue):
                self.error('Core C { functions { ' + body + ' } }', issue)
        self.validate('Core C { functions { int f(int a) { if(a) return 1; else return 2; } } }')
        self.error('Core C { functions { int f(int a) { if(a) return 1; } } }', 'MissingReturnStatement')

    def test_declarations(self):
        for declaration, issue in [
            ('void x;', 'VoidDeclaration'),
            ('const const int x = 1;', 'DuplicateQualifier'),
            ('extern register int x;', 'MultipleStorageClassSpecifiers'),
            ('const int x;', 'UninitializedConstant'),
            ('int &x;', 'UninitializedAlias'),
            ('int &x = {1};', 'InvalidListInitializer'),
            ('extern int x[2][3];', 'MultidimensionalAddressSpace'),
            ('volatile int x = 1;', 'InvalidIsaParameterDeclaration'),
            ('float x = 1;', 'InvalidIsaParameterType'),
            ('int x[2];', 'InvalidIsaParameterDeclaration'),
        ]:
            with self.subTest(issue=issue):
                self.error('Core C { architectural_state { ' + declaration + ' } }', issue)
        self.validate('Core C { architectural_state { const int x = 1; register const int y; } }')
        self.error('Core C { functions { void f() { register int x; } } }',
                   'StorageClassSpecifierOnLocalVariable')
        self.error('Core C { functions { void f() { int y; int &x = y; } } }', 'AliasLocalVariable')

    def test_control_flow(self):
        for stmt in ('break;', 'continue;'):
            self.error('Core C { functions { void f() { ' + stmt + ' } } }',
                       'StrayControlFlowStatement')
        self.validate('Core C { functions { void f() { while(1) { break; continue; } } } }')
        self.error('Core C { instructions { I { encoding: 8\'h01; behavior: { return; } } } }',
                   'ReturnStatementOutsideFunction')
        self.error('Core C { functions { void f() { 1+2; } } }', 'InvalidStatementExpression')
        self.error('Core C { functions { void f() { for(1; 1; 2) {} } } }', 'InvalidStatementExpression')

    def test_inheritance_cycle(self):
        self.error('InstructionSet A extends B {} InstructionSet B extends A {} Core C provides A {}',
                   'CyclicInstructionSetInheritance')
        self.validate('InstructionSet A {} InstructionSet B extends A {} Core C provides B {}')

    def test_switch_defaults_and_spawn_placement(self):
        self.error('Core C { functions { void f() { switch(1) { default: break; default: } } } }',
                   'SwitchMultipleDefaultSections')
        self.validate('Core C { functions { void f() { switch(1) { default: break; } } } }')
        self.error('Core C { functions { void f() { spawn {} } } }', 'InvalidSpawnStatementPlacement')
        for behavior in ('spawn {}', '{ spawn {} }'):
            self.validate("Core C { instructions { I { encoding: 8'h01; behavior: " + behavior + ' } } }')
        for behavior in ('{ spawn {} int x; }', '{ { spawn {} } }'):
            self.error("Core C { instructions { I { encoding: 8'h01; behavior: " + behavior + ' } } }',
                       'InvalidSpawnStatementPlacement')

    def test_warnings(self):
        with self.assertLogs('validate_source', level='WARNING') as logs:
            self.validate('Core C { functions { void f() { return; int x; } } }')
        self.assertIn('com.minres.coredsl.UnreachableCode', logs.output[0])
        for condition in ('if(x=1) {}', 'while(x=1) {}', 'do {} while(x=1);',
                          'for(;x=1;) {}'):
            with self.subTest(condition=condition), self.assertLogs('validate_source') as logs:
                self.validate('Core C { functions { void f() { int x; ' + condition + ' } } }')
            self.assertIn('LikelyAccidentalAssignment', logs.output[0])
        # MINRES only warns on bare simple assignments, not += or parentheses.
        self.validate('Core C { functions { void f() { int x; if(x+=1) {} if((x=1)) {} } } }')
