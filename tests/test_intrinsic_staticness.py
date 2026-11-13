"""Unresolved intrinsics must be conservative, rather than treated as functions."""
from types import SimpleNamespace
import unittest
from m2isar.metamodel import behav, attribute_info
from m2isar.metamodel.utils.scalar_staticness import VarAccessVisitor


class IntrinsicStaticness(unittest.TestCase):
    def test_intrinsic_calls_are_dynamic(self):
        for kind in (behav.FunctionCall,behav.ProcedureCall):
            result=VarAccessVisitor().generate(kind('branch',[behav.Literal(1)]),attribute_info.AccessContext())
            self.assertEqual(result,attribute_info.AccessAttribute.NONE)

    def test_named_function_attributes_are_retained(self):
        for kind in (behav.FunctionCall,behav.ProcedureCall):
            fn=SimpleNamespace(attributes={'static':True})
            result=VarAccessVisitor().generate(kind(fn,[]),attribute_info.AccessContext())
            self.assertEqual(result,attribute_info.AccessAttribute.READ)
