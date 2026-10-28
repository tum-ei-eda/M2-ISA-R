"""Release size queries distinguish declarator references from expressions."""
import os
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from m2isar.frontends.coredsl2.behavior_model_builder import BehaviorModelBuilder
from m2isar.frontends.coredsl2.source_validator import validate_source
from m2isar.frontends.coredsl2.utils import make_parser
from m2isar.metamodel.type_info import TypeKind
from m2isar.metamodel import load_model
import test_isa_alias_parity as harness
import test_source_validator as helpers


CASES = [
    ('bitsizeof(a)', 8), ('sizeof(a)', 1),
    ('bitsizeof((a))', 32), ('sizeof((a))', 4),
    ('bitsizeof(a[0])', 8), ('bitsizeof(a[1:0])', 16),
    ('sizeof(a[1:0])', 2), ('bitsizeof(unsigned<8>)', 8),
]


def function(body, declaration='unsigned<8> a[4];'):
    return 'Core C { functions { unsigned<8> f() { ' + declaration + body + ' } } }'


PARTIAL = ('InstructionSet I { architectural_state { int N; } functions { '
           'void f() { int a[N]; unsigned<5> x=bitsizeof(a); } } }')

STATE = '''Core C { architectural_state {
  register unsigned<8> R[4]; extern unsigned<3> M[100];
  unsigned<4> RB=bitsizeof(R); unsigned<1> RS=sizeof(R);
  unsigned<2> MB=bitsizeof(M); unsigned<1> MS=sizeof(M);
} }'''


class SizeQueryReferenceNativeTest(unittest.TestCase):
    validate = helpers.SourceValidatorTest.validate
    error = helpers.SourceValidatorTest.error

    def test_exact_values_and_result_types_in_lowering(self):
        for expression, expected in CASES:
            with self.subTest(expression=expression), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'sizes.core_desc'
                path.write_text(function('return ' + expression + ';'))
                tree = make_parser(path).description_content()
                validate_source(tree, None)
                builder = BehaviorModelBuilder({}, {}, {}, {}, {}, {}, {}, set())
                body = tree.definitions[0].sections[0].functions[0].behavior
                result = builder.visit(body).statements[-1].expr
                self.assertEqual(result.value, expected)
                self.assertEqual((result.ty.kind, result.ty.size),
                                 (TypeKind.UINT, expected.bit_length()))

    def test_conversion_boundaries(self):
        for expression, expected in CASES:
            width = expected.bit_length()
            with self.subTest(expression=expression):
                self.validate(function('unsigned<' + str(width) + '> x=' + expression + '; return 0;'))
                if width > 1:
                    self.error(function('unsigned<' + str(width - 1) + '> x=' + expression + '; return 0;'),
                               'InvalidAssignmentType')

    def test_incomplete_array_reference_has_known_declared_size(self):
        self.error(PARTIAL, 'InvalidAssignmentType')
        self.validate(PARTIAL.replace('unsigned<5>', 'unsigned<6>'))

    def test_multidimensional_reference_uses_base_type(self):
        self.validate(function('unsigned<4> x=bitsizeof(a); return x;', 'unsigned<8> a[2][3];'))

    def test_architecture_constants_survive_cli_and_serialization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sizes.core_desc'
            path.write_text(STATE)
            result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.coredsl2.parser',
                                     str(path), '--validate', '-Wno-size-of-not-exact'],
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout)
            core = load_model(Path(directory) / 'gen_model' / 'sizes.m2isarmodel').cores['C']
            self.assertEqual({name: core.parameters[name].value for name in ('RB', 'RS', 'MB', 'MS')},
                             {'RB': 8, 'RS': 1, 'MB': 3, 'MS': 1})


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class SizeQueryReferenceOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_exact_values(self):
        for expression, expected in CASES:
            with self.subTest(expression=expression):
                # Only zero among even integers fits unsigned<1>. Constant
                # assignment therefore pins the exact size after analysis.
                # Expression size queries in array dimensions can crash the
                # release because the argument type has not been analyzed yet.
                output, _ = self.probe(function('unsigned<1> x=(' + expression +
                                               '-' + str(expected) + ')*2; return 0;'))
                self.assertEqual(output.count('ERROR:'), 0, output)

    def test_release_conversion_boundaries(self):
        for expression, expected in CASES:
            width = expected.bit_length()
            with self.subTest(expression=expression):
                output, _ = self.probe(function('unsigned<' + str(width) + '> x=' + expression + '; return 0;'))
                self.assertEqual(output.count('ERROR:'), 0, output)
                if width > 1:
                    output, _ = self.probe(function('unsigned<' + str(width - 1) + '> x=' + expression + '; return 0;'))
                    self.assertEqual(output.count('ERROR:Cannot implicitly convert'), 1, output)
                    self.assertEqual(output.count('ERROR:'), 1, output)

    def test_release_incomplete_and_multidimensional_references(self):
        output, _ = self.probe(PARTIAL)
        self.assertEqual(output.count('ERROR:Cannot implicitly convert unsigned<6> to unsigned<5>'), 1, output)
        self.assertEqual(output.count('ERROR:'), 1, output)
        for text in (PARTIAL.replace('unsigned<5>', 'unsigned<6>'),
                     function('unsigned<4> x=bitsizeof(a); return x;', 'unsigned<8> a[2][3];')):
            output, _ = self.probe(text)
            self.assertEqual(output.count('ERROR:'), 0, output)

    def test_release_architecture_reference_sizing_and_rounding(self):
        output, _ = self.probe(STATE)
        self.assertEqual(output.count('ERROR:'), 0, output)
        self.assertEqual(output.count('WARNING:The size (3 bits) is not an exact multiple of 8'), 1, output)
