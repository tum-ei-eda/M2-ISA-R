<!--
SPDX-License-Identifier: Apache-2.0

This file is part of the M2-ISA-R project: https://github.com/tum-ei-eda/M2-ISA-R

Copyright (C) 2022
Chair of Electrical Design Automation
Technical University of Munich
-->

# M2-ISA-R v2

This tool serves as a general-purpose instruction set architecture metamodel. A parser for [CoreDSL](https://github.com/Minres/CoreDSL/wiki/CoreDSL-2-programmer's-manual) and an architecture generator for the instruction set simulator [ETISS](https://github.com/tum-ei-eda/etiss) are currently also provided.

**Please note:** M2-ISA-R is in heavy development, things might change and break without notice. Please report issues on GitHub for any problems you encounter.

## Prerequisites
- Python 3.7+ with at least `pip` and `venv`

## Installation (Usage with CoreDSL 2 and ETISS)
- Make a Python `venv` somewhere: `python -m venv <path-to-venv>`
- Activate said `venv`: `source <path-to-venv>/bin/activate`
- Install M2-ISA-R: `pip install git+https://github.com/tum-ei-eda/M2-ISA-R@coredsl2`

## Development Setup
- Clone the repository, change into the cloned directory
- Make a Python `venv`: `python -m venv venv`
- Activate said `venv`: `source venv/bin/activate`
- Install M2-ISA-R for development: `pip install -e .`

## Architecture
M2-ISA-R consists of 3 components, two of which are exchangeable for different needs:

Frontend -> Metamodel -> Backend

The frontend transforms a model specification into M2-ISA-R's internal architecture model. This model can then be transformed again to an output format, e.g. models for an ISS. This repo provides a CoreDSL frontend and an ETISS backend.

## Usage
M2-ISA-R v2 currently ships three usable tools: Two parsers (for transforming CoreDSL 1.5 / 2 to a M2-ISA-R metamodel) and a writer (for generating ETISS architecture plugins). These are described seperately in their respective directories, TL;DR version:

- To parse a CoreDSL 2 description: `coredsl2_parser path/to/input/<top_level>.core_desc`
- To generate ETISS Architecture: `etiss_writer -s path/to/input/gen_model/<top_level>.m2isarmodel`

For parsers, see [m2isar/frontends/coredsl](m2isar/frontends/coredsl) or [m2isar/frontends/coredsl2](m2isar/frontends/coredsl2). For the ETISS architecture writer, see [m2isar/backends/etiss](m2isar/backends/etiss).

## Roadmap
- [X] CoreDSL 2 support (WIP, RISC-V models are buildable)
- [ ] Formal metamodel description
- [ ] Support for extended CoreDSL 2 features:
	- [ ] Loops (WIP, for loops unimplemented)
	- [ ] Complex data types
	- [ ] Bit-wise aliasing
	- [ ] Spawn blocks
- [X] Detection and evaluation of generation-time static expressions
- [ ] Better support for translation-time static expressions, see #5 and #6
- [ ] Full generation of ETISS architecture models:
	- [ ] Variable width instruction decoding
	- [X] Exception handling
	- [X] Privilege levels