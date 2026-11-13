"""Operand inference traverses local array tensors."""
import unittest
from types import SimpleNamespace

from m2isar.metamodel import arch, attribute_info, behav, type_info
from m2isar.transforms.infer_operands import infer_operands


class InferOperandsTensorTest(unittest.TestCase):
    def test_local_tensor_without_initializer_is_ignored(self):
        tensor = behav.Tensor(
            [0],
            type_info.ArrayType(type_info.PrimitiveType(type_info.TypeKind.UINT, 32), 1),
        )
        instruction = SimpleNamespace(
            name="LOCALARRAY",
            operation=behav.Operation([tensor]),
            fields={},
            operands={},
        )

        self.assertIs(infer_operands(instruction), instruction)

    def test_tensor_initializer_references_are_analyzed(self):
        field = arch.BitFieldDescr("rs1", 5, type_info.TypeKind.UINT)
        tensor = behav.Tensor(
            [0],
            type_info.ArrayType(type_info.PrimitiveType(type_info.TypeKind.UINT, 32), 1),
            initializer_elements=[behav.NamedReference(field)],
        )
        instruction = SimpleNamespace(
            name="LOCALARRAY",
            operation=behav.Operation([tensor]),
            fields={"rs1": field},
            operands={},
        )

        infer_operands(instruction)

        operand = instruction.operands["rs1"]
        self.assertIn(attribute_info.OperandAttribute.IN, operand.attributes)
        self.assertIn(attribute_info.OperandAttribute.IS_IMM, operand.attributes)


if __name__ == "__main__":
    unittest.main()
