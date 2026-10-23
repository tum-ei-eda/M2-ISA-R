"""Integration coverage for the future-paper set parser and typed writer port."""
from pathlib import Path
import tempfile
import unittest

from m2isar.backends.coredsl2_set.writer import gen_cdsl_code
from m2isar.frontends.coredsl2_set.parser import main, parse_cdsl2_set
from m2isar.metamodel import M2Model, M2_METAMODEL_VERSION
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
            behavior: {}
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

    def test_legacy_assembly_and_cli_output(self):
        text = gen_cdsl_code(self.model(), with_includes=False, legacy=True)
        self.assertIn('assembly: "{rd}, {rs1}, {rs2}";', text)
        self.assertNotIn('assembly: {"add"', text)
        main([str(self.source)])
        self.assertTrue((self.root / "gen_model" / "Custom.m2isarmodel").is_file())

    def test_include_prefixes_are_honored(self):
        model = self.model()
        model.sets["Custom"].extension = ["RV32I", "tum_csr"]
        text = gen_cdsl_code(model, includes_prefix="base/", tum_includes_prefix="tum/")
        self.assertIn('import "base/RV32I.core_desc"', text)
        self.assertIn('import "tum/tum_mod.core_desc"', text)


if __name__ == "__main__":
    unittest.main()
