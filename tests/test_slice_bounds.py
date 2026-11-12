"""Statically out-of-bounds bit slices are rejected by the behavior validator."""
import unittest

from m2isar.diagnostics import M2ValidationError
from m2isar.metamodel import behav, type_info
from m2isar.transforms.validate_behav.visitor import ValidateBehavVisitor
from m2isar.warnings import WarningsInfo, WarningsManager


def literal(value, kind=type_info.TypeKind.UINT, size=8):
    return behav.Literal(value, type_info.PrimitiveType(kind, size))


def operand():
    return literal(0xFF)


class SliceBoundsTest(unittest.TestCase):
    def validate(self, node):
        ValidateBehavVisitor().generate(node, WarningsManager(WarningsInfo()))

    def slice(self, left, right):
        return behav.SliceOperation(operand(), literal(left), literal(right))

    def test_valid_slices(self):
        for left, right in ((7, 0), (3, 0), (7, 7)):
            with self.subTest(left=left, right=right):
                self.validate(self.slice(left, right))

    def test_out_of_bounds_slices(self):
        for left, right in ((8, 0), (10, 0), (0, 10)):
            with self.subTest(left=left, right=right):
                with self.assertRaises(M2ValidationError) as caught:
                    self.validate(self.slice(left, right))
                self.assertIn('exceeds operand width of 8 bits (valid range: [7:0])', str(caught.exception))

    def test_cast_does_not_suppress(self):
        cast = behav.TypeConv(type_info.TypeKind.UINT, 8, self.slice(10, 0))
        with self.assertRaises(M2ValidationError):
            self.validate(cast)
        self.validate(behav.TypeConv(type_info.TypeKind.UINT, 8, operand()))


if __name__ == '__main__':
    unittest.main()
