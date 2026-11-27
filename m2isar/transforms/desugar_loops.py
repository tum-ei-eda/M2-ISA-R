# SPDX-License-Identifier: Apache-2.0
"""Desugar source-level loop forms into canonical loops and operations."""

from functools import singledispatchmethod

from ..metamodel import behav
from ..metamodel.utils.ExprMutator import ExprMutator
from ..metamodel.utils.control_flow import lower_for_continues


class LoopDesugaringMutator(ExprMutator):
    """Expand ``for`` clauses while retaining a canonical loop node."""

    @singledispatchmethod
    def generate(self, expr: behav.BaseNode, context=None):
        return self.default_visit(expr, context)

    @generate.register
    def _(self, expr: behav.ForLoop, context=None):
        # Process nested loops first so their own continue statements remain
        # owned by those loops when this loop's updates are inserted.
        self.default_visit(expr, context)
        body = expr.body
        body.statements = [
            lower_for_continues(statement, expr.updates)
            for statement in body.statements
        ] + list(expr.updates)
        loop = behav.Loop(expr.cond, [body], False, expr.line_info)
        # The surrounding block preserves the lexical scope of declarations
        # made in a for initializer.
        return behav.Block([*expr.init, loop], expr.line_info)

    @generate.register
    def _(self, expr: behav.WhileLoop, context=None):
        self.default_visit(expr, context)
        return behav.Loop(expr.cond, expr.stmts, False, expr.line_info)

    @generate.register
    def _(self, expr: behav.DoWhileLoop, context=None):
        self.default_visit(expr, context)
        return behav.Loop(expr.cond, expr.stmts, True, expr.line_info)


def desugar_loops(model_obj):
    """Desugar source loop kinds in place and return ``model_obj``.

    A ``for`` loop becomes a lexical block containing its initializers and a
    pre-tested canonical loop. Updates run at the latch and before continues
    targeting that loop. ``while`` and ``do-while`` become canonical loops.
    Run this after analyses that depend on the source loop structure.
    """
    mutator = LoopDesugaringMutator()
    for component in (*model_obj.cores.values(), *model_obj.sets.values()):
        for fn_def in component.functions.values():
            fn_def.operation = mutator.generate(fn_def.operation)
        for always_block in component.always_blocks.values():
            always_block.operation = mutator.generate(always_block.operation)
        for instr_def in [*component.instructions.values(), *component.unencoded_instructions.values()]:
            instr_def.operation = mutator.generate(instr_def.operation)
    return model_obj
