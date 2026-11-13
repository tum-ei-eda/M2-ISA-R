# SPDX-License-Identifier: Apache-2.0

"""Source locations for CoreDSL2 parse contexts."""

from ...metamodel.code_info import LineInfoFactory


def line_info(ctx, *, placement=None):
    """Create source location metadata for a parse context."""
    args = (ctx.start.source[1].fileName, ctx.start.start, ctx.stop.stop,
            ctx.start.line, ctx.stop.line)
    return LineInfoFactory.make(*args, **({'placement': placement} if placement is not None else {}))
