from enum import IntFlag, auto

class StaticType(IntFlag):
	NONE = 0
	READ = auto()
	WRITE = auto()
	RW = READ | WRITE