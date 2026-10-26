# ISAAC Toolkit integration

The planner is now the default in the sibling ISAAC Toolkit checkout.
`generate_etiss_core_planner.py` is a compatibility entry point delegating to
`isaac_toolkit.generate.iss.generate_etiss_core`. Install the typed M2-ISA-R
checkout and ISAAC Toolkit before using it. There is one generator implementation
and one shared CoreDSL writer.

The auto-encoding path calls `encode_instruction_sets()` once for all sets.
Qualified names distinguish identically named instructions in different sets.
Existing encodings occupy the same allocation domain. A final pairwise code/mask
check rejects overlaps, including overlaps between patterns with different masks.
Allocation failure leaves source instructions unmodified and aborts before core
or extension files are emitted. Manual and CFU outputs also undergo overlap
validation. Only generated 32-bit extensions are checked, not imported base ISA
CoreDSL files.

Multi-index runs use globally distinct candidate IDs and update each original
index with its own encoded artifacts. Duplicate instruction names within one set
are rejected instead of silently overwritten. Split instruction dictionaries use
`(code, mask)` keys.

With the typed M2-ISA-R checkout and ISAAC Toolkit installed, run:

```sh
python3 -m isaac_toolkit.generate.iss.generate_etiss_core \
  --workdir /path/to/workdir \
  --index '/path/to/set-a/index.yml;/path/to/set-b/index.yml' \
  --set-name 'SetA;SetB' --auto-encoding --add-mnemonic-prefix
```

All four custom major opcodes are available by default. Add repeated
`--encoding-opcode 0x0b` options to choose permitted major opcodes, or repeated
`--encoding-reserve CODE/MASK` options to reserve patterns. These options apply
to the auto policy; the CFU policy retains its own fixed contract.

Successful auto generation writes `GEN_DIR/encoding_plan.json`. Supply a previous
successful plan with `--encoding-manifest /path/to/encoding_plan.json` to pin
assignments. For CFU, that flag retains the original persistent-ledger meaning.

## Verification and compatibility boundary

From the M2-ISA-R checkout, with the sibling `isaac-toolkit` checkout available:

```sh
python3 -m unittest discover -s tests -v
PYTHONPATH=.:../isaac-toolkit python3 integrations/isaac-toolkit/generate_etiss_core_planner.py --help
```

The smoke tests import the actual alternate generator and exercise its shared
allocator with real metamodel instructions. They verify identical names across
sets, different masks, existing encodings, manifest reuse, GPR metadata, and
capacity exhaustion across sets (32 across all four opcodes, 8 on custom-0 for
17-bit-immediate instructions).

End-to-end CoreDSL/ETISS generation has not been verified in this checkout:
the original Toolkit generator depends on legacy APIs absent from this M2-ISA-R
branch (`parse_cdsl2_set`, `backends.coredsl2_set.writer`, and legacy architectural
constructors). This copy preserves those code-generation sections. Porting the
CoreDSL writer and the surrounding generator to the new metamodel is separate
from the shared-allocation change. Legacy imports are deferred so the allocator
and CLI help can be used and tested with the current planner.
