# CoreDSL 1.5 Parser

This parser understands the unofficial version 1.5 of CoreDSL. It is based on the original CoreDSL specification with some fixes backported from version 2.0, such as sized address spaces. As stated in the main README, this parser is obsolete and kept around for reference only. New developments based on it should be avoided. For support please contact the project maintainers. The grammar of the currently used CoreDSL dialect can be seen in [coredsl.lark](m2isar/frontends/coredsl/coredsl.lark). See [here](https://lark-parser.readthedocs.io/en/latest/grammar.html) for the lark grammar reference which this grammar description uses.

## Outputs:

The parser outputs the metamodel as a pickled python object at `path/to/input/gen_model/<top_level>.m2isarmodel`.

The parser can be called by its full python module path `python -m m2isar.frontends.coredsl.parser` or if installed as in the main README, simply by `coredsl_parser`.

## Usage

```
$ coredsl_parser --help
usage: parser.py [-h] [-j PARALLEL] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             The top-level CoreDSL file.

optional arguments:
  -h, --help            show this help message and exit
  -j PARALLEL           Use PARALLEL threads while parsing.
  --log {critical,error,warning,info,debug}
```