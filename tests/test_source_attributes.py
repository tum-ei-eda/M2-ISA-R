import unittest
import subprocess
import sys
import tempfile
from pathlib import Path

from m2isar.frontends.coredsl2.architecture_model_builder import ArchitectureModelBuilder
from m2isar.frontends.coredsl2.utils import make_parser

import test_source_validator as source_tests


class SourceAttributesTest(unittest.TestCase):
    validate = source_tests.SourceValidatorTest.validate
    error = source_tests.SourceValidatorTest.error
    def test_attribute_rules(self):
        for sections, message in (
            ('functions { void f() [[no_cont]] {} }', 'cannot be placed here'),
            ("instructions { I [[enable]] { encoding: 8'h01; behavior: {} } }", 'requires exactly'),
            ("instructions { I [[cond(1)]] { encoding: 8'h01; behavior: {} } }", 'requires exactly'),
            ('architectural_state { register int x [[clk_budget(1)]]; }', 'cannot be placed here'),
        ):
            with self.subTest(sections=sections):
                self.error('Core C { ' + sections + ' }', 'InvalidAttributePlacement')
        with self.assertLogs('validate_source', level='WARNING') as logs:
            self.validate('Core C { functions { void f() [[custom]] {} } }')
        self.assertIn('com.minres.coredsl.UnknownAttribute', logs.output[0])
        self.validate("Core C { instructions { I [[cond]] [[enable(1)]] { encoding: 8'h01; behavior: {} } } }")

    def test_encoding_size_and_overrides(self):
        for encoding, actual in (("8'h01", 8), ('0x01', 1), ('a[7:0] :: a[8:8]', 9)):
            with self.subTest(encoding=encoding), self.assertLogs('validate_source') as logs:
                self.validate("Core C { instructions { I [[expected_encoding_size(16)]] { encoding: " + encoding + '; behavior: {} } } }')
            self.assertIn('com.minres.coredsl.UnexpectedInstructionSize', logs.output[0])
            self.assertIn(f'got {actual}', logs.output[0])
        self.validate("Core C { instructions [[expected_encoding_size(16)]] { I [[expected_encoding_size(8)]] { encoding: 8'h01; behavior: {} } } }")
        self.error("Core C { instructions { I { encoding: a[2147483648:0]; behavior: {} } } }", 'IndexOutOfRange')

    def test_literal_dimensions_and_widths(self):
        for size in ('0', '(-1)'):
            self.error('Core C { functions { void f() { unsigned<' + size + '> x; } } }', 'InvalidIntegerTypeSize')
        self.error('Core C { functions { void f() { unsigned<2147483648> x; } } }', 'InvalidIntegerTypeSize')
        for size in ('-1', "8'shff", '(1-2)'):
            self.error('Core C { functions { void f() { int x[' + size + ']; } } }', 'InvalidArraySize')
        with self.assertLogs('validate_source') as logs:
            self.validate('Core C { functions { void f() { int x[1-1]; } } }')
        self.assertIn('ArraySizeIsZero', logs.output[0])
        with self.assertLogs('validate_source') as logs:
            self.validate('Core C { functions { void f() { int x[2147483648]; } } }')
        self.assertIn('InvalidArraySize', logs.output[0])
        self.error('Core C { functions { void f() { int x[1/0]; } } }', 'DivisionByZero')
        self.validate('Core C { architectural_state { extern int x[2147483648]; } }')

    def test_unknown_attribute_suppression_survives_lowering(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'attributes.core_desc'
            path.write_text('Core C { architectural_state { register unsigned<32> PC [[is_pc]]; } functions { void f() [[custom]] {} } }')
            for flags, expected_warning, expected_status in (
                ([], True, 0), (['-Wno-unknown-attribute'], False, 0),
                (['-Werror=unknown-attribute'], True, 1),
            ):
                with self.subTest(flags=flags):
                    output = Path(directory) / ('model_' + str(len(flags)) + '_' + str(expected_status))
                    result = subprocess.run(
                        [sys.executable, '-m', 'm2isar.frontends.coredsl2.parser',
                         *flags, str(path), '--validate', '--output', str(output)],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        timeout=30, check=False)
                    self.assertEqual(result.returncode, expected_status, result.stdout)
                    self.assertNotIn('Traceback', result.stdout)
                    self.assertEqual('Unknown attribute' in result.stdout, expected_warning)
                    self.assertNotIn('unknown attribute "custom" encountered', result.stdout)
                    if expected_status == 0:
                        self.assertTrue((output / 'attributes.m2isarmodel').is_file())

    def test_nonvalidated_builder_keeps_its_legacy_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'attributes.core_desc'
            path.write_text('Core C { functions { void f() [[custom]] {} } }')
            tree = make_parser(path).description_content()
            attribute = tree.definitions[0].sections[0].functions[0].attributes[0]
            with self.assertLogs('arch_builder'):
                self.assertEqual(ArchitectureModelBuilder().visit(attribute)[0], 'custom')
            with self.assertNoLogs('arch_builder'):
                self.assertEqual(ArchitectureModelBuilder(attributes_validated=True).visit(attribute)[0], 'custom')

    def test_malformed_encoding_literal_has_syntax_code(self):
        from m2isar.diagnostics import M2ValidationError
        for attributes in ('', '[[expected_encoding_size(16)]]'):
            with self.subTest(attributes=attributes), self.assertRaises(M2ValidationError) as exc:
                self.validate("Core C { instructions " + attributes + " { I { encoding: 4'hff; behavior: {} } } }")
            self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax')
