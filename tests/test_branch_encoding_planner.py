"""B-format planning preserves signed byte offsets and encoding reservations."""
import unittest
from m2isar.metamodel.attribute_info import InstrAttribute, OperandAttribute as A
from m2isar.transforms.encode_instructions import EncodingPolicy, plan_encodings, apply_encoding_plan
from test_encoding_planner import instruction, operand, add


def branch(name='BRANCH', width=13, signed=True):
    offset=operand('offset',width,A.IS_IMM,signed=signed)
    offset.attributes[A.IS_BRANCH_OFFS]=[]
    result=instruction(name,operand('rs1'),operand('rs2'),offset)
    result.attributes[InstrAttribute.COND]=[]
    return result


class BranchEncodingPlanner(unittest.TestCase):
    def test_round_trip_all_even_displacements(self):
        instr=branch();plan=plan_encodings([instr]);plan.raise_for_errors()
        a=plan.assignments[0];self.assertEqual(a.layout,'B')
        for offset in range(-4096,4096,2):
            values={'rs1':10,'rs2':31,'offset':offset&8191};word=a.code
            for f in a.fields:word|=((values[f.name]>>f.source_lower)&((1<<f.width)-1))<<f.offset
            raw=((word>>31)&1)<<12 | ((word>>25)&63)<<5 | ((word>>8)&15)<<1 | ((word>>7)&1)<<11
            decoded=raw-8192 if raw&4096 else raw
            self.assertEqual(decoded,offset)
            self.assertEqual(word&a.mask,a.code)
        encoded=apply_encoding_plan([instr],plan)[0]
        self.assertEqual(encoded.operands['offset'].size,13)
        self.assertTrue(encoded.operands['offset'].signed)

    def test_branch_and_arithmetic_are_disjoint_and_pinnable(self):
        instructions=[branch(),add()];plan=plan_encodings(instructions);plan.raise_for_errors()
        a,b=plan.assignments
        self.assertNotEqual((a.code^b.code)&a.mask&b.mask,0)
        self.assertEqual(plan,plan_encodings(instructions,assignments=plan.to_dict()))

    def test_reject_invalid_branch_shapes(self):
        for width,signed in ((12,True),(13,False),(14,True)):
            self.assertTrue(plan_encodings([branch(width=width,signed=signed)]).errors)
        b=branch();b.operands['rd']=operand('rd',direction=A.OUT)
        self.assertTrue(plan_encodings([b]).errors)
        b=branch();b.attributes={}
        self.assertTrue(plan_encodings([b]).errors)

    def test_shared_capacity(self):
        plan=plan_encodings([branch(f'B{i}') for i in range(9)],policy=EncodingPolicy(opcodes=(0x0b,)))
        self.assertTrue(plan.errors) # Only eight funct3 values for two-register B format.
