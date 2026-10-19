"""Named composite definitions, layout and source diagnostics."""
import os
from pathlib import Path
import tempfile
import unittest

import test_isa_alias_parity as harness
import test_source_validator as helpers
from m2isar.diagnostics import M2ValidationError
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.source_semantics import SemanticValidator
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.warnings import WarningsInfo

CASES = [
    ('struct S { const const unsigned<8> x; }', '', None, ''),
    ('struct S { register unsigned<8> x; }', '', None, ''),
    ('struct S { unsigned<8> &x; }', '', None, ''),
    ('struct S { unsigned<3> a; unsigned<5> b; } register struct S R;',
     'void f() { unsigned<3> x = R.a; unsigned<4> n = bitsizeof(struct S); }', None, ''),
    ('union U { unsigned<3> a; unsigned<8> b; } register union U R;',
     'void f() { unsigned<8> x = R.b; }', None, ''),
    ('struct S { void x; }', '', None, ''),
    ('struct S { unsigned<0> x; }', '', 'InvalidIntegerTypeSize', 'greater than 0'),
    ('struct S { unsigned<8> x; } register struct S R;',
     'void f() { int x = R + 1; }', 'InvalidOperationType', 'Addition is only valid'),
    ('struct S { unsigned<8> x; } register struct S R;',
     'void f() { if (R) {} }', 'NonScalarCondition', 'must be a scalar type'),
    ('struct S { const unsigned<8> x; } register struct S R;',
     'void f() { R.x = 1; }', 'InvalidAssignmentTarget', 'Cannot assign constant field'),
    ('struct S { unsigned<8> x; } register struct S R;',
     'void f() { R.x = 256; }', 'InvalidAssignmentType', 'Cannot implicitly convert'),
    ('struct S { unsigned<8> x; } struct T { struct S a; } register struct T R;',
     'void f() { R.a.x = 1; }', None, ''),
]


def source(state, functions):
    return ('Core C { architectural_state { ' + state + ' } '
            + ('functions { ' + functions + ' } ' if functions else '') + '}')


class CompositeNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_field_initializer_syntax_diagnostic(self):
        with self.assertRaises(M2ValidationError) as exc:
            self.validate(source('struct S { unsigned<8> x = 1; }', ''))
        self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax')

    def test_negative_field_array_size(self):
        self.error(source('struct S { unsigned<8> x[-1]; }', ''), 'InvalidArraySize')

    def test_layout_with_dependent_array_and_nested_composite(self):
        text = source('unsigned<2> W = 3; struct S { unsigned<W> x[2]; unsigned<5> y; } '
                      'union U { struct S s; unsigned<4> y; } register struct S R; register union U T;', '')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'independent.core_desc'
            path.write_text(text)
            tree = make_parser(path).description_content()
            validator = SemanticValidator(tree, WarningsInfo())
            validator.visit(tree)
            self.assertEqual(validator.symbol_type(validator.lookup('R')).width, 11)
            self.assertEqual(validator.symbol_type(validator.lookup('T')).width, 11)

    def test_composites(self):
        for state, functions, issue, _ in CASES:
            with self.subTest(state=state, functions=functions):
                if issue is None:
                    self.validate(source(state, functions))
                else:
                    self.error(source(state, functions), issue)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'), 'Set COREDSL_VALIDATOR_JAR for differential tests')
class CompositeOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_field_initializer_syntax_diagnostic(self):
        output, tree = self.probe(source('struct S { unsigned<8> x = 1; }', ''))
        self.assertIn("mismatched input '=' expecting ';'", output)
        with self.assertRaises(M2ValidationError) as exc:
            validate_source(tree, WarningsInfo())
        self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax')

    def test_negative_field_array_reference_limitation(self):
        output, _ = self.probe(source('struct S { unsigned<8> x[-1]; }', ''), allow_internal_error=True)
        self.assertIn('An internal error occurred during analysis', output)
        self.assertIn('IndexOutOfBoundsException', output)

    def test_composites(self):
        for state, functions, issue, message in CASES:
            with self.subTest(state=state, functions=functions):
                output, tree = self.probe(source(state, functions))
                if issue is None:
                    self.assertNotIn('ERROR:', output, output)
                    validate_source(tree, WarningsInfo())
                else:
                    self.assertIn('ERROR:', output, output)
                    self.assertIn(message, output, output)
                    with self.assertRaises(M2ValidationError) as exc:
                        validate_source(tree, WarningsInfo())
                    self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
