# ETISS Writer

This M2-ISA-R backend generates architecture plugins for the instruction set simulator ETISS. Call it like this: `python -m m2isar.backends.etiss.writer` or `etiss_writer`, if installed as in the main README. Generator outputs (ETISS architecture plugins) are saved at `path/to/input/gen_output/<top_level>/<core_name>`. These architecture plugins possess all required functionality to run arbitrary target programs on them, except:
- Exception behavior
- Endianness conversion
- Variable-length instruction handling

These functionalities must be implemented manually in the file `<core_name>ArchSpecificImpl.cpp`

## Usage

```
$ etiss_writer --help
usage: writer.py [-h] [-s] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             A .m2isarmodel file containing the models to generate.

optional arguments:
  -h, --help            show this help message and exit
  -s, --separate        Generate separate .cpp files for each instruction set.
  --log {critical,error,warning,info,debug}
```
