"""
Template for new Operations
The Dict values need to be a Callables that take 
	the operands('Dict[str, mm.IndexedReference]') as argument
	and return any Metamodel BaseNode
"""

from functools import partial
from typing import Callable, Dict, List, Optional, Union

from ....metamodel import arch, behav
from ..operands import Operand
from ..seal5_support import GMIRLegalization

OpcodeDict = Dict[str, Callable[[Dict[str, Operand]], tuple[Union[behav.BaseNode, List[behav.BaseNode]], Optional[GMIRLegalization]]]]
