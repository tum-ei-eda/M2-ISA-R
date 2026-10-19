"""Parser failures retain legacy catchability and release diagnostic identity."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from m2isar import M2Error, M2SyntaxError
from m2isar.diagnostics import M2ParseError
from m2isar.frontends.coredsl2.utils import make_parser


class ParseDiagnosticTest(unittest.TestCase):
    def test_extern_body(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.core_desc'
            path.write_text('Core C { functions { extern void f() {} } }')
            with self.assertRaises(M2SyntaxError) as exc:
                make_parser(path).description_content()
            error = exc.exception
            self.assertIsInstance(error, M2Error)
            self.assertIsInstance(error, M2ParseError)
            self.assertEqual(error.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax')
            self.assertEqual(error.source_line, 1)
            self.assertGreater(error.source_column, 0)

    def test_frontend_cli_syntax_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.core_desc'
            path.write_text('Core C { functions { extern void f() {} } }')
            for frontend in ('coredsl2', 'coredsl2_set'):
                with self.subTest(frontend=frontend):
                    result = subprocess.run([sys.executable, '-m', 'm2isar.frontends.' + frontend + '.parser', str(path)],
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertIn('org.eclipse.xtext.diagnostics.Diagnostic.Syntax', result.stdout)
                    self.assertNotIn('Traceback', result.stdout)

    def test_lexical_error_is_not_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.core_desc'
            path.write_text('Core C @ {}')
            with self.assertRaises(M2ParseError) as exc:
                make_parser(path).description_content()
            self.assertEqual(exc.exception.issue_code, 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax')
            self.assertIn('token recognition error', str(exc.exception))
