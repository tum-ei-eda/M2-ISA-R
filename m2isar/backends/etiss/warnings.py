import argparse
from dataclasses import dataclass
from typing import Set

KNOWN_WARNINGS = {
	'implicit-trunc',
	'shift-outofrange',
	'implicit-extend',
	'signed-compare',
	'unused-value',
}


@dataclass
class WarningsInfo:
	known: Set[str] = default
	defaults: Set[str] = {}
	enabled: Set[str] = {}
	disabled: Set[str] = {}
	as_error: Set[str] = {}
	all_as_error: bool = False

	@property
	def warnings(self):
		return self.defaults - self.disabled + self.enabled

	@property
	def errors(self):
		return self.as_error if not self.all_as_error else self.warnings


class WarningFlagAction(argparse.Action):
	def __call__(self, parser, namespace, values, option_string=None):
		warnings_info = getattr(namespace, 'warnings_info', WarningsInfo())

		for val in values:
			if val.startswith('no-'):
				warn = val[3:]
				assert warn in warnings_info.known, f"Unknown warning: {warn}"
				disabled.add(warn)
			elif val.startswith('error='):
				warn = val[6:]
				assert warn in warnings_info.known, f"Unknown warning: {warn}"
				error_set.add(warn)
			elif val == 'error':
				all_as_error = True
			elif val == 'all':
				warnings_info.enabled.update(warnings_info.known)
			else:
				assert warn in warnings_info.known, f"Unknown warning: {val}"
				enabled.add(val)
			# No need for -Wall as all warnings are enabled by default

		setattr(namespace, 'warnings_info', warnings_info)

def add_warnings_flags(parser, known_warnings: Set[str], default_warnings: Set[str]):
	parser.add_argument(
		'-W',
		dest='warnings',
		metavar='warning',
		action=WarningFlagAction,
		nargs='+',
		help=(
			"Enable/disable warnings like -Wfoo or -Wno-foo; "
			"Make fatal with -Werror or -Werror=foo"
		),
	)

	# Defaults
	warnings_info = WarningsInfo(known=known_warnings, default=default_warnings)
	parser.set_defaults(enabled_warnings=warnings_info)


class WarningsManager:
	def __init__(self, warnings_info: WarningsInfo):
		self.warnings_info = warnings_info

		# TODO: warnings as errors?
	def emit_warning(self, msg, name=None, logger=None, line_info=None):
		log_warn_f = logging.warning if logger is None else logger.warning
		log_err_f = logging.error if logger is None else logger.error
		assert name in self.warnings_info.known, f"Unknown warning: {name}"
		is_err = name in self.warnings_info.errors
		if name not in self.wwarnings_info.warnings:
			# do nothing
			return
		log_f = log_err_f if is_err else log_warn_f
		if name is not None:
			msg += f" [-W{name}]"
		if line_info is not None:
			line_info_str = f"{line_info.file_path}:{line_info.start_line_no}"
			msg += f" @ {line_info_str}"
		log_f(msg)
		if is_err:
			raise RuntimeError(msg)


