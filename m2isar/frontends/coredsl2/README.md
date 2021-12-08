# CoreDSL 2 Parser

This parser understands the preliminary version 2 of CoreDSL. Its grammar is implemented after the [original XText grammar](https://github.com/Minres/CoreDSL/blob/master/com.minres.coredsl/src/com/minres/coredsl/CoreDsl.xtext) and the [accompanying programmer's manual](https://github.com/Minres/CoreDSL/wiki/CoreDSL-2-programmer's-manual), as the reference grammar is not complete.

## Setup
This parser uses the ANTLR parsing toolkit internally, the parser component needs to be generated before use. Download the ANTLR parser generator from [here](https://www.antlr.org/download.html), then execute:
```
cd /path/to/M2-ISA-R/m2isar/frontends/coredsl2
java -jar /path/to/antlr-4.9.3-complete.jar -o parser_gen -listener -visitor -Dlanguage=Python3 CoreDSL2.g4
```

A VSCode task for parser generation is already created for this project. To use it, put the ANTLR binary in the `/path/to/M2-ISA-R/ext` folder.

## Outputs

The parser outputs the metamodel as a pickled python object at `path/to/input/gen_model/<top_level>.m2isarmodel`.

The parser can be called by its full python module path `python -m m2isar.frontends.coredsl2.parser` or if installed as in the main README, simply by `coredsl2_parser`.

## Usage

```
$ coredsl_parser --help
usage: parser.py [-h] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             The top-level CoreDSL file.

optional arguments:
  -h, --help            show this help message and exit
  --log {critical,error,warning,info,debug}
```