"""Composite writes check the base and every selected readonly member."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


def cases():
    for kind in ('struct', 'union'):
        for base_const, field_const in ((False, False), (True, False), (False, True), (True, True)):
            definition = kind + ' S {' + ('const ' if field_const else '') + 'int a;}'
            declaration = 'register ' + ('const ' if base_const else '') + kind + ' S R;'
            yield definition + declaration, 'R.a', int(base_const) + int(field_const), int(base_const), int(field_const)
    yield 'struct T {int a;} struct S {const struct T t;} register struct S R;', 'R.t.a', 1, 0, 1
    yield 'struct S {int a;} register struct S R;', '(R).a', 1, 0, 0


def source(state, target, operator):
    statement = target + operator if operator == '++' else target + operator + '1'
    return 'Core C {architectural_state {' + state + '} functions {void f(){' + statement + ';}}}'


class CompositeAssignmentTargetNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_base_and_field_readonly_diagnostics(self):
        for state, target, count, _, _ in cases():
            for operator in ('=', '+=', '++'):
                with self.subTest(target=target, state=state, operator=operator):
                    if count:
                        with self.assertRaises(M2ValidationError) as caught:
                            self.validate(source(state, target, operator))
                        self.assertEqual(codes(caught.exception), ['InvalidAssignmentTarget'] * count)
                    else:
                        self.validate(source(state, target, operator))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class CompositeAssignmentTargetOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_base_and_member_error_counts(self):
        for state, target, count, base_count, field_count in cases():
            for operator in ('=', '+=', '++'):
                with self.subTest(target=target, state=state, operator=operator):
                    output, _ = self.probe(source(state, target, operator))
                    self.assertEqual(output.count('ERROR:'), count, output)
                    self.assertEqual(output.count('ERROR:Cannot assign to constant'), base_count, output)
                    self.assertEqual(output.count('ERROR:Cannot assign constant field'), field_count, output)
                    self.assertEqual(output.count('ERROR:Invalid assignment target'), int(target == '(R).a'), output)
