import unittest

import test_source_validator as helpers
from m2isar.warnings import WarningsInfo


class SourceSemanticsTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_function_calls(self):
        self.error('Core C { functions { void f(int x) {} void g() { f(); } } }', 'InvalidArgumentCount')
        self.error('Core C { functions { void f(unsigned<8> x) {} void g() { int x; f(x); } } }', 'InvalidArgumentType')
        self.error('Core C { functions { void f() { int x; x(); } } }', 'InvalidFunction')
        self.error('Core C { functions { void f() {} void g() { int x = f; } } }', 'ReferenceToFunction')
        self.validate('Core C { functions { void f(unsigned<8> x) {} void g() { f(1); } } }')
        self.validate('Core C { functions { void f(unsigned<8> x) {} void g() { f(16\'h01); } } }')

    def test_conversions_and_return(self):
        self.error('Core C { functions { unsigned<8> f(int x) { return x; } } }', 'ReturnTypeNotConvertible')
        self.error('Core C { functions { signed<1> f() { return 1; } } }', 'ReturnTypeNotConvertible')
        self.error('Core C { functions { void f() { int x; unsigned<8> y = x; } } }', 'InvalidAssignmentType')
        self.error('Core C { functions { void f() { unsigned<8> x = 256; } } }', 'InvalidAssignmentType')
        self.error('Core C { functions { void f() { const int x = 1; x = 2; } } }', 'InvalidAssignmentTarget')
        self.error('Core C { architectural_state { int x = 1; } functions { void f() { x = 2; } } }', 'InvalidAssignmentTarget')
        self.validate('Core C { functions { void f() { unsigned<8> x = 16\'hff; } } }')

    def test_arrays_conditions_casts_indices(self):
        self.error('Core C { functions { void f() { int x[2]; if(x) {} } } }', 'NonScalarCondition')
        self.error('Core C { functions { void f() { int x[2]; switch(x) {} } } }', 'SwitchConditionTypeInvalid')
        self.error('Core C { functions { void f() { int x[2]; int y = (signed)x; } } }', 'InvalidCast')
        self.error('Core C { functions { void g() {} void f() { int x = g()[0]; } } }', 'NonIndexableExpression')
        self.error('Core C { functions { void f() { int x[2]; int y[2]; int z = x[y]; } } }', 'InvalidIndexType')
        self.error('Core C { functions { void f() { unsigned<8> x; int a; int b; int z = x[a:b]; } } }', 'InvalidRangePattern')
        self.error('Core C { functions { void f() { int x[2]; int y = x + 1; } } }', 'InvalidOperationType')
        self.error('Core C { functions { void f() { int x[2]; int y = 1 ? x : 0; } } }', 'IncompatibleOptionTypes')
        self.validate('Core C { functions { void f() { unsigned<8> x; int a; unsigned<4> y = x[a:a+3]; } } }')

    def test_parameter_dependent_sizes(self):
        self.error('Core C { architectural_state { int W = 0; } functions { void f() { unsigned<W> x; } } }', 'InvalidIntegerTypeSize')
        self.error('Core C { architectural_state { int N = -1; } functions { void f() { int x[N]; } } }', 'InvalidArraySize')
        self.error('Core C { functions { void f() { const int N = 1; int x[N]; } } }', 'InvalidConstantExpressionIdentifier')
        self.validate('InstructionSet A { architectural_state { int W; } functions { void f() { unsigned<W> x; } } } Core C provides A { architectural_state { W = 8; } }')
        self.error('InstructionSet A { architectural_state { int W; } functions { void f() { unsigned<W> x; } } } Core C provides A { architectural_state { W = 0; } }', 'InvalidIntegerTypeSize')
        with self.assertLogs('validate_source') as logs:
            self.validate('Core C { architectural_state { int N = 0; } functions { void f() { int x[N]; } } }')
        self.assertIn('ArraySizeIsZero', logs.output[0])

    def test_switch_cases(self):
        self.error('Core C { functions { void f() { switch(1) { case 1: break; case 1: break; } } } }', 'SwitchDuplicateCaseSection')
        self.error('Core C { functions { void f(unsigned<1> x) { switch(x) { case 2: break; } } } }', 'SwitchCaseConditionOutOfRange')
        self.error('Core C { architectural_state { int A = 1; int B = 1; } functions { void f() { switch(1) { case A: break; case B: break; } } } }', 'SwitchDuplicateCaseSection')

    def test_scope_and_identity_mode(self):
        self.validate('Core C { architectural_state { int N = 8; } functions { void f() { { int N; } unsigned<N> x; } } }')
        self.error('Core C { architectural_state { int N = 8; } functions { void f() { int N; unsigned<N> x; } } }', 'InvalidConstantExpressionIdentifier')
        source = 'Core C { functions { void f() { int x; int y = (signed)x; } } }'
        with self.assertNoLogs('validate_source', level='WARNING'):
            self.validate(source)
        with self.assertLogs('validate_source') as logs:
            self.validate(source, WarningsInfo(enabled={'identity-cast'}))
        self.assertIn('IdentityCast', logs.output[0])

    def test_signature_is_not_affected_by_caller_shadowing(self):
        self.validate('Core C { architectural_state { int W = 8; } functions { unsigned<W> f() { return 1; } void g() { int W; unsigned<8> y = f(); } } }')
        self.error('Core C { functions { void f() { signed<1> x = 0; } } }', 'InvalidAssignmentType')

    def test_named_encoding_size(self):
        source = "Core C { architectural_state { int W = 16; } instructions [[expected_encoding_size(W)]] { I { encoding: 8'h01; behavior: {} } } }"
        with self.assertLogs('validate_source') as logs:
            self.validate(source)
        self.assertIn('UnexpectedInstructionSize', logs.output[0])
