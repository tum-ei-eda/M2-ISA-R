from enum import Flag, auto

class StaticType(Flag):
	NONE = 0
	READ = auto()
	WRITE = auto()
	RW = READ | WRITE