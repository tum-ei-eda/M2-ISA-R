# SPDX-License-Identifier: Apache-2.0
"""Lower source-level loop nodes to the canonical :class:`behav.Loop`."""

from functools import singledispatchmethod

from ..metamodel import behav
from ..metamodel.utils.ExprMutator import ExprMutator


class LoopLoweringMutator(ExprMutator):
    """Recursively replace explicit loop kinds with canonical loops."""

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context=None):
        return self.default_visit(expr, context)

    def _lower(self, expr, context):
        self.default_visit(expr, context)
        return behav.Loop(
            expr.cond,
            expr.stmts,
            expr.post_test,
            expr.line_info,
            init=expr.init,
            updates=expr.updates,
        )

    @generate.register
    def _(self, expr: behav.ForLoop, context=None):
        return self._lower(expr, context)

    @generate.register
    def _(self, expr: behav.WhileLoop, context=None):
        return self._lower(expr, context)

    @generate.register
    def _(self, expr: behav.DoWhileLoop, context=None):
        return self._lower(expr, context)


def lower_loops(model_obj):
    """Lower all loops in a model in place and return the model."""
    mutator = LoopLoweringMutator()
    for component in (*model_obj.cores.values(), *model_obj.sets.values()):
        for fn_def in component.functions.values():
            fn_def.operation = mutator.generate(fn_def.operation)
        for always_block in component.always_blocks.values():
            always_block.operation = mutator.generate(always_block.operation)
        for instr_def in component.instructions.values():
            instr_def.operation = mutator.generate(instr_def.operation)
    return model_obj
