import argparse
import logging
from copy import deepcopy
from .diagnostics import WARNING_ISSUES, M2WarningError
from dataclasses import dataclass, field
from typing import Set

KNOWN_WARNINGS = {
	'duplicate-isa-state-element',
	'index-out-of-range',
	'size-of-not-exact',
	'identity-cast',
	'unknown-attribute',
	'unexpected-instruction-size',
	'array-size-zero',
	'invalid-array-size',
	'unreachable-code',
	'likely-accidental-assignment',
	'implicit-trunc',
	'shift-overflow',
	'shift-signed',
	'implicit-extend',
	'sign-compare',
	'unused-value',
	'bit-op-missmatch',
	'infer-non-static-slice',
	'incomplete-type-info',
	'infer-type',
}


# IdentityCast is guarded by -Dstrict=true in the reference validator.
DEFAULT_WARNINGS = KNOWN_WARNINGS - {'identity-cast'}
DEFAULT_ERRORS = {'implicit-trunc'}


@dataclass
class WarningsInfo:
	# known: Set[str] = field(default_factory=set)
	known: Set[str] = field(default_factory=lambda: set(KNOWN_WARNINGS))
	# defaults: Set[str] = field(default_factory=set)
	defaults: Set[str] = field(default_factory=lambda: set(DEFAULT_WARNINGS))
	enabled: Set[str] = field(default_factory=set)
	disabled: Set[str] = field(default_factory=set)
	as_error: Set[str] = field(default_factory=set)
	all_as_error: bool = False
	default_as_error: Set[str] = field(default_factory=lambda: set(DEFAULT_ERRORS))
	not_as_error: Set[str] = field(default_factory=set)

	@property
	def warnings(self):
		return (self.defaults - self.disabled) | self.enabled

	@property
	def errors(self):
		fatal = self.warnings if self.all_as_error else (
			getattr(self, 'default_as_error', DEFAULT_ERRORS) | self.as_error)
		return fatal - getattr(self, 'not_as_error', set())


class WarningFlagAction(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		# argparse reuses defaults; never mutate the parser's default object.
		warnings_info = deepcopy(getattr(namespace, 'warnings', None))
		if warnings_info is None:
			warnings_info = WarningsInfo()
		for val in values:
			if val == 'no-error':
				warnings_info.all_as_error = False
			elif val == 'error':
				warnings_info.all_as_error = True
			elif val == 'all':
				warnings_info.enabled.update(warnings_info.known)
				warnings_info.disabled.clear()
			else:
				demote = val.startswith('no-error=')
				disable = val.startswith('no-')
				promote = val.startswith('error=')
				warn = val[9:] if demote else val[3:] if disable else val[6:] if promote else val
				if warn not in warnings_info.known:
					raise argparse.ArgumentError(self, f"Unknown warning: {warn}")
				if demote:
					warnings_info.not_as_error.add(warn)
					warnings_info.as_error.discard(warn)
				elif disable:
					warnings_info.disabled.add(warn)
					warnings_info.enabled.discard(warn)
				else:
					warnings_info.enabled.add(warn)
					warnings_info.disabled.discard(warn)
					if promote:
						warnings_info.as_error.add(warn)
						warnings_info.not_as_error.discard(warn)
		setattr(namespace, 'warnings', warnings_info)


def add_warnings_flags(
	parser,
	known_warnings: Set[str],
	default_warnings: Set[str],
	default_errors: Set[str] = None,
):
	parser.add_argument(
		'-W',
		dest='warnings',
		metavar='warning',
		action=WarningFlagAction,
		nargs=1,
		help=(
			"Enable/disable warnings like -Wfoo or -Wno-foo; "
			"Make fatal with -Werror or -Werror=foo; demote with -Wno-error=foo. "
			"Implicit truncation is fatal by default."
		),
	)

	# Defaults
	warnings_info = WarningsInfo(
		known=set(known_warnings), defaults=set(default_warnings),
		default_as_error=set(DEFAULT_ERRORS & known_warnings if default_errors is None else default_errors))
	parser.set_defaults(warnings=warnings_info)


class WarningsManager:
	def __init__(self, warnings_info: WarningsInfo):
		self.warnings_info = warnings_info

	def emit_warning(self, msg, name=None, logger=None, line_info=None):
		log_warn_f = logging.warning if logger is None else logger.warning
		log_err_f = logging.error if logger is None else logger.error
		if self.warnings_info is None:
			return  # ignore
		assert name in self.warnings_info.known, f"Unknown warning: {name}"
		is_err = name in self.warnings_info.errors
		if name not in self.warnings_info.warnings:
			# do nothing
			return
		log_f = log_err_f if is_err else log_warn_f
		if name is not None:
			msg += f" [-W{name}]"
		if name in WARNING_ISSUES:
			msg += f" [com.minres.coredsl.{WARNING_ISSUES[name]}]"
		if line_info is not None:
			line_info_str = f"{line_info.file_path}:{line_info.start_line_no}"
			msg += f" @ {line_info_str}"
		log_f(msg)
		if is_err:
			raise M2WarningError(msg, name, line_info)
