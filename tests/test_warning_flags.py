import argparse
import contextlib
import io
import unittest

from m2isar.warnings import add_warnings_flags, KNOWN_WARNINGS, WarningsManager


class WarningFlagsTest(unittest.TestCase):
    def setUp(self):
        self.parser = argparse.ArgumentParser()
        add_warnings_flags(self.parser, KNOWN_WARNINGS, KNOWN_WARNINGS)

    def parse(self, *flags):
        return self.parser.parse_args(flags).warnings

    def test_enable_disable_order(self):
        info = self.parse('-Wno-implicit-trunc', '-Wimplicit-trunc')
        self.assertIn('implicit-trunc', info.warnings)
        info = self.parse('-Wimplicit-trunc', '-Wno-implicit-trunc')
        self.assertNotIn('implicit-trunc', info.warnings)

    def test_parser_defaults_do_not_leak(self):
        self.parse('-Wno-implicit-trunc', '-Werror')
        info = self.parse()
        self.assertIn('implicit-trunc', info.warnings)
        self.assertFalse(info.all_as_error)

    def test_unknown_warning_is_cli_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exc:
            self.parse('-Wunknown')
        self.assertEqual(exc.exception.code, 2)

    def test_specific_error_enables_warning(self):
        info = self.parse('-Wno-implicit-trunc', '-Werror=implicit-trunc')
        with self.assertLogs(level='ERROR'), self.assertRaises(RuntimeError):
            WarningsManager(info).emit_warning('Truncation', 'implicit-trunc')

    def test_suppression_and_no_error(self):
        info = self.parse('-Werror', '-Wno-error', '-Wno-shift-signed')
        self.assertFalse(info.all_as_error)
        self.assertNotIn('shift-signed', info.warnings)
        self.assertIn('implicit-trunc', info.warnings)

    def test_all_after_disable(self):
        self.assertEqual(self.parse('-Wno-shift-signed', '-Wall').warnings, KNOWN_WARNINGS)

    def test_flags_before_positional_input(self):
        self.parser.add_argument('top_level')
        args = self.parser.parse_args(['-Wno-shift-signed', 'independent.core_desc'])
        self.assertEqual(args.top_level, 'independent.core_desc')
        self.assertNotIn('shift-signed', args.warnings.warnings)

    def test_promoted_warning_has_structured_identity(self):
        from m2isar import M2Error
        from m2isar.diagnostics import M2WarningError
        info = self.parse('-Werror=unknown-attribute')
        with self.assertLogs(level='ERROR'), self.assertRaises(M2WarningError) as exc:
            WarningsManager(info).emit_warning('Unknown attribute', 'unknown-attribute')
        self.assertIsInstance(exc.exception, M2Error)
        self.assertIsInstance(exc.exception, RuntimeError)
        self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.UnknownAttribute')
