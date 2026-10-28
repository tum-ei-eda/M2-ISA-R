"""PR #122 severity controls survive frontend and saved-model CLI paths."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class WarningDemotionCliTest(unittest.TestCase):
    def run_cli(self, module, arguments):
        result = subprocess.run([sys.executable, '-m', module, *arguments],
                                capture_output=True, text=True, timeout=30)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def test_all_four_cli_entry_points_accept_demotion(self):
        for module in ('m2isar.frontends.coredsl2.parser', 'm2isar.frontends.coredsl2_set.parser',
                       'm2isar.transforms.infer_types.transform', 'm2isar.transforms.validate_behav.validate'):
            with self.subTest(module=module):
                result = self.run_cli(module, ['-Werror', '-Wno-error=implicit-trunc', '--help'])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('demotewith-Wno-error=foo', ''.join(result.stdout.split()))

    def test_default_truncation_and_demotion_through_saved_model(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'truncation.core_desc'
            source.write_text("Core C {functions{void f(){unsigned<4> x=8'd3;}}}")
            parsed = self.run_cli('m2isar.frontends.coredsl2.parser', [str(source)])
            self.assertEqual(parsed.returncode, 0, parsed.stderr)
            model = source.parent / 'gen_model' / 'truncation.m2isarmodel'
            for flags, status, severity in (([], 1, 'ERROR:'),
                                            (['-Wno-error=implicit-trunc'], 0, 'WARNING:'),
                                            (['-Wno-implicit-trunc'], 0, None)):
                with self.subTest(flags=flags):
                    result = self.run_cli('m2isar.transforms.validate_behav.validate', [str(model), *flags])
                    self.assertEqual(result.returncode, status, result.stderr)
                    if severity:
                        self.assertIn(severity + 'validate_behav:', result.stderr)
                        self.assertIn('[-Wimplicit-trunc]', result.stderr)
                    else:
                        self.assertNotIn('[-Wimplicit-trunc]', result.stderr)

    def test_unknown_attribute_demotion_keeps_the_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'attributes.core_desc'
            source.write_text('Core C {functions{void f() [[custom]] {}}}')
            for flags, status in ((['-Werror=unknown-attribute'], 1),
                                  (['-Werror=unknown-attribute', '-Wno-error=unknown-attribute'], 0)):
                with self.subTest(flags=flags):
                    result = self.run_cli('m2isar.frontends.coredsl2.parser', [str(source), '--validate', *flags])
                    self.assertEqual(result.returncode, status, result.stderr)
                    self.assertIn('[-Wunknown-attribute]', result.stderr)
                    self.assertIn('com.minres.coredsl.UnknownAttribute', result.stderr)
