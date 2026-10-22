"""Release 2.0.21 cannot link members directly on function-call results."""
import os
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError


INVALID = ['g().a=1;', 'g().a++;', 'g(1).a=1;',
           'int n=g(1).a;', 'int n=(g(1)).a;', 'g(1).a+=1;']
VALID = ['R.a=1;', 'R.a++;', 'int n=R.a;', 'int n=(R).a;']


def source(statement):
    return ('Core C {architectural_state {struct S {int a;} register struct S R;}'
            'functions {extern struct S g(int n);void f(){' + statement + '}}}')


class CallResultMemberLinkingNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_call_result_linking_precedes_semantic_errors(self):
        for statement in INVALID:
            with self.subTest(statement=statement):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source(statement))
                self.assertEqual(codes(caught.exception), ['Linking'])
                self.assertEqual(caught.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Linking')
                self.assertIn("Declarator 'a'", str(caught.exception))
        for statement in VALID:
            with self.subTest(statement=statement):
                self.validate(source(statement))


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class CallResultMemberLinkingOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_call_result_member_scope(self):
        for statement in INVALID + VALID:
            with self.subTest(statement=statement):
                output, _ = self.probe(source(statement))
                expected = int(statement in INVALID)
                self.assertEqual(output.count('ERROR:'), expected, output)
                self.assertEqual(output.count("Couldn't resolve reference to Declarator 'a'"), expected, output)
