import unittest
from diff_diet.classifier import (
    FileCategory,
    classify_path,
    get_priority_weight,
    is_noise_category,
)


class TestClassifier(unittest.TestCase):
    def test_lockfile_classification(self):
        self.assertEqual(classify_path("package-lock.json"), FileCategory.LOCKFILE)
        self.assertEqual(classify_path("sub/dir/pnpm-lock.yaml"), FileCategory.LOCKFILE)
        self.assertEqual(classify_path("Cargo.lock"), FileCategory.LOCKFILE)
        self.assertEqual(classify_path("poetry.lock"), FileCategory.LOCKFILE)
        self.assertEqual(classify_path("go.sum"), FileCategory.LOCKFILE)

    def test_minified_and_sourcemaps(self):
        self.assertEqual(classify_path("dist/bundle.min.js"), FileCategory.MINIFIED)
        self.assertEqual(classify_path("static/style.min.css"), FileCategory.MINIFIED)
        self.assertEqual(classify_path("dist/bundle.js.map"), FileCategory.SOURCEMAP)

    def test_generated_stubs(self):
        self.assertEqual(classify_path("src/api.generated.ts"), FileCategory.GENERATED)
        self.assertEqual(classify_path("proto/service.pb.go"), FileCategory.GENERATED)
        self.assertEqual(classify_path("schema.d.ts"), FileCategory.GENERATED)
        self.assertEqual(classify_path("lib/model.g.dart"), FileCategory.GENERATED)

    def test_source_code(self):
        self.assertEqual(classify_path("src/core/engine.py"), FileCategory.SOURCE)
        self.assertEqual(classify_path("components/Button.tsx"), FileCategory.SOURCE)
        self.assertEqual(classify_path("crates/parser/src/lib.rs"), FileCategory.SOURCE)
        self.assertEqual(classify_path("pkg/server/handler.go"), FileCategory.SOURCE)

    def test_tests_and_snapshots(self):
        self.assertEqual(classify_path("tests/test_auth.py"), FileCategory.TEST)
        self.assertEqual(classify_path("src/utils.spec.ts"), FileCategory.TEST)
        self.assertEqual(classify_path("tests/__snapshots__/view.snap"), FileCategory.SNAPSHOT)

    def test_docs_and_config(self):
        self.assertEqual(classify_path("README.md"), FileCategory.DOCS)
        self.assertEqual(classify_path("docs/architecture.rst"), FileCategory.DOCS)
        self.assertEqual(classify_path("pyproject.toml"), FileCategory.CONFIG)
        self.assertEqual(classify_path(".env.local"), FileCategory.CONFIG)
        self.assertEqual(classify_path("Dockerfile"), FileCategory.CONFIG)

    def test_noise_detection(self):
        self.assertTrue(is_noise_category(FileCategory.LOCKFILE))
        self.assertTrue(is_noise_category(FileCategory.MINIFIED))
        self.assertTrue(is_noise_category(FileCategory.SOURCEMAP))
        self.assertTrue(is_noise_category(FileCategory.GENERATED))
        self.assertFalse(is_noise_category(FileCategory.SOURCE))
        self.assertFalse(is_noise_category(FileCategory.TEST))

    def test_priority_weights(self):
        self.assertGreater(
            get_priority_weight(FileCategory.SOURCE),
            get_priority_weight(FileCategory.TEST),
        )
        self.assertGreater(
            get_priority_weight(FileCategory.TEST),
            get_priority_weight(FileCategory.DOCS),
        )
        self.assertGreater(
            get_priority_weight(FileCategory.DOCS),
            get_priority_weight(FileCategory.LOCKFILE),
        )


if __name__ == "__main__":
    unittest.main()
