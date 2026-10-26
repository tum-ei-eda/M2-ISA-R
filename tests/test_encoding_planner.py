"""Smoke tests using real metamodel instructions, without external fixtures."""
import contextlib
import io
import json
from pathlib import Path
import pickle
import tempfile
from types import SimpleNamespace
import unittest

from m2isar.metamodel import M2Model, M2_METAMODEL_VERSION, arch
from m2isar.metamodel.attribute_info import OperandAttribute as A
from m2isar.transforms.encode_instructions import (
    EncodingError, EncodingPolicy, apply_encoding_plan, apply_model_plan,
    plan_encodings, plan_model,
)
from m2isar.transforms.encode_instructions.encoder import main
from m2isar.transforms.encode_instructions.planner import overlaps


def operand(name, width=5, kind=A.IS_REG, direction=A.IN, signed=False):
    return arch.Parameter(name, None, {kind: [], direction: []}, width, signed)


def instruction(name, *operands):
    with contextlib.redirect_stdout(io.StringIO()):
        return arch.Instruction(name, {}, {o.name: o for o in operands}, [None], None, None, None, None)


def add(name="ADD"):
    return instruction(name, operand("rs1"), operand("rs2"), operand("rd", direction=A.OUT))


def model_with_shared_instruction():
    instr = add()
    extension = SimpleNamespace(instructions={}, unencoded_instructions={instr.name: instr})
    core = SimpleNamespace(instructions={}, unencoded_instructions={instr.name: instr}, _instructions_by_ext={}, _instructions_by_class={})
    return M2Model(M2_METAMODEL_VERSION, {"CPU": core}, {"EXT": extension}, {})


class PlannerSmokeTests(unittest.TestCase):
    def test_determinism_and_nonmutation(self):
        a, b = add("A"), add("B")
        first = plan_encodings([a, b])
        self.assertEqual(first, plan_encodings([b, a]))
        self.assertFalse(a.has_encoding)
        encoded = apply_encoding_plan([a, b], first)
        self.assertFalse(a.has_encoding)
        self.assertTrue(all(i.has_encoding and i.size == 32 for i in encoded))
        self.assertFalse(overlaps((encoded[0].code, encoded[0].mask), (encoded[1].code, encoded[1].mask)))
        # Independently recompute the emitted mask and code from metamodel fields.
        for instr in encoded:
            mask = code = offset = 0
            for field in reversed(instr.encoding):
                if isinstance(field, arch.BitVal):
                    mask |= ((1 << field.length) - 1) << offset
                    code |= field.value << offset
                    offset += field.length
                else:
                    offset += field.range.length
            self.assertEqual((offset, code, mask), (32, instr.code, instr.mask))

    def test_width_signedness_inout_and_multiple_immediates(self):
        instr = instruction("SHIFT", operand("acc", direction=A.INOUT),
                            operand("amount", 3, A.IS_IMM, signed=True), operand("mode", 2, A.IS_IMM))
        encoded = apply_encoding_plan([instr], plan_encodings([instr]))[0]
        fields = [f for f in encoded.encoding if isinstance(f, arch.BitField)]
        self.assertEqual({f.name: f.range.length for f in fields}, {"acc": 5, "amount": 3, "mode": 2})
        self.assertEqual(encoded.fields["amount"].ty.size, 3)
        self.assertTrue(encoded.operands["amount"].signed)

    def test_encoding_reprocessed_by_metamodel(self):
        instr = instruction("SIGNED", operand("rs"), operand("rd", direction=A.OUT),
                            operand("imm", 9, A.IS_IMM, signed=True))
        encoded = apply_encoding_plan([instr], plan_encodings([instr]))[0]
        reconstructed = arch.Instruction(encoded.name, {}, encoded.operands,
                                         encoded.encoding, None, None, None, None)
        self.assertEqual((reconstructed.code, reconstructed.mask, reconstructed.size),
                         (encoded.code, encoded.mask, encoded.size))
        self.assertEqual(reconstructed.fields["imm"].ty.size, 9)

    def test_no_silently_dropped_operands(self):
        invalid = instruction("TOO_BIG", *(operand("s" + str(i)) for i in range(3)),
                              operand("rd", direction=A.OUT), operand("imm", 6, A.IS_IMM))
        valid = add()
        plan = plan_encodings([valid, invalid])
        self.assertIn("no layout fits", plan.errors[0])
        with self.assertRaises(EncodingError):
            apply_encoding_plan([valid, invalid], plan, copy=False)
        self.assertFalse(valid.has_encoding)

    def test_ambiguous_attributes_rejected(self):
        instr = add()
        instr.operands["rs1"].attributes[A.OUT] = []
        self.assertIn("exactly one", plan_encodings([instr]).errors[0])

    def test_existing_overlap_and_exhaustion(self):
        policy = EncodingPolicy(opcodes=(0x0B,))
        plan = plan_encodings([add()], policy, existing=[(0x0B, 0x7F)])
        self.assertTrue(plan.errors)
        plan = plan_encodings([add()], existing=[(0x0B, 0x7F)])
        self.assertFalse(plan.errors)
        self.assertNotEqual(plan.assignments[0].code & 0x7F, 0x0B)

    def test_manifest_stability_and_conflict(self):
        previous = plan_encodings([add("Z")])
        new = plan_encodings([add("A"), add("Z")], assignments=previous.to_dict())
        self.assertFalse(new.errors)
        self.assertEqual(new.assignments[1], previous.assignments[0])
        blocked = plan_encodings([add("Z")], existing=[(0x0B, 0x7F)], assignments=previous.to_dict())
        self.assertTrue(blocked.errors)

    def test_model_aliases_and_collection_updates(self):
        original = model_with_shared_instruction()
        plan = plan_model(original)
        self.assertEqual(len(plan.assignments), 1)
        encoded = apply_model_plan(original, plan)
        self.assertTrue(original.sets["EXT"].unencoded_instructions)
        self.assertFalse(encoded.cores["CPU"].unencoded_instructions)
        self.assertIs(next(iter(encoded.sets["EXT"].instructions.values())), next(iter(encoded.cores["CPU"].instructions.values())))
        self.assertEqual(len(plan_model(encoded).assignments), 0)
        self.assertIsNone(encoded.cores["CPU"]._instructions_by_ext)

    def test_model_preserves_behavior_descriptor_identity(self):
        original = model_with_shared_instruction()
        instr = original.sets["EXT"].unencoded_instructions["ADD"]
        instr.operation.descriptor = instr.fields["rs1"]
        encoded = apply_model_plan(original, plan_model(original))
        result = next(iter(encoded.sets["EXT"].instructions.values()))
        self.assertIs(result.operation.descriptor, result.fields["rs1"])

    def test_more_layouts_and_operand_coverage(self):
        requests = [
            instruction("NOP"),
            instruction("LI", operand("rd", direction=A.OUT), operand("imm", 17, A.IS_IMM)),
            instruction("R4", *(operand("s" + str(i)) for i in range(3)), operand("rd", direction=A.OUT)),
            instruction("PAIR", operand("s1"), operand("s2"), operand("d1", direction=A.OUT), operand("d2", direction=A.OUT)),
        ]
        plan = plan_encodings(requests)
        self.assertFalse(plan.errors)
        for encoded in apply_encoding_plan(requests, plan):
            self.assertEqual(set(encoded.operands), {f.name for f in encoded.encoding if isinstance(f, arch.BitField)})
        too_many = instruction("THREE_DESTS", *(operand("d" + str(i), direction=A.OUT) for i in range(3)))
        self.assertTrue(plan_encodings([too_many]).errors)

    def test_reservation_exhaustion(self):
        plan = plan_encodings([instruction("NOP")], EncodingPolicy(reservations=((0, 0),)))
        self.assertTrue(plan.errors)

    def test_stale_plan_is_transactional(self):
        first, second = add("A"), add("B")
        plan = plan_encodings([first, second])
        second.operands["rs1"]._size = 6
        with self.assertRaises(EncodingError):
            apply_encoding_plan([first, second], plan, copy=False)
        self.assertFalse(first.has_encoding)

    def test_cli_failure_leaves_output_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.m2isarmodel"
            output = Path(directory) / "output.m2isarmodel"
            source.write_bytes(pickle.dumps(model_with_shared_instruction()))
            output.write_bytes(b"existing output")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main([str(source), "-o", str(output), "--reserve", "0/0"])
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(output.read_bytes(), b"existing output")

    def test_cli_dry_run_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output, report = [Path(directory) / name for name in ("input.m2isarmodel", "output.m2isarmodel", "report.json")]
            source.write_bytes(pickle.dumps(model_with_shared_instruction()))
            before = source.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(source), "--dry-run", "--report", str(report)])
            self.assertEqual(source.read_bytes(), before)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(report.read_text())["errors"], [])
            main([str(source), "-o", str(output), "--assignments", str(report)])
            encoded = pickle.loads(output.read_bytes())
            self.assertEqual(len(encoded.cores["CPU"].instructions), 1)
            self.assertEqual(source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
