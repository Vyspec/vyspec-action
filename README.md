# Vyspec QA for GitHub Actions

Run Vyspec against the application already started by your GitHub Actions workflow. The Action
installs the pinned public Vyspec CLI and Chromium, waits for the application on loopback port
`3000`, executes either a saved or one-time Run Profile, writes the canonical JSON result, and
creates or updates one pull-request report.

Vyspec executes on the customer's GitHub runner. Source code, environment variables, and
application credentials remain on that runner; only bounded browser observations and Run results
are sent to Vyspec.

## Saved Run Profile

Start the application before invoking Vyspec:

```yaml
name: Vyspec QA

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  qa:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - uses: actions/setup-node@v6
        with:
          node-version: 22
          cache: npm

      - run: npm ci
      - run: npm run dev -- --host 127.0.0.1 --port 3000 &

      - name: Run Vyspec QA
        id: vyspec
        uses: ramonzubiate/vyspec-action@v1
        with:
          project-api-key: ${{ secrets.VSY_PROJECT_API_KEY }}
          run-profile-id: 123e4567-e89b-42d3-a456-426614174000
```

The Action waits for the application, so a separate readiness loop is unnecessary.

## One-time Run Profile

Generate a one-time profile from a ticket, pull-request description, or another CI step, then pass
its repository-relative path:

```yaml
- name: Build one-time QA instructions
  env:
    ISSUE_BODY: ${{ github.event.pull_request.body }}
  run: |
    jq -n \
      --arg instructions "${ISSUE_BODY}" \
      '{
        qa_instructions: $instructions,
        execution_depth: "balanced",
        start_path: "/",
        browser_preset: "desktop_chrome"
      }' > .vyspec-one-time.json

- name: Run one-time Vyspec QA
  uses: ramonzubiate/vyspec-action@v1
  with:
    project-api-key: ${{ secrets.VSY_PROJECT_API_KEY }}
    one-time-profile-file: .vyspec-one-time.json
```

Exactly one of `run-profile-id` and `one-time-profile-file` is required.

## Inputs

| Input | Required | Description |
| --- | --- | --- |
| `project-api-key` | Yes | Revocable Project API key stored in GitHub Actions secrets. |
| `run-profile-id` | One execution source | Saved Run Profile UUID. |
| `one-time-profile-file` | One execution source | Path to one-time Run Profile JSON. |
| `run-notes-file` | No | Path to a JSON array of notes attached to the Run. |
| `app-ready-timeout` | No | Seconds to wait for port 3000; defaults to 120. |
| `github-token` | No | Token used for the PR report; defaults to `github.token`. |

Automatic-login Session Profiles may require additional credential names. Store those exact names
as GitHub Actions secrets and expose them only to the Vyspec job.

## Outputs

| Output | Description |
| --- | --- |
| `exit-code` | Operational exit code. |
| `finding-count` | Number of confirmed findings. |
| `qa-verdict` | `passed` or `failed` after completed execution. |
| `result-file` | Path to the canonical JSON result. |
| `run-id` | Vyspec Run ID. |
| `run-url` | Authenticated Vyspec Run report URL. |

A confirmed QA failure is a successful execution and therefore does not fail the workflow. An
installation, authentication, browser, connectivity, cancellation, or protocol failure does fail
the workflow. The PR report shows the QA verdict separately.

## Supported runner

The first release supports GitHub-hosted Ubuntu runners. The customer application must listen on
`127.0.0.1:3000`; arbitrary target URLs are intentionally unsupported.
