# Encoding planner prototype

The planner assigns deterministic, collision-free 32-bit RISC-V custom encodings
without changing the input model. It supports standard-position R, I and R4
layouts, a two-destination layout, and an immediate-only layout with up to 17
immediate bits. Several logical immediates can share one immediate slot.
Unused slot bits become fixed instruction discriminator bits. Logical immediate
widths and signedness are preserved.

## CLI

After installing the package, use `m2isar_encode`. From a checkout:

```sh
python3 -m m2isar.transforms.encode_instructions.encoder input.m2isarmodel --dry-run --explain
python3 -m m2isar.transforms.encode_instructions.encoder input.m2isarmodel -o encoded.m2isarmodel --report encodings.json
python3 -m m2isar.transforms.encode_instructions.encoder input.m2isarmodel -o encoded.m2isarmodel --assignments encodings.json
```

`--inplace` explicitly replaces the input. Model writes use a temporary file and
atomic replacement. `--dry-run` never writes a model; `--report` still writes a
JSON report. Reports from successful runs can be imported to pin assignments.
Reports with planning errors cannot be imported as assignment manifests.

Use repeated `--opcode 0x0b` options to limit the permitted custom major opcodes.
Use repeated `--reserve CODE/MASK` options to reserve decoding patterns, for
example `--reserve 0x2b/0x7f` reserves an entire major opcode. Overlap checks
compare decoding patterns, rather than only identical code/mask pairs.

Input model files use the repository's existing pickle format and must be trusted.

## Python

```python
from m2isar.transforms.encode_instructions import (
    EncodingPolicy, plan_model, apply_model_plan,
)

plan = plan_model(model, policy=EncodingPolicy())
print(plan.explain())
plan.raise_for_errors()
encoded_model = apply_model_plan(model, plan)
```

`plan_encodings(instructions, policy=None, existing=(), assignments=None)` and
`apply_encoding_plan(instructions, plan, copy=True)` provide the equivalent
instruction-level API. `existing` contains occupied `(code, mask)` patterns.
The `assignments` argument accepts the dictionary returned by `plan.to_dict()`.
Instruction names must be unique in this API. Model-level names are qualified
by set/core name, and shared instruction objects are allocated once. In-place
instruction application validates and stages the entire collection first.

The old `encoder.encode_instructions(instructions)` entry point remains an
in-place wrapper, but assignments follow the new policy. It does not reproduce
legacy generator ordering. The old low-level generator module is retained for
existing direct consumers and is not used by the planner.

## Contracts and prototype limits

- Every operand needs exactly one of IS_REG/IS_IMM and IN/OUT/INOUT. Names are
  never used to guess meaning. An INOUT register uses one destination selector.
- Register operands must be unsigned five-bit selectors. Explicit register
  metadata supports GPR and integer types s32/i32/u32/s64/i64/u64; unsupported
  classes/types are rejected. Metadata is preserved in encoded models.
- Immediate operands must be inputs. No implicit widening, split immediate,
  implicit operand, or user-defined layout support is included yet.
- Allocation uses one conservative namespace across the model. Independent
  sets cannot reuse patterns in this prototype. Existing 32-bit encodings and
  explicit reservations are occupied space; other instruction lengths are
  rejected. Existing-to-existing ambiguities are not diagnosed by this pass.
- Allocation is greedy with deterministic layout and instruction ordering,
  not a global packing optimizer. Adding instructions can change assignments
  unless a previous manifest pins them. Operand declaration order determines
  physical slot order.
- There is no legacy-assignment policy, TOML configuration, core selection,
  capacity visualization, or backtracking optimizer yet.
- Apply plans to the same model state used for planning. Application validates
  operand layouts and existing encoding collisions again; it does not track
  changes to unrelated instruction behavior or policy reservations.

## Smoke tests

```sh
python3 -m unittest discover -s tests -v
```

Tests use metamodel instructions and exercise deterministic allocation, exact
operand coverage, signed immediates, INOUT, multiple destinations, exhausted
reservations, manifest pins, transactional failure, shared model references,
behavior descriptor identity, dry runs, and output serialization.
