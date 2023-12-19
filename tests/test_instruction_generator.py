import pytest
from m2isar.frontends.gen_custom_insns.instructions_classes import InstructionCollection, Instruction
from m2isar.frontends.gen_custom_insns.operands import Operand, ComplexOperand, simplify_operands
from m2isar.metamodel import behav


def test_add_generation():
    instr1 = InstructionCollection(
        name="addN{rs1.sign}{rs1.width}",
        ops="addN",
        operands={
            "rs1": ComplexOperand(width=[16, 32], sign="s", immediate=False),
            "rs2": ComplexOperand(width="rs1", sign="rs1", immediate=False),
            "rd": ComplexOperand(width=32, sign="s"),
        },
    )
    instr2 = instr1.generate()
    assert instr2[0] == Instruction(
        name="addNs16",
        op="addN",
        operands={
            "rs1": Operand(width=16, sign="s"),
            "rs2": Operand(width=16, sign="s"),
            "rd": Operand(32, "s"),
        },
    )
    assert instr2[1] == Instruction(
        name="addNs32",
        op="addN",
        operands={
            "rs1": Operand(width=32, sign="s"),
            "rs2": Operand(width=32, sign="s"),
            "rd": Operand(32, "s"),
        },
    )


def test_sign_width_matching():
    c_opr = ComplexOperand(width=[16, 32], sign=["u", "s"])
    _ = simplify_operands({"rs1": c_opr})


def test_sign_width_missmatch():
    c_opr = ComplexOperand(width=[8, 16, 32], sign=["u", "s"])
    with pytest.raises(ValueError):
        simplify_operands({"rs1": c_opr})


def test_metamodel_translation():
    instr = Instruction(
        name="addNs32",
        op="addN",
        operands={
            "rs1": Operand(width=32, sign="s"),
            "rs2": Operand(width=32, sign="s"),
            "ls3": Operand(width=3, sign="u"),
            "rd": Operand(32, "s"),
        },
    )

    mm = instr.to_metamodel()

    assert isinstance(mm.operation, behav.Operation)
