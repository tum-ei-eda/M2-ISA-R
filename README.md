<!--
SPDX-License-Identifier: Apache-2.0

This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R

Copyright (C) 2026
Chair of Electrical Design Automation
Technical University of Munich
-->

# M2-ISA-R v2

This tool serves as a general-purpose instruction set architecture metamodel. A parser for [CoreDSL](https://github.com/Minres/CoreDSL/wiki/CoreDSL-2-programmer's-manual) and an architecture generator for the instruction set simulator [ETISS](https://github.com/tum-ei-eda/etiss) are currently also provided.

**Please note:** M2-ISA-R is in heavy development, things might change and break without notice. Please report issues on GitHub for any problems you encounter.

## Prerequisites
- Python 3.10+ with at least `pip` and `venv`

## Installation (Usage with CoreDSL 2 and ETISS)
- Make a Python `venv` somewhere: `python -m venv <path-to-venv>`
- Activate said `venv`: `source <path-to-venv>/bin/activate`
- Install M2-ISA-R: `pip install git+https://github.com/tum-ei-eda/M2-ISA-R.git`

## Development Setup
- Clone the repository, change into the cloned directory
- Make a Python `venv`: `python -m venv venv`
- Activate said `venv`: `source venv/bin/activate`
- Install the current checkout and its command-line tools: `pip install -e .`
- To install the published PyPI release instead: `pip install m2isar`

## Warning severity

Implicit truncation is an error by default. Use `-Wno-error=implicit-trunc` to
retain it as a warning, or `-Wno-implicit-trunc` to suppress it. Likewise,
`-Werror -Wno-error=foo` promotes enabled warnings except `foo`.
A later `-Werror=foo` promotes that warning again.

## Regression tests

Run `python -m unittest discover -s tests -v` from the repository root.
See [the test guide](tests/README.md) for feature-specific runs, optional MINRES
comparisons, and adding CDSL or Python metamodel regression cases.

## Architecture
M2-ISA-R consists of 3 components, two of which are exchangeable for different needs:

Frontend -> Metamodel -> Backend

The frontend transforms a model specification into M2-ISA-R's internal architecture model. This model can then be transformed again to an output format, e.g. models for an ISS. This repo provides CoreDSL 2 and CoreDSL 2 instruction-set frontends and several backends.

## Usage
M2-ISA-R provides CoreDSL 2 frontends and backends for ETISS and experimental Spike plugins. Basic commands (run after installation):

- To parse a CoreDSL 2 description: `coredsl2_parser path/to/input/<top_level>.core_desc` (writes the model under `path/to/input/gen_model/`; use `--help` for validation, include path, and output options).
- To generate an ETISS architecture: `etiss_writer path/to/input/gen_model/<top_level>.m2isarmodel`
- To generate a Spike extension: `spike_writer path/to/input/gen_model/<top_level>.m2isarmodel` (see [supported subset and build instructions](doc/source/spike.rst)).

The ETISS writer accepts `--fill-mode empty|auto` to choose whether architecture-specific implementation files are placeholders or populated from available model metadata. Pass GDB register-description mappings as `--gdb-xml-descr <core-name>:<xml-file>...` to generate the corresponding gdbserver register mapping and XML support. See [ETISS writer options](m2isar/backends/etiss/README.md#usage).

### Available frontends, transforms, and backends

- **Frontends:** `coredsl2` parses CoreDSL 2 core descriptions; `coredsl2_set` parses CoreDSL 2 instruction-set descriptions.
- **Transforms:** type inference (`infer_types`), operand inference (`infer_operands`), behavior validation (`validate_behav`), instruction encoding planning/application (`encode_instructions`), loop lowering (`lower_loops`), and merging always blocks (`merge_always_blocks`).
- **Backends and tools:** ETISS architecture generation (`etiss`), experimental Spike extension generation (`spike`), CoreDSL 2 and instruction-set export (`coredsl2`, `coredsl2_set`), model browsing (`viewer`), disassembly (`disass`), trace-model generation (`trace_gen`), ISA manual generation (`isa_manual`), and coverage processing (`coverage`).

Installed command-line entry points include `coredsl2_parser`, `etiss_writer`, `spike_writer`, `m2isar_encode`, `m2isar_viewer`, `m2isar2lcov`, and `trace_gen`. Some frontends, transforms, and backends are library modules without a dedicated installed command.

For parsers, see [the CoreDSL 2 frontend](m2isar/frontends/coredsl2) and [the CoreDSL 2 set frontend](m2isar/frontends/coredsl2_set). For the ETISS architecture writer, see [m2isar/backends/etiss](m2isar/backends/etiss).
