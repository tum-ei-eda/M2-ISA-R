"""Stable issue identifiers shared with the MINRES CoreDSL validator."""
from . import M2Error, M2SyntaxError


class M2ValidationError(M2Error):
    def __init__(self, message, issue, line_info=None):
        self.issue_code = (issue if issue.startswith('org.eclipse.') else
                           'com.minres.coredsl.' + issue)
        self.line_info = line_info
        self.related_diagnostics = []
        location = '' if line_info is None else (
            f' @ {line_info.file_path}:{line_info.start_line_no}')
        super().__init__(f'{message} [{self.issue_code}]{location}')

    def __str__(self):
        return '\n'.join([super().__str__(), *(str(item) for item in self.related_diagnostics)])


class M2ParseError(M2SyntaxError):
    """Frontend syntax diagnostic retaining legacy SyntaxError identity."""
    issue_code = 'org.eclipse.xtext.diagnostics.Diagnostic.Syntax'

    def __init__(self, message, filename=None, line=None, column=None):
        self.file_path = filename
        self.source_line = line
        self.source_column = column
        super().__init__(f"Syntax error in file {filename}, line {line}, column {column}: {message} [{self.issue_code}]")


WARNING_ISSUES = {
    'duplicate-isa-state-element': 'DuplicateIsaStateElement',
    'index-out-of-range': 'IndexOutOfRange',
    'size-of-not-exact': 'SizeOfNotExact',
    'identity-cast': 'IdentityCast',
    'unknown-attribute': 'UnknownAttribute',
    'unexpected-instruction-size': 'UnexpectedInstructionSize',
    'array-size-zero': 'ArraySizeIsZero',
    'invalid-array-size': 'InvalidArraySize',
    'shift-overflow': 'ShiftAlwaysZero',
    'unreachable-code': 'UnreachableCode',
    'likely-accidental-assignment': 'LikelyAccidentalAssignment',
}


class M2WarningError(RuntimeError, M2Error):
    """A promoted warning, catchable as both a legacy RuntimeError and M2Error."""
    def __init__(self, message, name, line_info=None):
        self.warning_name = name
        self.line_info = line_info
        issue = WARNING_ISSUES.get(name)
        self.issue_code = None if issue is None else 'com.minres.coredsl.' + issue
        super().__init__(message)
