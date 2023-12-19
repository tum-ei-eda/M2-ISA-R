"""
Template for new Operations
The Dict values need to be a Callables that take 
	the operands('Dict[str, mm.IndexedReference]') as argument
	and return any Metamodel BaseNode
"""

from functools import partial
from typing import Callable, Dict
from ....metamodel import arch, behav
from ..operands import Operand

OPS: Dict[str, Callable[[Dict[str, Operand]], behav.BaseNode]]
