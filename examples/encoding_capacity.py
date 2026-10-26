"""Generate and verify models near and beyond the custom32 encoding capacity.

Run from the repository root:
    python3 -m examples.encoding_capacity --output-dir /tmp/m2isar-capacity
"""
import argparse
from pathlib import Path
import pickle

from m2isar.metamodel import M2Model, M2_METAMODEL_VERSION, arch
from m2isar.metamodel.attribute_info import OperandAttribute as A
from m2isar.transforms.encode_instructions import apply_model_plan, plan_model


def make_model(count):
    instructions = {}
    for index in range(count):
        name = f"LOAD_IMM_{index:02d}"
        operands = {
            "rd": arch.Parameter("rd", None, {A.IS_REG: [], A.OUT: []}, 5),
            "imm": arch.Parameter("imm", None, {A.IS_IMM: [], A.IN: []}, 17),
        }
        instructions[name] = arch.Instruction(
            name, {}, operands, [None], None, None, None, None,
        )
    extension = arch.InstructionSet(
        name="CapacityDemo", extension=[], parameters={}, memories={},
        memory_aliases={}, register_banks={}, register_aliases={},
        functions={}, instructions={}, unencoded_instructions=instructions,
    )
    return M2Model(M2_METAMODEL_VERSION, {}, {extension.name: extension}, {})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/m2isar-capacity"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 32 bits - 7 opcode bits - 5 rd bits - 17 imm bits = 3 discriminator bits.
    # Thus 8 instruction identities per major opcode, or 32 across custom-0..3.
    for label, count, expected_errors in (("near-full", 31, 0), ("overflow", 33, 1)):
        model = make_model(count)
        plan = plan_model(model)
        if len(plan.assignments) != min(count, 32) or len(plan.errors) != expected_errors:
            raise RuntimeError(f"unexpected planning outcome for {label}:\n{plan.explain()}")
        path = args.output_dir / f"{label}.m2isarmodel"
        path.write_bytes(pickle.dumps(model))
        print(f"{label}: {count} requested, {len(plan.assignments)}/32 slots allocated, "
              f"{len(plan.errors)} errors")
        print(f"  input: {path}")
        if plan.errors:
            print(f"  {plan.errors[0]}")
            try:
                apply_model_plan(model, plan)
            except ValueError:
                print("  Application rejected; input model remains unencoded.")
            else:
                raise RuntimeError("overflow plan unexpectedly applied")
        else:
            encoded = apply_model_plan(model, plan)
            if len(encoded.sets["CapacityDemo"].instructions) != count:
                raise RuntimeError("encoded model is missing instructions")
            print(f"  Occupies {count / 32:.3%} of all four custom major opcodes.")


if __name__ == "__main__":
    main()
