"""Integration coverage for the future-paper set parser and typed writer port."""
from pathlib import Path
import tempfile
import pickle
from unittest.mock import MagicMock, patch
import unittest

from m2isar.backends.coredsl2.writer import gen_cdsl_code, write_cdsl_default, write_cdsl_splitted
from m2isar.frontends.coredsl2_set.parser import main, parse_cdsl2_set
from m2isar.metamodel import M2Model, M2_METAMODEL_VERSION, type_info
from m2isar.metamodel.attribute_info import OperandAttribute as A
from m2isar.transforms.encode_instructions import apply_model_plan, plan_model


SOURCE = '''InstructionSet Custom {
    instructions {
        ADD {
            operands: {
                unsigned<5> rs1 [[in]] [[is_reg]];
                unsigned<5> rs2 [[in]] [[is_reg]];
                unsigned<5> rd [[out]] [[is_reg]];
            }
            encoding: auto;
            assembly: {"add", "{rd}, {rs1}, {rs2}"};
            behavior: { rd = rs1 + rs2; }
        }
        LI {
            operands: {
                unsigned<5> rd [[out]] [[is_reg]];
                signed<12> imm [[in]] [[is_imm]];
            }
            encoding: auto;
            behavior: {}
        }
    }
}'''


class FuturePaperPortTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.source = self.root / "Custom.core_desc"
        self.source.write_text(SOURCE)

    def model(self):
        return M2Model(M2_METAMODEL_VERSION, {}, parse_cdsl2_set(self.source), {})

    def test_shared_writer_and_compatibility_api(self):
        from m2isar.backends.coredsl2_set.writer import gen_cdsl_code as compatibility
        self.assertIs(compatibility, gen_cdsl_code)
        model = self.model()
        output = self.root / "shared.core_desc"
        write_cdsl_default(model, output, writer_kwargs={"reduced": False})
        self.assertEqual(set(parse_cdsl2_set(output)["Custom"].unencoded_instructions), {"ADD", "LI"})
        split = self.root / "split"
        split.mkdir()
        write_cdsl_splitted(model, split, writer_kwargs={"reduced": False})
        for name in ("ADD", "LI"):
            parsed = parse_cdsl2_set(split / "Custom" / f"{name}.core_desc")
            self.assertEqual(set(parsed["Custom"].unencoded_instructions), {name})
        self.assertEqual(set(model.sets["Custom"].unencoded_instructions), {"ADD", "LI"})

    def test_callable_parser_keeps_operands_local_and_typed(self):
        sets = parse_cdsl2_set(self.source, None)
        self.assertFalse((self.root / "gen_model").exists())
        instruction_set = sets["Custom"]
        self.assertEqual(instruction_set.parameters, {})
        add = instruction_set.unencoded_instructions["ADD"]
        self.assertEqual(add.operands["rs1"].attributes, {A.IN: [], A.IS_REG: []})
        self.assertEqual(add.fields["rs1"].ty.size, 5)
        li = instruction_set.unencoded_instructions["LI"]
        self.assertTrue(li.operands["imm"].signed)
        self.assertEqual(li.fields["imm"].ty.size, 12)

    def test_auto_encoding_roundtrip_and_model_allocation(self):
        model = self.model()
        text = gen_cdsl_code(model, with_includes=False)
        self.source.write_text(text)
        reparsed = self.model()
        self.assertEqual(set(reparsed.sets["Custom"].unencoded_instructions), {"ADD", "LI"})
        encoded = apply_model_plan(reparsed, plan_model(reparsed))
        self.assertFalse(encoded.sets["Custom"].unencoded_instructions)
        self.source.write_text(gen_cdsl_code(encoded, with_includes=False))
        final = self.model()
        self.assertEqual({i.name for i in final.sets["Custom"].instructions.values()}, {"ADD", "LI"})
        self.assertTrue(model.sets["Custom"].unencoded_instructions)
        li = next(i for i in final.sets["Custom"].instructions.values() if i.name == "LI")
        self.assertTrue(li.operands["imm"].signed)
        self.assertEqual(li.fields["imm"].ty.kind, type_info.TypeKind.INT)
        self.assertEqual(li.operands["imm"].attributes, {A.IN: [], A.IS_IMM: []})

    def test_legacy_assembly_and_cli_output(self):
        text = gen_cdsl_code(self.model(), with_includes=False, legacy=True)
        self.assertIn('assembly: "{rd}, {rs1}, {rs2}";', text)
        self.assertNotIn('assembly: {"add"', text)
        main([str(self.source)])
        self.assertTrue((self.root / "gen_model" / "Custom.m2isarmodel").is_file())

    def test_nested_casts_roundtrip_after_type_inference(self):
        self.source.write_text(SOURCE.replace(
            "rd = rs1 + rs2;",
            "unsigned<32> value = (unsigned<32>)(rs1 ^ "
            "(unsigned<32>)(unsigned<32>)(rs2 >> (unsigned<32>)(8))); "
            "rd = (unsigned)value;",
        ))
        text = gen_cdsl_code(self.model(), with_includes=False)
        self.assertIn("(unsigned)", text)
        self.source.write_text(text)
        self.assertIn("ADD", self.model().sets["Custom"].unencoded_instructions)

    def test_include_prefixes_are_honored(self):
        model = self.model()
        model.sets["Custom"].extension = ["RV32I", "tum_csr"]
        text = gen_cdsl_code(model, includes_prefix="base/", tum_includes_prefix="tum/")
        self.assertIn('import "base/RVI.core_desc"', text)
        self.assertIn('import "tum/tum_mod.core_desc"', text)

    def test_inherited_only_set_omits_empty_blocks(self):
        self.source.write_text(SOURCE + "\nInstructionSet Aggregate extends Custom {}\n")
        model = self.model()
        for legacy in (False, True):
            text = gen_cdsl_code(model, with_includes=False, legacy=legacy)
            aggregate = text.split("InstructionSet Aggregate", 1)[1]
            self.assertNotIn("instructions", aggregate)
            self.assertNotIn("functions", aggregate)
            self.source.write_text(text)
            self.assertIn("Aggregate", self.model().sets)

    def test_unresolved_parameters_and_always_blocks_survive_export(self):
        self.source.write_text(SOURCE.replace("    instructions {", """    architectural_state { unsigned<32> XLEN; }
    always { before {} }
    instructions {""", 1))
        model = self.model()
        self.assertIsNone(model.sets["Custom"].parameters["XLEN"].value)
        text = gen_cdsl_code(model, with_includes=False)
        self.source.write_text(text)
        reparsed = self.model()
        self.assertIsNone(reparsed.sets["Custom"].parameters["XLEN"].value)
        self.assertEqual(set(reparsed.sets["Custom"].always_blocks), {"before"})

    def test_core_parser_and_encoder_register_instruction_width(self):
        from m2isar.frontends.coredsl2.parser import main as parse_core
        source = SOURCE.replace("InstructionSet Custom", "Core Custom")
        source = source.replace("[[in]] [[is_reg]]", '[[in]] [[is_reg]] [[reg_class="GPR"]]')
        self.source.write_text(source)
        parse_core([str(self.source)])
        model_path = self.root / "gen_model" / "Custom.m2isarmodel"
        model = pickle.loads(model_path.read_bytes())
        core = model.cores["Custom"]
        self.assertFalse(core.instr_classes)
        self.assertEqual(core.unencoded_instructions["ADD"].operands["rs1"].attributes[A.REG_CLASS][0].value, "GPR")
        encoded = apply_model_plan(model, plan_model(model))
        self.assertEqual(encoded.cores["Custom"].instr_classes, {32})
        self.assertFalse(encoded.cores["Custom"].unencoded_instructions)
        self.assertFalse(core.instr_classes)

    def test_set_viewer_builds_unencoded_group_without_display(self):
        from m2isar.backends.viewer import viewer
        model_path = self.root / "Custom.m2isarmodel"
        model_path.write_bytes(pickle.dumps(self.model()))
        tree = MagicMock()
        tree.insert.side_effect = lambda *args, **kwargs: str(tree.insert.call_count)
        with patch.object(viewer.tk, "Tk"), patch.object(viewer.ttk, "Treeview", return_value=tree), patch.object(viewer.ttk, "Scrollbar"):
            viewer.main([str(model_path)], sets_only=True)
        labels = [call.kwargs.get("text") for call in tree.insert.call_args_list]
        self.assertIn("Custom", labels)
        self.assertIn("Unencoded", labels)
        self.assertIn("Custom : ADD", labels)
        self.assertIn("Custom : LI", labels)


if __name__ == "__main__":
    unittest.main()
