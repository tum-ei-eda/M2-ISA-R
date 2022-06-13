<!--
SPDX-License-Identifier: Apache-2.0

This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R

Copyright (C) 2022
Chair of Electrical Design Automation
Technical University of Munich
-->

# ETISS Writer

This M2-ISA-R backend generates architecture plugins for the instruction set simulator ETISS. Call it like this: `python -m m2isar.backends.etiss.writer` or `etiss_writer`, if installed as in the main README. Generator outputs (ETISS architecture plugins) are saved at `path/to/input/gen_output/<top_level>/<core_name>`. These architecture plugins possess all required functionality to run arbitrary target programs on them, except:
- Exception behavior
- Endianness conversion
- Variable-length instruction handling

These functionalities must be implemented manually in the file `<core_name>ArchSpecificImpl.cpp`. Future versions of M2-ISA-R aim to also generate at least parts of these functions from a metamodel.

## Known issues
- Instruction behavior such as `MEM[X[rs1] + imm] = MEM[X[rs2]]` does not see `X[rs1]` as a dependent register.
- Staticness (whether the value of a variable is completely known at instruction generation time, i.e. outside of JIT-compilation in ETISS) detection of instruction-level local variables (scalars) is crude and breaks once multiple levels of scoping are necessary.
- The above also breaks ETISS's register dependency tracking when scope-restricted variables or expressions are used for register addressing, see [issue #6](https://github.com/tum-ei-eda/M2-ISA-R/issues/6) in this repo.

## Usage

```
$ etiss_writer --help
usage: writer.py [-h] [-s] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             A .m2isarmodel file containing the models to generate.

optional arguments:
  -h, --help            show this help message and exit
  -s, --separate        Generate separate .cpp files for each instruction set.
  --static-scalars      Enable crude static detection for scalars. WARNING: known to break!
  --log {critical,error,warning,info,debug}
```

## Internals
This M2-ISA-R generator backend works in different stages to generate ETISS architecture models:
1) Load pickled architecture model
2) Create output directory structure
3) Generate ETISS model boilderplate
4) Generate function and instruction behavior

Behavior generation makes heavy use of Python's monkey-patching and introspection capabilities. To separate the plain structure and data model information from the knowledge of how to transform this data into ETISS code, the functions required for ETISS code generation are monkey-patched into the architecture model at runtime. In this process, the generic method `generate(context)` of every behavior model node is replaced by a specialized method, defined in [instruction_transform.py](instruction_transform.py). To automate this patching process, Python's `inspect` module is used, looking at every function inside [instruction_transform.py](instruction_transform.py), reading its signature and type hints, and replacing the `generate` function in the class indicated by the type hint of the `self` argument. Example:

```
def operation(self: behav.Operation, context: TransformerContext):
  return "nop"
```

The patching logic would perform the assignment `behav.Operation.generate = operation`. For the implementation of the patching logic, see [here](https://github.com/tum-ei-eda/M2-ISA-R/blob/coredsl2/m2isar/backends/etiss/instruction_generator.py#L14).

High-level code generation is done through `mako` templates, where large amounts of static text is required. Behavioral code is generated directly in Python through string operations. To pass state information between generation nodes, `CodeString` objects containing the actual string and supporting data are used.