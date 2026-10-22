Experimental Spike plugin backend
=================================

The backend generates a shared-library extension rather than patches to Spike.
It uses ``extension_t`` (the general interface behind Spike's RoCC examples),
so operands need not obey the RoCC xs1/xs2/xd convention. Each factory call
allocates a separate extension instance; custom state belongs to that instance
and is initialized both on construction and on hart reset.

Generate and build
------------------

Parse a CoreDSL specification using ``coredsl2_parser``, then run::

   spike_writer path/to/gen_model/Example.m2isarmodel
   cd path/to/gen_output/Example/Example
   make SPIKE_INCLUDE=/path/to/spike/install/include/riscv
   spike --isa=RV32IM --extlib=./libextension.so --extension=m2_Example program.elf

The extension name is ``m2_`` followed by the core name (or legacy instruction-set name), preserving
case. Integration tests were verified against Spike revision
``2c300cd90eb74bb79f3fcdd58596a6f8d842d01c``.
The library must be compiled against the same Spike revision and build
configuration as the executable. Spike's C++ plugin ABI is not stable.
``extension.cc`` and a minimal Makefile are generated per core.
When building against an uninstalled source tree, supply the source and build
include directories through ``CPPFLAGS`` instead.

Supported subset and constraints
-------------------------------

* RV32I and RV64I integer execution, with 32-bit instructions in the four
  RISC-V custom opcode spaces (0x0b, 0x2b, 0x5b, 0x7b). RV32E/RV64E are
  unsupported. The main integer bank's element width selects the plugin's XLEN;
  execution on a hart with a different XLEN traps. Models without a main
  integer bank default to RV32.
* Encoded operands of 1 through 32 bits, including split fields. Signed metamodel fields are sign-extended;
  the existing CoreDSL frontend does not currently handle explicit operand
  declarations correctly, so the CoreDSL examples use unsigned fields. Instruction encodings must be disjoint. Overlapping later
  instructions are warned about and omitted.
* A main integer bank tagged ``is_main_reg`` must have 32 entries of either 32 or 64 bits.
  Reads and writes use Spike's integer state; x0 remains hardwired to zero.
* Custom register banks have finite, zero-based ranges and 32- or 64-bit elements, independently of XLEN.
  Initial values are restored at reset; unspecified elements start at zero.
  Custom state is accessed by generated instructions, not exposed as CSRs or
  debugger registers. Memory aliases are unsupported.
* Assignments, blocks, integer literals, field/constant/register references,
  grouping, unary +, -, ~, !, and binary +, -, *, &, |, ^ and comparisons
  are supported. Integer register writes truncate to XLEN; custom-state writes
  truncate to the declared element width. Intermediate arithmetic uses
  generated C++ integer types; arbitrary CoreDSL width and overflow semantics
  are not implemented.
* Main memory accesses, PC writes, floating point, vectors, function calls,
  casts, slices, concatenation, loops, conditionals, instruction attributes,
  and raw code literals are unsupported. Custom state bounds are checked by
  generated accessors; invalid indices trap as illegal instructions.
* Disassembly currently falls back to Spike's unknown-instruction display.

Unsupported instructions produce a logging warning naming the instruction and
reason and are omitted entirely. Unsupported custom state declarations fail
rather than producing an invalid library. Review warnings before running:
programs that execute omitted instructions trap as illegal instructions.

Tests
-----

Run the unit tests with::

   python -m unittest discover -s tests -v

For the real shared-library and guest execution test, build Spike and run::

   SPIKE_SOURCE=/path/to/riscv-isa-sim SPIKE_BUILD=/path/to/build \
     python -m unittest discover -s tests -v

This test also needs a C++ compiler and Clang/LLD with RISC-V target support.
The representative model covers add, subtract, xor, and, or, custom-state set,
get, and accumulate operations. The integration harness also verifies independent
state on two harts, reset including nonzero initial values, and invalid-state-index
traps. The RV32 and RV64 guests verify x0 and register-width wraparound. RV64 checks
also exercise values above 32 bits, the top register bit, custom-state
round trips, commit logging, and PCs above 4 GiB.

For an RV64 model, declare the main bank as ``register unsigned<64> X[32]
[[is_main_reg]]`` (and use 64-bit PC/custom state as needed), then select
``--isa=RV64IM`` when running Spike. Instruction encodings remain 32 bits.

Interface references:
`Spike dummy_rocc.cc <https://github.com/riscv-software-src/riscv-isa-sim/blob/master/customext/dummy_rocc.cc>`_
and `extension.h <https://github.com/riscv-software-src/riscv-isa-sim/blob/master/riscv/extension.h>`_.
