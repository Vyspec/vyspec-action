import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ACTION = ROOT / "action.yml"
README = ROOT / "README.md"


class ActionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ACTION.read_text(encoding="utf-8")

    def test_uses_the_immutable_public_cli_release(self) -> None:
        self.assertIn('VYSPEC_CLI_VERSION: "0.1.2"', self.source)
        self.assertIn('python -m pip install "vyspec==${VYSPEC_CLI_VERSION}"', self.source)
        self.assertNotIn("GITHUB_ACTION_PATH", self.source)

    def test_pins_third_party_actions_to_full_commit_shas(self) -> None:
        references = re.findall(r"uses: ([^\s]+)", self.source)
        self.assertEqual(len(references), 2)
        for reference in references:
            self.assertRegex(reference, r"@(?:[0-9a-f]{40})$")

    def test_accepts_exactly_one_execution_source(self) -> None:
        self.assertIn("Set either run-profile-id or one-time-profile-file, not both.", self.source)
        self.assertIn("Set run-profile-id or one-time-profile-file.", self.source)
        self.assertIn('arguments+=(--profile "${VSY_RUN_PROFILE_ID}")', self.source)
        self.assertIn('arguments+=(--one-time "${VSY_ONE_TIME_PROFILE_FILE}")', self.source)

    def test_keeps_the_target_on_loopback_port_3000(self) -> None:
        self.assertNotIn("target-url:", self.source)
        self.assertNotIn("app-port:", self.source)
        self.assertNotIn("api-url:", self.source)
        self.assertIn("loopback port 3000", self.source)

    def test_exposes_the_provider_neutral_result(self) -> None:
        for output in (
            "exit-code:",
            "finding-count:",
            "qa-verdict:",
            "result-file:",
            "run-id:",
            "run-url:",
        ):
            self.assertIn(output, self.source)
        self.assertIn('--result-file "${VSY_RESULT_FILE}"', self.source)

    def test_reports_one_comment_and_preserves_operational_failure(self) -> None:
        self.assertIn("<!-- vyspec-qa-result -->", self.source)
        self.assertIn("github.rest.issues.updateComment", self.source)
        self.assertIn("github.rest.issues.createComment", self.source)
        self.assertIn("❌ Vyspec QA — FAILED", self.source)
        self.assertIn("✅ Vyspec QA — PASSED", self.source)
        self.assertIn('run: exit "${VSY_EXIT_CODE:-2}"', self.source)

    def test_readme_documents_saved_and_one_time_usage(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("run-profile-id:", readme)
        self.assertIn("one-time-profile-file:", readme)
        self.assertIn("pull-requests: write", readme)
        self.assertIn("127.0.0.1:3000", readme)


if __name__ == "__main__":
    unittest.main()
