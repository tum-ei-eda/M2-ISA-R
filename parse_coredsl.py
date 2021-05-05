import argparse
import pathlib
import pickle
from typing import List

from lark import Lark, Tree

import model_classes
from architecture_model_builder import ArchitectureModelBuilder
from behavior_model_builder import BehaviorModelBuilder
from instruction_set_storage import InstructionSetStorage
from transformers import Importer, NaturalConverter, ParallelImporter, Parent

GRAMMAR_FNAME = 'coredsl.lark'

parser = argparse.ArgumentParser()
parser.add_argument("top_level")
parser.add_argument("-j", default=1, type=int, dest='parallel')

args = parser.parse_args()

top_level = pathlib.Path(args.top_level)
abs_top_level = top_level.resolve()
search_path = abs_top_level.parent

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

model_path = search_path.joinpath('gen_model')
model_path.mkdir(exist_ok=True)

if False:
    print('INFO: dumping parse tree')
    with open(model_path / (abs_top_level.stem + '_parsed.pickle'), 'wb') as f:
        pickle.dump(converted_tree, f)

    print('INFO: dumping instruction set store')
    with open(model_path / (abs_top_level.stem + '_iss.pickle'), 'wb') as f:
        pickle.dump(iss, f)

models = {}

for core_name, instruction_sets in iss.core_defs.items():
    print(f'INFO: building architecture model for core {core_name}')
    print("")

    arch_builder = ArchitectureModelBuilder()
    mt : List[model_classes.CoreDef] = arch_builder.transform(Tree('make_list', instruction_sets))

    models[core_name] = mt[0]

for core_name, core_def in models.items():
    print(f'INFO: building behavior model for core {core_name}')
    print("")

    warned_fns = set()

    # functions
    for fn_name, fn_def in core_def.functions.items():
        behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases, fn_def.args, core_def.functions, warned_fns)
        if isinstance(fn_def.operation, Tree):
            fn_def.operation = behav_builder.transform(fn_def.operation)

    # instructions
    for (code, mask), instr_def in core_def.instructions.items():
        behav_builder = BehaviorModelBuilder(core_def.constants, core_def.memories, core_def.memory_aliases, instr_def.fields, core_def.functions, warned_fns)
        if isinstance(instr_def.operation, Tree):
            instr_def.operation = behav_builder.transform(instr_def.operation)

print('INFO: dumping model')
with open(model_path / (abs_top_level.stem + '_model.pickle'), 'wb') as f:
    pickle.dump(models, f)

pass
