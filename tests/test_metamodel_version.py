# SPDX-License-Identifier: Apache-2.0
import unittest

from m2isar.metamodel import M2Model, M2_METAMODEL_VERSION, check_model_version


class MetamodelVersionTest(unittest.TestCase):
    def test_matching_model_version_is_accepted(self):
        model = M2Model(M2_METAMODEL_VERSION, {}, {}, {})
        self.assertIsNone(check_model_version(model, "test consumer"))

    def test_mismatched_version_fails_with_regeneration_guidance(self):
        model = M2Model(M2_METAMODEL_VERSION - 1, {}, {}, {})
        with self.assertRaisesRegex(
            RuntimeError,
            rf"test consumer supports metamodel version {M2_METAMODEL_VERSION}.*"
            rf"loaded model uses version {M2_METAMODEL_VERSION - 1}.*Regenerate",
        ):
            check_model_version(model, "test consumer")


if __name__ == "__main__":
    unittest.main()
