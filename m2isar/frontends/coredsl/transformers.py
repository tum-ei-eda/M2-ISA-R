# SPDX-License-Identifier: Apache-2.0
#
# This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R
#
# Copyright (C) 2022
# Chair of Electrical Design Automation
# Technical University of Munich

import logging
import os
from functools import partial
from itertools import chain
from multiprocessing.pool import Pool

from lark import Discard, Lark, Transformer, Tree, Visitor, v_args


@v_args(inline=True)
class ParallelImporter(Transformer):
	def __init__(self, search_path, parallel, **parser_args):
		self.imported = set()
		self.new_children = []
		self.got_new = True
		self.search_path = search_path
		self.parallel = parallel if parallel > 1 else None
		self.parser_args = parser_args
		self.current_set = set()
		self.logger = logging.getLogger("parallel_importer")

	def transform(self, tree):
		self.new_children.clear()
		self.current_set.clear()
		self.got_new = False
		res = super().transform(tree)

		with Pool(processes=self.parallel) as pool:
			imported_children = pool.map(self.do_include, self.current_set)

		res.children = list(chain.from_iterable(imported_children)) + res.children
		return res

	def do_include(self, filename):
		self.logger.info(f'processing file {filename}')
		p = Lark.open(**self.parser_args)
		with open(os.path.join(self.search_path, filename), 'r') as f:
			__t = p.parse(f.read())

		self.logger.info(f'done with file {filename}')
		return __t.children

	def include(self, filename):
		if filename not in self.imported:
			self.logger.info(f'queuing file {filename}')
			self.got_new = True
			self.imported.add(filename)
			self.current_set.add(filename)

		raise Discard

@v_args(inline=True)
class Importer(Transformer):
	def __init__(self, search_path, parser):
		self.imported = set()
		self.new_children = []
		self.got_new = True
		self.search_path = search_path
		self.parser = parser
		self.logger = logging.getLogger("importer")

	def transform(self, tree):
		self.new_children.clear()
		self.got_new = False
		res = super().transform(tree)

		res.children = self.new_children + res.children

		return res

	def include(self, filename):
		if filename not in self.imported:
			self.logger.info(f'importing file {filename}')
			self.got_new = True
			self.imported.add(filename)
			with open(os.path.join(self.search_path, filename), 'r') as f:
				__t = self.parser.parse(f.read())
				self.new_children.extend(__t.children)

		raise Discard

@v_args(inline=True)
class NaturalConverter(Transformer):
	BINARY = partial(int, base=2)
	HEX = partial(int, base=16)
	OCT = partial(int, base=8)
	INT = partial(int, base=10)
	ID = str
	OP_ID = str

	def natural(self, num):
		return num

class Parent(Visitor):
	def __default__(self, tree):
		for subtree in tree.children:
			if isinstance(subtree, Tree):
				assert not hasattr(subtree, 'parent')
				subtree.parent = tree
