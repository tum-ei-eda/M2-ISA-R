# SPDX-License-Identifier: Apache-2.0
"""Lower always blocks into instruction behavior for legacy backends."""

from ..metamodel import behav


def merge_always_blocks(model_obj):
    """Prepend each model component's always blocks to all its instructions.

    The transform mutates and returns ``model_obj``.  It is idempotent: consumed
    always blocks are removed after lowering.
    """
    for component in (*model_obj.cores.values(), *model_obj.sets.values()):
        always_blocks = getattr(component, "always_blocks", {})
        if not always_blocks:
            continue
        # Python's sort is stable, so blocks with equal (or default) order
        # retain their declaration/parser order.
        ordered_blocks = sorted(always_blocks.values(), key=lambda block: block.order)
        prefix = [block.operation for block in ordered_blocks]
        for instr in component.instructions.values():
            instr.operation.statements = prefix + instr.operation.statements
        component.always_blocks = {}
    return model_obj
