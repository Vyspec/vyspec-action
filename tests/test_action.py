import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
ACTION = ROOT / "action.yml"
README = ROOT / "README.md"


class ActionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ACTION.read_text(encoding="utf-8")
        parsed = json.loads(subprocess.check_output(
            [
                "ruby",
                "-rjson",
                "-ryaml",
                "-e",
                'puts JSON.generate(YAML.safe_load(File.read("action.yml"), aliases: true))',
            ],
            cwd=ROOT,
            text=True,
        ))
        cls.steps = {step["name"]: step for step in parsed["runs"]["steps"]}

    def run_validation(self, **values: str) -> subprocess.CompletedProcess[str]:
        environment = {
            **os.environ,
            "RUNNER_OS": "Linux",
            "VSY_INSTRUCTIONS": "",
            "VSY_INSTRUCTIONS_FILE": "",
            "VSY_PROJECT_API_KEY": "project-key",
            "VSY_RUN_NOTES_FILE": "",
            "VSY_RUN_PROFILE_ID": "",
            "VSY_SESSION_PROFILE_ID": "",
            "VSY_START_PATH": "",
            **values,
        }
        return subprocess.run(
            ["bash", "-c", self.steps["Validate Vyspec configuration"]["run"]],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_uses_the_immutable_public_cli_release(self) -> None:
        self.assertRegex(
            self.source,
            r'VYSPEC_CLI_VERSION: "\d+\.\d+\.\d+"',
        )
        self.assertIn('python -m pip install "vyspec==${VYSPEC_CLI_VERSION}"', self.source)
        self.assertNotIn("GITHUB_ACTION_PATH", self.source)

    def test_defaults_to_the_public_vyspec_origin(self) -> None:
        self.assertIn("https://www.vyspec.com", self.source)
        self.assertNotIn("https://app.vyspec.com", self.source)

    def test_pins_third_party_actions_to_full_commit_shas(self) -> None:
        references = re.findall(r"uses: ([^\s]+)", self.source)
        self.assertEqual(len(references), 1)
        for reference in references:
            self.assertRegex(reference, r"@(?:[0-9a-f]{40})$")

    def test_accepts_exactly_one_execution_source(self) -> None:
        self.assertIn(
            "Set exactly one of run-profile-id, instructions, or instructions-file.",
            self.source,
        )
        self.assertIn('arguments+=(--profile "${VSY_RUN_PROFILE_ID}")', self.source)
        self.assertIn('arguments+=(--instructions "${VSY_INSTRUCTIONS}")', self.source)
        self.assertIn(
            'arguments+=(--instructions-file "${VSY_INSTRUCTIONS_FILE}")',
            self.source,
        )
        self.assertNotIn("one-time-profile-file", self.source)
        self.assertNotIn("--one-time", self.source)

        self.assertEqual(
            self.run_validation(VSY_RUN_PROFILE_ID="profile-id").returncode,
            0,
        )
        self.assertEqual(
            self.run_validation(VSY_INSTRUCTIONS="Verify checkout").returncode,
            0,
        )
        missing = self.run_validation()
        self.assertEqual(missing.returncode, 2)
        self.assertIn("Set exactly one", missing.stdout)
        conflicting = self.run_validation(
            VSY_INSTRUCTIONS="Verify checkout",
            VSY_RUN_PROFILE_ID="profile-id",
        )
        self.assertEqual(conflicting.returncode, 2)

    def test_supports_optional_direct_run_context(self) -> None:
        self.assertIn("session-profile-id:", self.source)
        self.assertIn("start-path:", self.source)
        self.assertIn(
            'arguments+=(--session-profile "${VSY_SESSION_PROFILE_ID}")',
            self.source,
        )
        self.assertIn('arguments+=(--start-path "${VSY_START_PATH}")', self.source)
        self.assertIn(
            "session-profile-id and start-path are available only for direct instructions.",
            self.source,
        )
        self.assertEqual(
            self.run_validation(
                VSY_INSTRUCTIONS="Verify account",
                VSY_SESSION_PROFILE_ID="session-id",
                VSY_START_PATH="/account",
            ).returncode,
            0,
        )
        saved = self.run_validation(
            VSY_RUN_PROFILE_ID="profile-id",
            VSY_SESSION_PROFILE_ID="session-id",
        )
        self.assertEqual(saved.returncode, 2)
        self.assertIn("available only for direct instructions", saved.stdout)

    def test_invokes_the_cli_with_direct_run_inputs_as_exact_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            fake_vsy = temporary / "vsy"
            fake_vsy.write_text(
                '#!/usr/bin/env bash\nprintf \'%s\\0\' "$@" > "${VYSPEC_ARGS_FILE}"\n',
                encoding="utf-8",
            )
            fake_vsy.chmod(0o755)
            args_file = temporary / "args"
            output_file = temporary / "output"
            result_file = temporary / "result.json"
            instructions = "Verify checkout totals and account ownership."
            environment = {
                **os.environ,
                "CI": "true",
                "GITHUB_OUTPUT": str(output_file),
                "PATH": f"{temporary}:{os.environ['PATH']}",
                "VSY_APP_READY_TIMEOUT": "120",
                "VSY_CI_BRANCH": "feature/direct-qa",
                "VSY_CI_PROVIDER": "github",
                "VSY_CI_PULL_REQUEST_NUMBER": "42",
                "VSY_CI_REPOSITORY": "vyspec/customer-app",
                "VSY_INSTRUCTIONS": instructions,
                "VSY_INSTRUCTIONS_FILE": "",
                "VSY_PROJECT_API_KEY": "project-key",
                "VSY_RESULT_FILE": str(result_file),
                "VSY_RUN_NOTES_FILE": "",
                "VSY_RUN_PROFILE_ID": "",
                "VSY_SESSION_PROFILE_ID": "423e4567-e89b-42d3-a456-426614174000",
                "VSY_START_PATH": "/account",
                "VYSPEC_ARGS_FILE": str(args_file),
            }

            completed = subprocess.run(
                ["bash", "-c", self.steps["Run Vyspec QA"]["run"]],
                cwd=ROOT,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            arguments = [
                value.decode()
                for value in args_file.read_bytes().split(b"\0")
                if value
            ]
            self.assertEqual(arguments, [
                "run",
                "--app-ready-timeout",
                "120",
                "--result-file",
                str(result_file),
                "--instructions",
                instructions,
                "--session-profile",
                "423e4567-e89b-42d3-a456-426614174000",
                "--start-path",
                "/account",
            ])

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
        self.assertIn("pull-request-number:", self.source)
        self.assertIn("ci-branch:", self.source)
        self.assertIn("VSY_PULL_REQUEST_NUMBER", self.source)
        self.assertIn("/api/v1/integrations/github/report", self.source)
        self.assertIn("github.repository_id", self.source)
        self.assertNotIn("actions/github-script", self.source)
        self.assertNotIn("github-token:", self.source)
        self.assertIn('run: exit "${VSY_EXIT_CODE:-2}"', self.source)

    def test_sends_the_canonical_result_to_the_vyspec_github_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            fake_curl = temporary / "curl"
            fake_curl.write_text(
                '#!/usr/bin/env bash\nprintf \'%s\\0\' "$@" > "${CURL_ARGS_FILE}"\n',
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            result_file = temporary / "result.json"
            result_file.write_text(json.dumps({
                "findings": [],
                "qa_verdict": "passed",
                "run_id": "00000000-0000-4000-8000-000000000001",
                "run_url": "https://app.vyspec.test/app/runs/00000000-0000-4000-8000-000000000001",
            }), encoding="utf-8")
            args_file = temporary / "curl-args"
            completed = subprocess.run(
                ["bash", "-c", self.steps["Update pull-request report"]["run"]],
                cwd=ROOT,
                env={
                    **os.environ,
                    "CURL_ARGS_FILE": str(args_file),
                    "PATH": f"{temporary}:{os.environ['PATH']}",
                    "VSY_API_URL": "https://app.vyspec.test",
                    "VSY_PROJECT_API_KEY": "project-key",
                    "VSY_PULL_REQUEST_NUMBER": "12",
                    "VSY_REPOSITORY_ID": "42",
                    "VSY_RESULT_FILE": str(result_file),
                },
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            arguments = [
                value.decode()
                for value in args_file.read_bytes().split(b"\0")
                if value
            ]
            self.assertIn(
                "https://app.vyspec.test/api/v1/integrations/github/report",
                arguments,
            )
            payload = json.loads(arguments[arguments.index("--data") + 1])
            self.assertEqual(payload["change_request_number"], 12)
            self.assertEqual(payload["provider_repository_id"], "42")
            self.assertEqual(payload["result"]["qa_verdict"], "passed")

    def test_readme_documents_saved_and_direct_usage(self) -> None:
        readme = README.read_text(encoding="utf-8")
        self.assertIn("run-profile-id:", readme)
        self.assertIn("instructions:", readme)
        self.assertIn("instructions-file:", readme)
        self.assertIn("session-profile-id:", readme)
        self.assertIn("start-path:", readme)
        self.assertIn("`pull-request-number`", readme)
        self.assertIn("`ci-branch`", readme)
        self.assertNotIn("pull-requests: write", readme)
        self.assertIn("Vyspec GitHub App", readme)
        self.assertIn("127.0.0.1:3000", readme)


if __name__ == "__main__":
    unittest.main()
