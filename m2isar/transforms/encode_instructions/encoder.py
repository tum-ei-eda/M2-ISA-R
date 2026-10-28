"""Command line interface and compatibility wrapper for the encoding planner."""
import argparse
import json
import logging
import os
from pathlib import Path
import pickle
import tempfile

from ...metamodel import M2_METAMODEL_VERSION
from .planner import (EncodingError, EncodingPolicy, apply_encoding_plan,
                      apply_model_plan, plan_encodings, plan_model)


def encode_instructions(instructions):
    """Encode an instruction collection in place after complete validation.

    Assignments use the new deterministic policy, not the legacy generator order.
    Use plan_encodings directly to reserve existing patterns or preview choices.
    """
    instructions = list(instructions)
    return apply_encoding_plan(instructions, plan_encodings(instructions), copy=False)


def save_model(model, path):
    """Atomically replace the output only after successful serialization."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name + ".", delete=False) as stream:
            temporary = stream.name
            pickle.dump(model, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("top_level", type=Path)
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--output", "-o", type=Path)
    output.add_argument("--inplace", "-i", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--report", type=Path, help="Write a JSON report / assignment manifest")
    parser.add_argument("--assignments", type=Path, help="Pin assignments from a previous successful report")
    parser.add_argument("--opcode", action="append", type=lambda value: int(value, 0), help="Custom major opcode (repeatable)")
    parser.add_argument("--reserve", action="append", default=[], metavar="CODE/MASK", help="Reserve a 32-bit pattern; integers accept 0x prefixes")
    parser.add_argument("--log", default="info", choices=["critical", "error", "warning", "info", "debug"])
    args = parser.parse_args(argv)
    if not args.dry_run and not (args.output or args.inplace):
        parser.error("choose --output, --inplace, or --dry-run")
    # Reports must never overwrite models or input manifests.
    protected = [args.top_level, args.output, args.assignments]
    if args.report and any(args.report.resolve() == p.resolve() for p in protected if p):
        parser.error("--report must differ from model and manifest paths")
    if args.output and args.output.resolve() == args.top_level.resolve():
        parser.error("use --inplace to overwrite the input model")
    logging.basicConfig(level=getattr(logging, args.log.upper()))
    try:
        with args.top_level.open("rb") as stream:
            model = pickle.load(stream)
        if model.model_version != M2_METAMODEL_VERSION:
            raise EncodingError("loaded model version mismatch")
        manifest = json.loads(args.assignments.read_text()) if args.assignments else None
        reservations = tuple(tuple(int(x, 0) for x in value.split("/")) for value in args.reserve)
        if any(len(pattern) != 2 for pattern in reservations):
            raise EncodingError("reservations require CODE/MASK")
        policy = EncodingPolicy(tuple(args.opcode) if args.opcode else EncodingPolicy().opcodes, reservations)
        plan = plan_model(model, policy, manifest)
        if args.explain or args.dry_run or plan.errors:
            print(plan.explain())
        if args.report:
            args.report.write_text(json.dumps(plan.to_dict(), indent=2) + "\n")
        plan.raise_for_errors()
        if not args.dry_run:
            save_model(apply_model_plan(model, plan), args.top_level if args.inplace else args.output)
    except (EncodingError, ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"encoding failed: {exc}\n")


if __name__ == "__main__":
    main()
