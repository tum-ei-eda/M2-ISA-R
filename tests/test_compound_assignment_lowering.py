"""Compound assignments check their source operand and survive saved-model validation."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import test_continue_regression as helpers
import test_isa_alias_parity as harness
from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info
from m2isar.transforms.validate_behav.validate import validate_behav
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsManager

OPERATORS = ('+=','-=','*=','/=','%=','&=','|=','^=','<<=','>>=')
def source(operator):
    return helpers.source('int x=1;int y=2;x'+operator+'y;')

class CompoundAssignmentNativeTest(unittest.TestCase):
    def test_validated_operators_and_saved_cli(self):
        for operator in OPERATORS:
            with self.subTest(operator=operator), tempfile.TemporaryDirectory() as directory:
                model, saved = helpers.parse_model(source(operator), directory, validated=True)
                validate_behav(model, None)
                result = subprocess.run([sys.executable,'-m','m2isar.transforms.validate_behav.validate',str(saved)],
                                        capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertNotIn('Traceback',result.stderr)

    def test_coredsl_emission_retains_compound_operator(self):
        from m2isar.backends.coredsl2.visitor import CDSLWriterVisitor
        import test_source_validator as validator_helpers
        for operator in OPERATORS:
            with self.subTest(operator=operator), tempfile.TemporaryDirectory() as directory:
                model, _ = helpers.parse_model(source(operator), directory, validated=True)
                writer = helpers.CWriter()
                CDSLWriterVisitor().generate(model.cores['C'].functions['f'].operation, writer)
                body = ''.join(writer.parts)
                self.assertIn('x ' + operator + ' y', body)
                validator_helpers.SourceValidatorTest.validate(self, helpers.source(body))

    def test_plain_widening_and_compound_operand_rules(self):
        u8 = type_info.PrimitiveType(type_info.TypeKind.UINT,8)
        u16 = type_info.PrimitiveType(type_info.TypeKind.UINT,16)
        array = type_info.ArrayType(u8,2)
        for compound,target_type,value_type,expected in [
            (False,u8,u8,'InvalidAssignmentType'), (True,u8,u8,None),
            (True,u8,u16,'InvalidAssignmentType'), (True,array,array,'InvalidOperationType')]:
            with self.subTest(compound=compound,target=target_type,value=value_type):
                def reference(name,ty):
                    node = behav.NamedReference(SimpleNamespace(name=name,ty=ty))
                    node.ty = ty
                    return node
                target,value = reference('target',target_type),reference('value',value_type)
                binary = behav.BinaryOperation(target,behav.Operator('+'),value)
                binary.ty = type_info.PrimitiveType(type_info.TypeKind.UINT,17 if value_type is u16 else 9)
                assignment = behav.Assignment(target,binary)
                if compound: assignment.compound_operator = '+='
                if expected:
                    with self.assertRaises(M2ValidationError) as caught:
                        ValidateBehavVisitor().generate(assignment,WarningsManager(None))
                    self.assertEqual(caught.exception.issue_code,'com.minres.coredsl.'+expected)
                else:
                    ValidateBehavVisitor().generate(assignment,WarningsManager(None))

@unittest.skipUnless(os.environ.get('COREDSL_VALIDATOR_JAR'),'Set COREDSL_VALIDATOR_JAR for differential tests')
class CompoundAssignmentOracleTest(unittest.TestCase):
    probe = harness.IsaAliasOracleTest.probe
    def test_release_valid_operators(self):
        for operator in OPERATORS:
            with self.subTest(operator=operator):
                output,_ = self.probe(source(operator))
                self.assertNotIn('ERROR:',output)
    def test_release_plain_widening_is_rejected(self):
        output,_ = self.probe(helpers.source('unsigned<8> x=0;unsigned<8> y=1;x=x+y;'))
        self.assertEqual(output.count('ERROR:'),1,output)
        self.assertIn('Cannot implicitly convert',output)
