from lark import Transformer, Visitor, Tree, Discard, v_args
from functools import partial
from multiprocessing.pool import Pool
import os

@v_args(inline=True)
class ParallelImporter(Transformer):
    def __init__(self, search_path, parser):
        self.imported = set()
        self.new_children = []
        self.got_new = True
        self.search_path = search_path
        self.parser = parser
        self.current_set = set()

    def transform(self, tree):
        self.new_children.clear()
        self.current_set.clear()
        self.got_new = False
        res = super().transform(tree)

        with Pool() as pool:
            a = pool.map(self.do_include, self.current_set)
            pass

        return res

    def do_include(self, filename):
        print(f'INFO: processing file {filename}')
        with open(os.path.join(self.search_path, filename), 'r') as f:
            __t = self.parser.parse(f.read())
            #self.new_children.extend(__t.children)
        print(f'INFO: done with file {filename}')
        return __t

    def include(self, filename):
        if filename not in self.imported:
            print(f'INFO: queuing file {filename}')
            self.got_new = True
            self.imported.add(filename)
            self.current_set.add(filename)
#            with open(os.path.join(self.search_path, filename), 'r') as f:
#                __t = self.parser.parse(f.read())
#                self.new_children.extend(__t.children)

        raise Discard

@v_args(inline=True)
class Importer(Transformer):
    def __init__(self, search_path, parser):
        self.imported = set()
        self.new_children = []
        self.got_new = True
        self.search_path = search_path
        self.parser = parser

    def transform(self, tree):
        self.new_children.clear()
        self.got_new = False
        return super().transform(tree)

    def include(self, filename):
        if filename not in self.imported:
            print(f'INFO: importing file {filename}')
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