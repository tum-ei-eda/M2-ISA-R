"""Model constant arithmetic keeps release integer semantics."""
import unittest
from m2isar.frontends.coredsl2.expr_interpreter import ExprInterpreterVisitor
from m2isar.metamodel import behav
from m2isar.diagnostics import M2ValidationError


class ConstantLoweringTest(unittest.TestCase):
    def calculate(self, left, op, right):
        return ExprInterpreterVisitor().generate(behav.BinaryOperation(behav.Literal(left), behav.Operator(op), behav.Literal(right)), None)

    def test_integer_division(self):
        for left, right, expected in [(2**100+1, 3, (2**100+1)//3), (-7, 3, -2), (7, -3, -2), (-7, -3, 2)]:
            with self.subTest(left=left, right=right):
                self.assertEqual(self.calculate(left, '/', right), expected)

    def test_negative_shifts(self):
        self.assertEqual(self.calculate(8, '<<', -2), 2)
        self.assertEqual(self.calculate(2, '>>', -2), 8)

    def test_diagnostics(self):
        for op, right, issue in [('/', 0, 'DivisionByZero'), ('%', 2, 'UnsupportedLanguageFeature'), ('&&', 1, 'UnsupportedLanguageFeature')]:
            with self.subTest(op=op):
                with self.assertRaises(M2ValidationError) as exc:
                    self.calculate(3, op, right)
                self.assertEqual(exc.exception.issue_code, 'com.minres.coredsl.' + issue)
