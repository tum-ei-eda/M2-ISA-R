<!--
SPDX-License-Identifier: Apache-2.0

This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R

Copyright (C) 2022
Chair of Electrical Design Automation
Technical University of Munich
-->

# CoreDSL 2 Parser

This parser understands the preliminary version 2 of CoreDSL. Its grammar is implemented after the [original XText grammar](https://github.com/Minres/CoreDSL/blob/master/com.minres.coredsl/src/com/minres/coredsl/CoreDsl.xtext) and the [accompanying programmer's manual](https://github.com/Minres/CoreDSL/wiki/CoreDSL-2-programmer's-manual), as the reference grammar is not complete.

## Parser generation
The actual text parser for the CoreDSL 2 language is generated from [](CoreDSL2.g4) using the ANTLR4 parser generator. This repository provides up-to-date generation outputs for ease of use. If you want to change the main grammar, you have to regenerate the parser as follows:

1) Install `antlr-tools` in your venv:

    ```
    pip install antlr-tools
    ```

2) Run ANTLR4 parser generator:

    ```
    cd /path/to/M2-ISA-R/m2isar/frontends/coredsl2
    antlr4 -v 4.13.1 -o parser_gen -listener -visitor -Dlanguage=Python3 CoreDSL2.g4
    ```

A VSCode task for parser generation is already created for this project. To use it, install `antlr-tools` as shown in 1), then select `Terminal` -> `Run Task...` -> `Generate CoreDSL2 ANTLR parser`.

## Limitations
This parser should be considered as in active development, so bugs will most likely occur. In addition, this parser (but also the metamodel and therefore the code generator) do not implement the following CoreDSL 2 features (at the moment):
- Pre- / Post-increment (`x++, ++x`)
- Switch case statements
- Lowering of composite datatypes (`struct`, `union`): the validator checks them and the metamodel has `StructType` / `UnionType`, but declarations and member accesses are not lowered to the model yet. `enum`s are supported and lowered to their base integer type (see [Validator view and metamodel view](#validator-view-and-metamodel-view)).
- Pointers
- `spawn` statements
- String literals

In addition to that, qualifiers other than `extern` and `register` in `architectural_state` declarations are ignored. The "flexible attribute system" of the reference parser is implemented, although unknown attributes are currently ignored.

The parser does not honor CoreDSL 2's type promotion rules for arithmetic operations. For progress on this feature, see #10.

In the future, these features might also be implemented if needed. For most CPU models, they should however not be absolutely necessary.

Functionality currently considered experimental:
- Slicing expressions
- Concatenation expressions
- Loops

## Outputs

The parser outputs the architecture model as a pickled python object at `path/to/input/gen_model/<top_level>.m2isarmodel`.

## Usage

The parser can be called by its full python module path `python -m m2isar.frontends.coredsl2.parser` or if installed as in the main README, simply by `coredsl2_parser`.

```
$ coredsl2_parser --help
usage: parser.py [-h] [--log {critical,error,warning,info,debug}] top_level

positional arguments:
  top_level             The top-level CoreDSL file.

optional arguments:
  -h, --help            show this help message and exit
  --log {critical,error,warning,info,debug}
```

## Internals
CoreDSL 2 files are parsed using the ANTLR v4 grammar [CoreDSL2.g4](CoreDSL2.g4). Generation of the architecture model takes place during multiple phases:
1) Read top-level CoreDSL file
2) Recursively resolve and read all imports
3) Generate a bottom-up parsing order, to preserve the hierarchical model contained in the CoreDSL description during model generation
4) Parse architectural details and build an architectural model. Here everything except instruction and function behavior is read and generated.
5) Check if top-level architecture model is fully resolved. As CoreDSL 2 allows arbitrary expressions almost anywhere (i.e. user-defined parameters as register size), try to evaluate all expressions describing architectural details. Cancel parsing if evaluation fails.
6) Parse instruction / function behavior, build the behavioral models for each instruction and function. This and the previous parsing steps are seperated to make state tracking between different passes easy.
7) Dump the resulting model to disk, as a binary Python pickle dump.

### Validator view and metamodel view
The frontend works with two views of the same declarations and types:

- The **validator view** is what the source semantic validator ([source_semantics.py](source_semantics.py), [source_types.py](source_types.py)) checks the CoreDSL source against, following the rules of the MINRES CoreDSL 2.0.21 analyzer. It exists before any model is built, may contain types that are not resolved yet, and never leaves the frontend.
- The **metamodel view** is the model that the frontend produces and backends consume ([arch.py](../../metamodel/arch.py), [type_info.py](../../metamodel/type_info.py)).

| Concept | Validator view | Metamodel view |
|---|---|---|
| Declared name | `DslSymbol` | `arch.Symbol` (`Register`, `Memory`, `Variable`, ...) or `arch.Parameter` |
| Type | `DslType` | `type_info.PrimitiveType`, `ArrayType`, `PointerType`, `StructType`, `UnionType` |

The validator classes use a `Dsl` prefix so they don't clash with the metamodel names.

**How the two views are connected.** The validator classes refer to the metamodel classes through composition. The metamodel never refers back to the validator.

- `DslType.meta` holds the metamodel type that backs the `DslType`. The `width`, `signed` and `count` properties read from it, and sizes inside `meta` are always resolved integers. `source_types.from_meta(ty, resolve)` wraps an existing metamodel type and uses `resolve` (usually `arch.get_const_or_val`) to resolve parameter or expression sizes.
- `DslSymbol.model` refers to the `arch.Symbol` or `arch.Parameter` a symbol was built from, when the model builders hand existing model objects to the validator. Symbols the validator creates from the source alone have `model=None`.

**Validator-only rules.** Some things exist only in the validator view and are not part of the metamodel:

- Type equality and conversion rules (`DslType.equality_key`, `convertible`, `common_integer`). These include MINRES quirks; for example, two enum types compare equal when their widths match.
- Unknown types (`UNKNOWN`). A type that cannot be resolved yet is skipped for now and later checks catch it; it is never taken as proof that the source is valid.
- Enums. An enum `DslType` keeps its name, identity and members (name -> value) itself. Its `meta` is the base integer type, so the model only ever sees that integer. Enum members are lowered to `arch.Parameter`s tagged with `_coredsl_enum_name`.
- Extern address spaces (`kind == 'address'`). In the metamodel, these are represented as a pointer to their array (`PointerType(ArrayType(...))`).

Structs and unions exist in both views. In the metamodel, `StructType` and `UnionType` store each field's type, bit size and bit offset. Lowering of composite member access is not implemented yet.
