Metamodel versions and compatibility
====================================

M2-ISA-R stores the metamodel version in each serialized ``M2Model``. A model
pickle is an internal interchange format: consumers should use models produced
by the same M2-ISA-R metamodel version. A version match is required, but is not
a guarantee that arbitrary Python or dependency versions can unpickle it.
M2-ISA-R does not automatically migrate older model pickles. Regenerate them
from their CoreDSL sources when changing metamodel versions.

Version history
---------------

The notes below summarize changes that can be established from the repository
history.

* **Pre-versioned legacy output:** Before the versioned ``M2Model``
  container, the CoreDSL frontend wrote the model dictionary and line
  information separately. This output is not a supported input format for
  current consumers.
* **Version 2:** Replaced the raw model dictionary and
  separate line-info pickle with one versioned ``M2Model`` pickle. The
  container held the core-model mapping and a shared ``code_infos`` database
  containing source locations and function metadata. This changed the top
  level serialized object and the representation of source-location records.
* **Version 3:** The version introduces several structural changes:

  * ``M2Model.models`` becomes ``M2Model.cores`` and a separate ``sets``
    mapping was added for instruction-set models.
  * Behavioral nodes gained an ``inferred_type`` field. ``StringLiteral`` was
    added, and ``IntLiteral`` changed its default signedness rule so zero is
    signed when signedness is omitted.
  * Instructions replaced the single ``disass`` field with ``mnemonic`` and
    ``assembly``, and instructions and functions gained ``function_info``
    references.
  * Source metadata gained branch records (``BranchInfo`` and
    ``BranchEntryInfo``), branch IDs, and before/after placement. The metadata
    factories were consolidated into ``InfoFactory`` and IDs/placement became
    keyword-only constructor fields.
  * Source locations were attached to additional expression nodes, including
    literals, casts, and branch conditions.

  No v2-to-v3 migration is provided; consumers must regenerate models.
* **Version 4:** Added ``AlwaysBlock`` to cores and
  instruction sets, with ordering information. ``merge_always_blocks`` was
  added for backends that need always-block behavior copied into instructions
  in declaration order (stable for equal order values).
* **Version 5:** Changed loop representation and semantics.
  Loops retain initializer and update statements, and explicit
  ``ForLoop``, ``WhileLoop`` and ``DoWhileLoop`` classes were added. A for
  initializer runs once before the loop; updates run at the latch, including
  before a continue targeting that loop. Iterator declaration, condition,
  updates, body and conditional break/continue participate in one staticness
  domain. Prefix/postfix increment and decrement, continue statements and
  block-level attributes are also represented. This is an intentional
  breaking change from version 4: v4 consumers must not interpret v5 loop
  objects using the old ``Loop`` layout or assume that init/updates have
  already been expanded into surrounding statements.

Loop transforms
---------------

``lower_loops`` is backend canonicalization: it maps ``ForLoop``,
``WhileLoop`` and ``DoWhileLoop`` to the common ``Loop`` class while preserving
the loop's initializer, updates, condition, body and pre/post-test behavior.
It does not desugar for clauses.

``desugar_loops`` expands a for loop into a lexical block containing its
initializer statements and a canonical pre-tested ``Loop``. Updates are
placed at the loop latch and before continues targeting that loop. While and
do-while loops become canonical ``Loop`` nodes with the corresponding test
order. This transform is intended for consumers that need the expanded
statement shape; run analyses that rely on source loop classes or unified
loop staticness before applying it. The transform is opt-in and does not
change the serialized model version.

Version checking
----------------

Use ``load_model`` for model loading. It rejects a version mismatch by
default. Its ``allow_missmatch=True`` escape hatch is for deliberate
investigation only; it logs a warning and does not migrate the model. Backend
loaders reject mismatched versions with an error that reports both versions
and directs users to regenerate the model. A mismatch means the consumer may
read fields with changed meaning or layout, so regenerate the model with the
matching M2-ISA-R release.
