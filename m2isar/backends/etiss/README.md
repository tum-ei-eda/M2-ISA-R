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
