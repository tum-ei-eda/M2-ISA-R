"""
Template for new Operations
The Dict values need to be Callables that take 
    the operands('Dict[str, mm.IndexedReference]') as argument
    and return any Metamodel BaseNode
"""

from functools import partial
from typing import Callable, Dict
from m2isar.m2isar.metamodel import arch, behav as mm

OPS: Dict[str, Callable[[Dict[str, mm.IndexedReference]], mm.BaseNode]]
