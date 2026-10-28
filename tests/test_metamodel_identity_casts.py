"""Standalone identity warnings follow strict mode and CLI warning policy."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_semantic_parity as oracle
from test_metamodel_casts import INT, cast, model
from test_metamodel_conditions import condition
from test_source_statement_collection import codes
from m2isar.diagnostics import M2ValidationError, M2WarningError
from m2isar.metamodel import arch, behav, type_info
from m2isar.transforms.validate_behav.validate import ValidatorContext, validate_behav
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsInfo


SOURCE = 'functions { signed<32> f(signed<32> x) { return (signed)x; } }'


class MetamodelIdentityCastNativeTest(unittest.TestCase):
    def test_known_identity_and_nonidentity_controls(self):
        for source in (INT, type_info.PrimitiveType(type_info.TypeKind.UINT, 32)):
            for target, width in ((source.kind, None), (source.kind, 32),
                                  (type_info.TypeKind.UINT if source.kind == type_info.TypeKind.INT
                                   else type_info.TypeKind.INT, 32), (source.kind, 16)):
                identity = target == source.kind and width in (None, 32)
                with self.subTest(source=source, target=target, width=width):
                    expr = cast(condition(source), width, target)
                    context = ValidatorContext(WarningsInfo(enabled={'identity-cast'}))
                    if identity:
                        with self.assertLogs('validate_behav', level='WARNING') as logs:
                            ValidateBehavVisitor().generate(expr, context)
                        self.assertEqual(sum('com.minres.coredsl.IdentityCast' in line
                                             for line in logs.output), 1)
                    else:
                        with self.assertNoLogs('validate_behav', level='WARNING'):
                            ValidateBehavVisitor().generate(expr, context)

    def test_disabled_unknown_and_source_validated_contexts(self):
        for source in (INT, None, type_info.PointerType(INT)):
            with self.subTest(source=source), self.assertNoLogs('validate_behav', level='WARNING'):
                ValidateBehavVisitor().generate(cast(condition(source), 32), ValidatorContext(WarningsInfo()))
        saved = model(cast(condition(INT), None))
        policy = WarningsInfo(enabled={'identity-cast'})
        with self.assertNoLogs('validate_behav', level='WARNING'):
            validate_behav(saved, policy, source_validated=True)
        with self.assertLogs('validate_behav', level='WARNING') as logs:
            validate_behav(saved, policy)
        self.assertEqual(sum('com.minres.coredsl.IdentityCast' in line for line in logs.output), 1)

    def test_promotion_and_existing_child_error(self):
        policy = WarningsInfo(enabled={'identity-cast'}, as_error={'identity-cast'})
        with self.assertLogs('validate_behav', level='ERROR'):
            with self.assertRaises(M2WarningError) as caught:
                ValidateBehavVisitor().generate(cast(condition(INT), None), ValidatorContext(policy))
        self.assertEqual(caught.exception.issue_code, 'com.minres.coredsl.IdentityCast')
        function = arch.Function('g', {}, 32, type_info.TypeKind.INT, [], None, extern=True)
        for promoted in (False, True):
            with self.subTest(promoted=promoted):
                child = behav.FunctionCall(function, [behav.Literal(1)])
                child.ty = INT
                warning_policy = policy if promoted else WarningsInfo(enabled={'identity-cast'})
                with self.assertLogs('validate_behav', level='WARNING') as logs:
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(cast(child, None), ValidatorContext(warning_policy))
                expected = ['InvalidArgumentCount'] + (['IdentityCast'] if promoted else [])
                self.assertEqual(codes(caught.exception), expected)
                self.assertEqual(sum('com.minres.coredsl.IdentityCast' in line for line in logs.output), 1)

    def test_frontend_and_saved_model_warning_policy(self):
        policies = [([], 0, 0), (['-Widentity-cast'], 0, 1), (['-Wall'], 0, 1),
                    (['-Werror=identity-cast'], 1, 1),
                    (['-Werror=identity-cast', '-Wno-error=identity-cast'], 0, 1)]
        for frontend, root in (('coredsl2', 'Core'), ('coredsl2_set', 'InstructionSet')):
            with self.subTest(frontend=frontend), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'identity.core_desc'
                path.write_text(root + ' C { ' + SOURCE + ' }')
                parsed = subprocess.run([sys.executable, '-m', f'm2isar.frontends.{frontend}.parser', str(path)],
                                        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(parsed.returncode, 0, parsed.stdout)
                saved = Path(directory) / 'gen_model' / 'identity.m2isarmodel'
                for flags, status, warnings in policies:
                    for command in ([sys.executable, '-m', 'm2isar.transforms.validate_behav.validate', str(saved)],
                                    [sys.executable, '-m', f'm2isar.frontends.{frontend}.parser', str(path), '--validate']):
                        with self.subTest(flags=flags, command=command[2]):
                            checked = subprocess.run(command + flags, text=True,
                                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                            self.assertEqual(checked.returncode, status, checked.stdout)
                            # A promoted warning is also printed by the CLI's final error report.
                            count = checked.stdout.count('Identity cast does nothing')
                            self.assertEqual(count, warnings + int(status != 0), checked.stdout)
                            self.assertNotIn('Traceback', checked.stdout)


@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),
                     'Set COREDSL_VALIDATOR_JAR for differential tests')
class MetamodelIdentityCastOracleTest(unittest.TestCase):
    probe = oracle.SemanticParityTest.probe

    def test_release_strict_mode(self):
        for strict in (False, True):
            for body, count in ((SOURCE, 1),
                                ('functions { signed<32> f(unsigned<32> x) { return (signed)x; } }', 0),
                                ('functions { int g() { return 0; } void f() { int x=(signed)g(1); } }', 1)):
                with self.subTest(strict=strict, body=body):
                    output, _ = self.probe('Core C { ' + body + ' }', strict=strict)
                    self.assertEqual(output.count('WARNING:Identity cast does nothing'),
                                     count if strict else 0, output)
