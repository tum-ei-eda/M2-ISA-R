"""Literal casts keep their type and release constant-expression provenance."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_isa_alias_parity as harness


CASES = [
    ("unsigned<4> f() { return (unsigned<4>)8'hff; }", None),
    ("signed<8> f() { return (signed)8'hff; }", None),
    ("unsigned<8> f() { return (unsigned)8'shff; }", None),
    ("void f() { unsigned<4> x=(signed<4>)4'd1; }", 'InvalidAssignmentType'),
    ("void f() { unsigned<4> x=(unsigned<8>)8'd1; }", 'InvalidAssignmentType'),
    ("void f() { signed<8> x=(signed<8>)8'd1; }", None),
]


class LiteralCastPreservationNativeTest(unittest.TestCase):
    def test_saved_literal_casts_match_source_conversion_rules(self):
        for frontend, root in (('coredsl2', 'Core'), ('coredsl2_set', 'InstructionSet')):
            for body, issue in CASES:
                with self.subTest(frontend=frontend, body=body), tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'literal_cast.core_desc'
                    path.write_text(root + ' C { functions { ' + body + ' } }')
                    parsed = subprocess.run(
                        [sys.executable, '-m', f'm2isar.frontends.{frontend}.parser', str(path)],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(parsed.returncode, 0, parsed.stdout)
                    checked = subprocess.run(
                        [sys.executable, '-m', 'm2isar.transforms.validate_behav.validate',
                         str(Path(directory) / 'gen_model' / 'literal_cast.m2isarmodel'),
                         '-Wno-error=implicit-trunc'],
                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    self.assertEqual(checked.returncode, int(issue is not None), checked.stdout)
                    if issue:
                        self.assertIn('com.minres.coredsl.' + issue, checked.stdout)
                    self.assertNotIn('Traceback', checked.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class LiteralCastPreservationOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe

    def test_release_literal_cast_conversions(self):
        for body, issue in CASES:
            with self.subTest(body=body):
                output, _ = self.probe('Core C { functions { ' + body + ' } }')
                self.assertEqual(output.count('ERROR:'), int(issue is not None), output)
                if issue:
                    self.assertIn('ERROR:Cannot implicitly convert', output)
