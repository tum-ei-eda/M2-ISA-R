"""Retain structural evidence that execution simplification can erase."""
from .. import behav


def stray_break_locations(statement, loop_depth=0):
    if isinstance(statement, behav.Break):
        return [statement.line_info] if loop_depth == 0 else []
    if isinstance(statement, behav.Operation):
        children = statement.statements
    elif isinstance(statement, behav.Conditional):
        children = statement.stmts
    elif isinstance(statement, behav.Loop):
        children = statement.stmts
        loop_depth += 1
    else:
        return []
    return [location for child in children for location in stray_break_locations(child, loop_depth)]


def stray_control_flow_locations(statement, loop_depth=0):
    if isinstance(statement, (behav.Break, behav.Continue)):
        kind = 'break' if isinstance(statement, behav.Break) else 'continue'
        return [(kind, statement.line_info)] if loop_depth == 0 else []
    if isinstance(statement, behav.Operation):
        children = statement.statements
    elif isinstance(statement, behav.Conditional):
        children = statement.stmts
    elif isinstance(statement, behav.Loop):
        children = statement.stmts
        loop_depth += 1
    else:
        return []
    return [entry for child in children for entry in stray_control_flow_locations(child, loop_depth)]


def preserve_break_scope(operation):
    if not hasattr(operation, '_stray_control_flow_locations'):
        locations = stray_control_flow_locations(operation)
        if hasattr(operation, '_stray_break_locations'):
            # Older inferred models may have folded away their break nodes.
            locations = [('break', location) for location in operation._stray_break_locations] + [
                entry for entry in locations if entry[0] == 'continue']
            if all(location is not None for _, location in locations):
                locations.sort(key=lambda entry: (entry[1].start_line_no, entry[1].start_chr))
        operation._stray_control_flow_locations = locations
    if not hasattr(operation, '_stray_break_locations'):
        operation._stray_break_locations = stray_break_locations(operation)
    if not hasattr(operation, '_stray_continue_locations'):
        operation._stray_continue_locations = stray_continue_locations(operation)


def stray_continue_locations(statement, loop_depth=0):
    if isinstance(statement, behav.Continue):
        return [statement.line_info] if loop_depth == 0 else []
    if isinstance(statement, behav.Operation):
        children = statement.statements
    elif isinstance(statement, behav.Conditional):
        children = statement.stmts
    elif isinstance(statement, behav.Loop):
        children = statement.stmts
        loop_depth += 1
    else:
        return []
    return [location for child in children for location in stray_continue_locations(child, loop_depth)]


def lower_for_continues(statement, updates):
    """Execute for-loop updates before continues belonging to this loop."""
    if isinstance(statement, behav.Continue):
        return behav.Block([*updates, statement], statement.line_info)
    if isinstance(statement, behav.Loop):
        return statement  # Nested loops own their continues.
    if isinstance(statement, behav.Operation):
        statement.statements = [lower_for_continues(child, updates) for child in statement.statements]
    elif isinstance(statement, behav.Conditional):
        statement.stmts = [lower_for_continues(child, updates) for child in statement.stmts]
    return statement
