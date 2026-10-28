"""Compatibility with aggregate sets emitted by the shared typed writer."""
from pathlib import Path
import tempfile
import unittest

from m2isar.frontends.coredsl2_set.parser import parse_cdsl2_set


class InheritedSetTests(unittest.TestCase):
    def test_inherited_only_set_retains_parent_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "aggregate.core_desc"
            source.write_text('''InstructionSet Parent {
    instructions {
        CUSTOM { encoding: 32'h0000000b; behavior: {} }
    }
}
InstructionSet Aggregate extends Parent {}
''')
            models = parse_cdsl2_set(source, [])
            aggregate = models["Aggregate"]
            self.assertEqual(aggregate.extension, ["Parent"])
            self.assertEqual({instruction.name for instruction in models["Parent"].instructions.values()}, {"CUSTOM"})


if __name__ == "__main__":
    unittest.main()
