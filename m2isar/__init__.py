class M2Error(Exception):
	pass

class M2ValueError(ValueError, M2Error):
	pass

class M2NameError(NameError, M2Error):
	pass

class M2DuplicateError(M2NameError):
	pass

class M2TypeError(TypeError, M2Error):
	pass

class M2SyntaxError(SyntaxError, M2Error):
	pass