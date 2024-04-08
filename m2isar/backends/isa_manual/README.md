# ISA Manual Generator

## Setup

Make sure to have a recent version of the NPM package manager installed on your system.

In this directory run `npm install` to download the dependencies. After completion, check if `./node_modules/.bin/datasheet` exists.

## Usage

Generate Asciidoc:

```sh
python3 -m m2isar.backends.isa_manual.writer /path/to/etiss_arch_riscv/gen_model/top.m2isarmodel --output out.adoc
```

Convert Asciidoc:

```sh
# to html
./node_modules/.bin/datasheet -i M2-ISA-R/out.adoc -o /tmp/out.html

# to pdf
./node_modules/.bin/datasheet -i M2-ISA-R/out.adoc -o /tmp/out.pdf
```
