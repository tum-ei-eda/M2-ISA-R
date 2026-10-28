"""Reference resolution precedes semantic diagnostics and respects lexical scope."""
import os
import unittest
import test_source_validator as helpers
import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError

LINKING = 'org.eclipse.xtext.diagnostics.Diagnostic.Linking'

def function(body):
    return 'Core C { functions { void g() {} void f() { ' + body + ' } } }'

CASES = [
    ('Core C {architectural_state {int A=B; int B=A;}}', 'NamedEntity', 'B'),
    (function('g(missing);'), 'NamedEntity', 'missing'),
    (function('g(0); missing();'), 'NamedEntity', 'missing'),
    (function('int &x=y;'), 'NamedEntity', 'y'),
    (function('int x=x;'), 'NamedEntity', 'x'),
    (function('{int x=1;} x=0;'), 'NamedEntity', 'x'),
    (function('for(int a=1,b=a;a<2;a++){} a=0;'), 'NamedEntity', 'a'),
    ('Core C { architectural_state { int A=B; int B=1; } }', 'NamedEntity', 'B'),
    ('Core C { architectural_state { int A=B,B=1; } }', 'NamedEntity', 'B'),
    (function('g(0); struct Missing x;'), 'StructTypeDeclaration', 'Missing'),
    (function('enum Missing x;'), 'EnumTypeDeclaration', 'Missing'),
    ('Core C { architectural_state { struct S {int x;} register struct S R; } functions {void f(){int z=R.missing;}} }', 'Declarator', 'missing'),
]
SIBLINGS = ('InstructionSet A { architectural_state {struct SA {int x;} register struct SA R;} } '
            'InstructionSet B { architectural_state {struct SB {int y;} register struct SB R;} } '
            'Core C provides A,B {functions {void f(){int z=R.%s;}}}')
CASES.append((SIBLINGS % 'y', 'Declarator', 'y'))

ENUM_INHERITED = ('InstructionSet A {architectural_state {enum E {AX=1}}} '
                  'Core C provides A {architectural_state {enum E {BX=256} register enum E R;} '
                  'functions {void f(){unsigned<2> n=bitsizeof(enum E);}}}')
VALID = [
    ENUM_INHERITED,
    function('int x=1; {int x=x;}'),
    function('for(int a=1,b=a;a<2;a++){}'),
    'Core C { architectural_state { int B=1; int A=B; } }',
    'Core C { architectural_state { int B=1,A=B; } }',
    'InstructionSet A { architectural_state { struct S {int x;} } } Core C provides A { architectural_state { struct S {int y;} register struct S R; } functions {void f(){int z=R.x;}} }',
]

class SourceLinkingNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate

    def test_unresolved_references_suppress_semantic_errors(self):
        for source, kind, name in CASES:
            with self.subTest(source=source):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(source)
                error = caught.exception
                self.assertEqual(error.issue_code, LINKING)
                self.assertIn(f"{kind} '{name}'", str(error))
                self.assertEqual(error.related_diagnostics, [])

    def test_valid_scopes_and_inherited_type_precedence(self):
        for source in VALID:
            with self.subTest(source=source):
                self.validate(source)

    def test_first_inherited_entity_links_before_signature_validation(self):
        with self.assertRaises(M2ValidationError) as caught:
            self.validate(SIBLINGS % 'x')
        self.assertEqual(caught.exception.issue_code,
                         'com.minres.coredsl.MismatchingIsaStateElementSignatures')

    def test_all_unresolved_references_are_retained(self):
        with self.assertRaises(M2ValidationError) as caught:
            self.validate(function('g(first); second();'))
        errors = [caught.exception, *caught.exception.related_diagnostics]
        self.assertEqual([e.issue_code for e in errors], [LINKING, LINKING])
        self.assertIn("'first'", str(errors[0]))
        self.assertIn("'second'", str(errors[1]))

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SourceLinkingOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_linking_precedence_and_scopes(self):
        for source, kind, name in CASES:
            with self.subTest(source=source):
                output, _ = self.probe(source)
                self.assertEqual(output.count('ERROR:'), 1, output)
                self.assertIn(f"Couldn't resolve reference to {kind} '{name}'", output)

    def test_release_first_inherited_entity(self):
        output, _ = self.probe(SIBLINGS % 'x')
        self.assertEqual(output.count('ERROR:'), 1, output)
        self.assertIn('mismatching signatures', output)
        self.assertNotIn("Couldn't resolve", output)

    def test_release_valid_controls(self):
        for source in VALID:
            with self.subTest(source=source):
                output, _ = self.probe(source)
                self.assertNotIn('ERROR:', output)
