import argparse
import pathlib
import pickle

from lark import Lark, Tree

from instruction_set_storage import InstructionSetStorage
from model_tree import ModelTree
from transformers import Importer, NaturalConverter, ParallelImporter, Parent

GRAMMAR_FNAME = 'coredsl.lark'

parser = argparse.ArgumentParser()
parser.add_argument("top_level")
parser.add_argument("-j", default=1, type=int, dest='parallel')

args = parser.parse_args()

top_level = pathlib.Path(args.top_level)
abs_top_level = top_level.resolve()
search_path = abs_top_level.parent
model_path = search_path.joinpath('gen_model')
model_path.mkdir(exist_ok=True)

#abs_top_level = os.path.abspath(args.top_level)
#search_path = os.path.dirname(abs_top_level)
#model_path = os.path.join(search_path, 'gen_model')

parser_args = {'grammar_filename': GRAMMAR_FNAME, 'parser': 'earley', 'maybe_placeholders': True, 'debug': False}

print('INFO: reading grammar')
p = Lark.open(**parser_args)

print('INFO: parsing top level')
with open(abs_top_level, 'r') as f:
    tree = p.parse(f.read())

print('INFO: recursively importing files')
imported_tree = tree.copy()

if args.parallel == 1:
    i = Importer(search_path, p)
else:
    i = ParallelImporter(search_path, args.parallel, **parser_args)

while i.got_new:
    imported_tree = i.transform(imported_tree)

print('INFO: cleaning up tree')
converted_tree = NaturalConverter().transform(imported_tree)
converted_tree = Parent().visit(converted_tree)

print('INFO: reading instruction load order')
iss = InstructionSetStorage()
iss.visit(converted_tree)

print('INFO: dumping parse tree')
with open(model_path / (abs_top_level.stem + '_parsed.pickle'), 'wb') as f:
    pickle.dump(converted_tree, f)

print('INFO: dumping instruction set store')
with open(model_path / (abs_top_level.stem + '_iss.pickle'), 'wb') as f:
    pickle.dump(iss, f)

models = {}

for core_name, instruction_sets in iss.core_defs.items():
    print(f'INFO: building model for core {core_name}')
    mt_transformer = ModelTree()
    mt = mt_transformer.transform(Tree('Base', instruction_sets))

    models[core_name] = (mt_transformer, mt[0])


print('INFO: dumping model')
with open(model_path / (abs_top_level.stem + '_model.pickle'), 'wb') as f:
    pickle.dump(models, f)

pass
