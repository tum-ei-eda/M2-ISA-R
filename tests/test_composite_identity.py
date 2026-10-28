"""Composite assignment and equality preserve declaration identity."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.warnings import WarningsInfo

STATE = ('struct S { unsigned<8> x; } struct T { unsigned<8> x; } '
         'register struct S R; register struct S Q; register struct T U;')
CASES = [
    ('R = Q;', None, ''),
    ('R = U;', 'InvalidAssignmentType', 'Cannot implicitly convert struct T to struct S'),
    ('bool b = R == Q;', None, ''),
    ('bool b = R == U;', 'InvalidOperationType', 'Equality comparisons are only valid'),
    ('struct S v = (struct S)R;', 'InvalidCast', 'Cannot cast from struct S to struct S'),
]


def source(body):
    return 'Core C { architectural_state { ' + STATE + ' } functions { void f() { ' + body + ' } } }'


class CompositeIdentityNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_identity(self):
        for body, issue, message in CASES:
            with self.subTest(body=body):
                if issue is None:
                    self.validate(source(body))
                else:
                    with self.assertRaises(M2ValidationError) as exc:
                        self.validate(source(body))
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
                    if issue != 'InvalidOperationType':
                        self.assertIn(message, str(exc.exception))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class CompositeIdentityOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_identity(self):
        for body, issue, message in CASES:
            with self.subTest(body=body):
                output, tree = self.probe(source(body))
                if issue is None:
                    self.assertNotIn('ERROR:', output)
                    validate_source(tree, WarningsInfo())
                else:
                    self.assertIn(message, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_source(tree, WarningsInfo())
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
