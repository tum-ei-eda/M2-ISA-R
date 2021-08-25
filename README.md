# M2-ISA-R v2

This tool serves as a general-purpose instruction set architecture metamodel. A parser for [CoreDSL](https://github.com/Minres/CoreDSL/wiki/CoreDSL-2-programmer's-manual)(note: CoreDSL Version 2 support is currently in development and not ready. The current parser will be obsoleted by this new version, and should not be used for new developments) and an architecture generator for the instruction set simulator [ETISS](https://github.com/tum-ei-eda/etiss) are currently also provided.

## Prerequisites
- Python 3.7+ with at least `pip` and `venv`

## Installation
- Clone the repository, change into its root
- Create a Python virtualenv: `python3 -m venv venv`
- Activate venv: `source venv/bin/activate` (might differ on Windows)
- Install Python dependencies: `pip install -r requirements.txt`

## Architecture
M2-ISA-R consists of 3 components, two of which are exchangeable for different needs:

Frontend -> Metamodel -> Backend

The frontend transforms a model specification into M2-ISA-R's internal architecture model. This model can then be transformed again to an output format, e.g. models for an ISS. This repo provides a CoreDSL frontend and an ETISS backend.

## Usage
M2-ISA-R v2 is divided into two separate tools: Parser and Writer. These are described below, TL;DR version:

- To parse a CoreDSL description: `python -m m2isar.frontends.coredsl.parser [-j threads] path/to/input/<top_level>.core_desc`
- To generate ETISS Architecture: `python -m m2isar.backends.etiss.writer -s path/to/input/gen_model/<top_level>.m2isarmodel`

Notes:
- `path/to/input` stays the same for both calls if the same model is compiled, and should point to the top-level CoreDSL file
- The intermediate and output files are put into `path/to/input/gen_model` and `path/to/input/gen_output`, respectively

### Parser:
Currently, a CoreDSL parser is provided. This parser understands the unofficial version 1.5 of CoreDSL. It is based on the original CoreDSL specification with some fixes backported from version 2.0, such as sized address spaces. As stated above, this parser will become obsolete in the near future, new developments based on it should be avoided. For support please contact the project maintainers.

The parser outputs the metamodel as a pickled python objects at `path/to/input/gen_model/<top_level>.m2isarmodel`.

The parser can be called by `python -m m2isar.frontends.coredsl.parser`. 

Usage:

```
$ python -m m2isar.frontends.coredsl.parser --help
usage: parser.py [-h] [-j PARALLEL] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             The top-level CoreDSL file.

optional arguments:
  -h, --help            show this help message and exit
  -j PARALLEL           Use PARALLEL threads while parsing.
  --log {critical,error,warning,info,debug}
```

### Writer:
A writer backend for ETISS is provided. Call it like this: `python -m m2isar.backends.etiss.writer`. Generator outputs (ETISS architecture plugins) are saved at `path/to/input/gen_output/<top_level>/<core_name>`. These architecture plugins possess all required functionality to run arbitrary target programs on them, except:
- Exception behavior
- Endianness conversion
- Variable-length instruction handling

These functionalities must be implemented manually in the file `<core_name>ArchSpecificImpl.cpp`

Usage:

```
$ python -m m2isar.backends.etiss.writer --help
usage: writer.py [-h] [-s] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             A .m2isarmodel file containing the models to generate.

optional arguments:
  -h, --help            show this help message and exit
  -s, --separate        Generate separate .cpp files for each instruction set.
  --log {critical,error,warning,info,debug}
```
