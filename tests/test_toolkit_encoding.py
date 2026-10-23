"""Exercise the alternate toolkit generator's real shared allocation helper."""
import importlib.util
import itertools
from pathlib import Path
from types import SimpleNamespace
import unittest

from m2isar.metamodel.attribute_info import OperandAttribute as A
from m2isar.transforms.encode_instructions import EncodingError, EncodingPolicy, apply_encoding_plan, plan_encodings
from m2isar.transforms.encode_instructions.planner import overlaps
from test_encoding_planner import add, instruction, operand

# Load the staged generator, not an extracted or reimplemented allocator.
# No parser/writer/session dependencies are needed to use its encoding helpers.
path = Path(__file__).resolve().parents[1] / "integrations/isaac-toolkit/generate_etiss_core_planner.py"
spec = importlib.util.spec_from_file_location("toolkit_generator_planner", path)
generator = importlib.util.module_from_spec(spec)
# The toolkit logger is an optional checkout dependency for these smoke tests.
# Resolve it from the sibling checkout without replacing any modules with mocks.
import sys
sibling = path.parents[2].parent / "isaac-toolkit"
if str(sibling) not in sys.path:
    sys.path.insert(0, str(sibling))
spec.loader.exec_module(generator)


def immediate_instruction(name, width=17):
    return instruction(name, operand("rd", direction=A.OUT), operand("imm", width, A.IS_IMM))


class ToolkitEncodingSmokeTests(unittest.TestCase):
    def assert_disjoint(self, result):
        instructions = [i for group in result.values() for i in group.values()]
        for a, b in itertools.combinations(instructions, 2):
            self.assertFalse(overlaps((a.code, a.mask), (b.code, b.mask)))

    def test_same_instruction_name_in_distinct_sets(self):
        a, b = add(), add()
        source = {"First": {"ADD": a}, "Second": {"ADD": b}}
        result, plan = generator.encode_instruction_sets(source)
        self.assertEqual(len(plan.assignments), 2)
        self.assertEqual({i.name for group in result.values() for i in group.values()}, {"ADD"})
        self.assert_disjoint(result)
        self.assertFalse(a.has_encoding)
        self.assertFalse(b.has_encoding)
        reversed_result, reversed_plan = generator.encode_instruction_sets(dict(reversed(list(source.items()))))
        self.assertEqual(plan, reversed_plan)
        self.assert_disjoint(reversed_result)

    def test_global_capacity_across_sets(self):
        source = {set_name: {f"LI{i:02d}": immediate_instruction(f"LI{i:02d}") for i in range(16)}
                  for set_name in ("First", "Second")}
        result, plan = generator.encode_instruction_sets(source)
        self.assertEqual(len(plan.assignments), 32)
        self.assert_disjoint(result)
        source["Second"]["EXTRA"] = immediate_instruction("EXTRA")
        with self.assertRaisesRegex(EncodingError, "no collision-free encoding remains"):
            generator.encode_instruction_sets(source)
        self.assertTrue(all(not i.has_encoding for group in source.values() for i in group.values()))

    def test_custom0_capacity_is_shared(self):
        source = {name: {f"I{i}": immediate_instruction(f"I{i}") for i in range(4)} for name in ("A", "B")}
        result, _ = generator.encode_instruction_sets(source, policy=EncodingPolicy(opcodes=(0x0B,)))
        self.assert_disjoint(result)
        self.assertTrue(all(i.code & 0x7F == 0x0B for group in result.values() for i in group.values()))
        source["B"]["EXTRA"] = immediate_instruction("EXTRA")
        with self.assertRaises(EncodingError):
            generator.encode_instruction_sets(source, policy=EncodingPolicy(opcodes=(0x0B,)))

    def test_mixed_width_masks(self):
        source = {"A": {"LI": immediate_instruction("LI", 17)},
                  "B": {"LI": immediate_instruction("LI", 16)}}
        result, _ = generator.encode_instruction_sets(source)
        self.assert_disjoint(result)
        patterns = [i.mask for group in result.values() for i in group.values()]
        self.assertNotEqual(*patterns)

    def test_existing_and_pinned_assignments(self):
        a = add()
        old = apply_encoding_plan([a], plan_encodings([a]))
        existing = {"Old": old}
        source = {"New": {"ADD": add()}}
        result, previous = generator.encode_instruction_sets(source, existing_per_set=existing)
        self.assert_disjoint(result)
        source["Other"] = {"ADD": add()}
        expanded, plan = generator.encode_instruction_sets(source, existing_per_set=existing, assignments=previous.to_dict())
        self.assert_disjoint(expanded)
        self.assertIn(previous.assignments[0], plan.assignments)

    def test_manual_overlap_with_different_masks_is_rejected(self):
        a, b = immediate_instruction("A", 17), immediate_instruction("B", 16)
        a = apply_encoding_plan([a], plan_encodings([a]))[0]
        b = apply_encoding_plan([b], plan_encodings([b]))[0]
        self.assertNotEqual(a.mask, b.mask)
        with self.assertRaisesRegex(EncodingError, "overlapping generated encodings"):
            generator.validate_instruction_sets({"First": [a], "Second": [b]})
        with self.assertRaises(EncodingError):
            generator.encode_instruction_sets({}, existing_per_set={"First": [a], "Second": [b]})

    def test_gpr_metadata_preserved_and_unsupported_class_rejected(self):
        instr = add()
        for op in instr.operands.values():
            op.attributes[A.REG_CLASS] = [SimpleNamespace(value="GPR")]
            op.attributes[A.REG_TYPE] = [SimpleNamespace(value="s32")]
        result, _ = generator.encode_instruction_sets({"Demo": {"ADD": instr}})
        encoded = next(iter(result["Demo"].values()))
        self.assertEqual(encoded.operands["rs1"].attributes[A.REG_CLASS][0].value, "GPR")
        instr.operands["rs1"].attributes[A.REG_CLASS][0].value = "FPR"
        with self.assertRaisesRegex(EncodingError, "unsupported REG_CLASS"):
            generator.encode_instruction_sets({"Demo": {"ADD": instr}})
        self.assertFalse(instr.has_encoding)

    def test_cli_options(self):
        args = generator.get_parser().parse_args(["--encoding-opcode", "0x0b", "--encoding-reserve", "0x2b/0x7f"])
        self.assertEqual(args.encoding_opcode, [0x0B])
        self.assertEqual(args.encoding_reserve, [(0x2B, 0x7F)])
        with self.assertRaises(Exception):
            generator.parse_reservation("0x80/0x7f")


if __name__ == "__main__":
    unittest.main()
