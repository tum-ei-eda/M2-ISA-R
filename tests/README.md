# Regression tests

Run from the repository root using the development environment (`pip install -e .`).
The native suite uses Python's standard-library `unittest`; Java and the MINRES
validator are optional.

The `Regression tests` GitHub Actions workflow runs the native suite on pushes
and pull requests using Python 3.10. New `test_*.py` files are discovered
automatically; no CI registration is needed.

```sh
python -m unittest discover -s tests -v
```

With the local environment, use `venv/bin/python` instead of `python`.
Run a feature group while developing:

```sh
python -m unittest discover -s tests -p 'test_metamodel_collection.py' -v
python -m unittest discover -s tests -p 'test_*lowering.py' -v
```

Run one regression method with the test directory on Python's import path:

```sh
PYTHONPATH=tests python -m unittest \
  test_continue_regression.ContinueNativeTest.test_mixed_order_after_folding -v
```

To include differential checks against MINRES **2.0.21**, supply your own release
JAR and install Java:

```sh
COREDSL_VALIDATOR_JAR=/absolute/path/com.minres.coredsl.validator-2.0.21.jar \
  python -m unittest discover -s tests -v
```

Without this variable, oracle tests are explicitly skipped; native regression
tests still run. The JAR is not downloaded by the suite. Oracle tests inspect
diagnostic output because the release can return exit status zero on errors.

## Coverage and useful starting points

| Layer | Examples | What the assertions protect |
| --- | --- | --- |
| Source CDSL validation | `test_source_validator.py`, `test_source_semantics.py`, `test_source_attributes.py`, `test_source_statement_collection.py`, `test_source_call_collection.py` | Valid programs, issue codes, warning names, semantic errors, scope cleanup, lazy call arguments and recovery across calls, blocks, declarators and for-loop parts |
| Parsing and lowering | `test_parse_diagnostics.py`, `test_literal_lowering.py`, `test_local_scope_lowering.py`, `test_enum_lowering.py` | Clean syntax diagnostics, model values/types, lexical binding |
| Direct Python metamodel validation | `test_behavior_validator.py`, `test_metamodel_sizes.py`, `test_metamodel_conditions.py`, `test_range_constants.py` | Node semantics, boundary cases, warning promotion and suppression, independent constant failures |
| Saved-model API and CLI | `test_metamodel_collection.py`, `test_metamodel_returns.py`, `test_metamodel_breaks.py` | Serialization, retained diagnostics after optimization, multiple errors, clean CLI failures |
| Generated-code execution | `test_continue_regression.py`, `test_increment_regression.py` | Compile and run emitted behavior; check loop results, prefix/postfix values, width wrapping, slice preservation, lazy branches, memory callback counts and index evaluation |
| Release comparison | `test_minres_parity.py`, `test_*parity.py`, oracle classes in metamodel tests | Expected release messages/severity and diagnostic counts |

CDSL fixtures are stored as source strings and case tables in these Python files.
Tests materialize independent `.core_desc` files and generated models in temporary
directories. They do not require or modify the external default architecture.
Both the fixtures and assertions therefore travel with the repository.

## Adding a regression or feature

1. Add a small CDSL reproducer to the relevant native test or case table. Include
   a nearby valid example and a boundary case where useful. Assert the issue code
   or resulting model behavior, rather than merely checking that parsing finishes.
2. For behavior supported by saved models, test parsing without `--validate`,
   loading the generated model, and standalone validation. The helpers in
   `test_metamodel_collection.py` show how to check API diagnostics and CLI exit
   status together, including the absence of a traceback.
3. Add a direct Python-node test when a case depends on unknown types, partial
   analysis, legacy model metadata, or a condition that CDSL lowering cannot
   represent. Use the public validation entry point when testing model traversal.
4. Add the same case to an optional MINRES comparison when claiming release
   parity. Check relevant messages and total error counts so extra diagnostics
   also fail the test. Keep native assertions runnable without the JAR.
   `test_source_call_collection.py` and `test_source_intrinsic_collection.py`
   demonstrate the distinction between lazy declared-call arguments and eager
   intrinsic arguments, including recovery of known result types after errors.
   `test_source_branch_collection.py` covers condition/branch/body recovery,
   traversal order and partial-analysis deferral.
   `test_source_ternary_collection.py` covers all-child analysis and preserving
   initializer/outer-call conversion errors after child failures.
   `test_source_binary_collection.py` checks both operand errors, operator errors
   and Boolean results retained by logical/comparison operators.
   `test_source_assignment_collection.py` checks independent target/conversion
   diagnostics, retained assignment types and full/partial compound rules.
   `test_signature_mismatch_recovery.py` checks independent body diagnostics
   after mismatched inherited declarations and distinguishes lexical reference
   types from elaborated parameter values.
   `test_inherited_parameter_precedence.py` distinguishes provider default values
   and explicit Core overrides, and checks independent behavior errors retained
   after equal-signature redeclaration diagnostics.
   `test_inheritance_cycle_collection.py` checks independent/mutual cycles,
   per-ISA chains and nonparticipating dependents, recording known release
   internal-error counts separately from native cycle diagnostics.
   `test_dependency_linking_collection.py` checks multiple missing/wrong-kind
   ISA dependencies alongside independent unresolved body references, with
   release error counts and a valid inheritance control.
   `test_call_result_member_linking.py` checks direct function-result member
   linking before semantic errors, including wrong call arities and valid
   ordinary-reference controls.
   `test_composite_assignment_targets.py` checks writable/readonly composite
   bases and fields, nested members, grouped bases and independent error counts
   against the release.
   `test_readonly_assignment_targets.py` pairs readonly and writable targets
   for ordinary/compound assignments through source, saved-model API/CLI and
   optional release checks.
   `test_grouped_assignment_targets.py` checks grouped lvalue rejection through
   source and saved-model API/CLI validation, grouped array read execution,
   emitted grouping and release diagnostic counts.
   `test_source_unary_collection.py` checks unary child/target/operator errors,
   logical-not results and unary-minus widening.
   `test_source_cast_collection.py` checks cast/child/conversion recovery,
   incomplete array casts and identity warnings retained after child errors.
   `test_source_switch_collection.py` checks condition/label/body diagnostics
   in section order, repeated and trailing labels, and partial case values.
   `test_source_return_collection.py` checks return context and conversion
   diagnostics after child errors, branch recovery and incomplete return types.
   `test_duplicate_member_precedence.py` checks first-member lookup for repeated
   struct and union fields, with release comparisons and valid nested accesses.
   `test_compound_assignment_lowering.py` checks all ten compound operators,
   saved-model validation, emitted source, and ordinary versus compound
   conversion rules.
   `test_continue_regression.py` checks continue scope through saved models,
   folding and serialization, mixed break/continue order, utility traversal,
   and compiled loop behavior from CoreDSL2 and ETISS output. Its execution
   test skips explicitly if g++ is unavailable.
   `test_increment_regression.py` checks prefix/postfix parsing, saved-model
   diagnostics and const architectural targets, declared-width wrapping, emitted
   CoreDSL2 values, and compiled ETISS scalar/slice and memory assignment/return
   behavior. Memory controls count address evaluations, reads and writes, and
   check read failures. Execution methods skip explicitly without g++.
   `test_source_linking.py` checks linking before semantic diagnostics, lexical
   scope, forward state references, and inherited composite type precedence.
   `test_source_alias_collection.py` checks independent alias type, storage and
   constness errors and valid exact-type const aliases.
   `test_source_list_collection.py` checks list shape, element conversion/child
   errors, nested-list traversal, scalar-list laziness, and valid bindings.
   `test_source_definition_collection.py` checks sibling functions, instructions,
   always blocks, roots, state initializer/alias recovery, and function-context
   cleanup after signature errors.
   `test_size_query_references.py` checks exact size-query values and widths,
   direct versus parenthesized array references, partial arrays, and constant
   values retained by model lowering and serialization.
5. Run the feature group, then the native suite. Update
   `doc/coredsl2-validator-alignment.md` when a diagnostic's coverage changes.

Use descriptive `test_*` names and `subTest` labels for case tables. Avoid
machine-specific paths, external architecture dependencies, and assertions that
only mirror implementation details. Tests documenting an existing gap must say
so explicitly; passing them does not establish parity. The alignment tracker
records the remaining gaps; this suite does not yet cover every language feature
or backend behavior.
