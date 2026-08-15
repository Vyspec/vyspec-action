# Vyspec QA for GitHub Actions

Run Vyspec against the application already started by your GitHub Actions workflow. The Action
installs the pinned public Vyspec CLI and Chromium, waits for the application on loopback port
`3000`, executes either a saved Run Profile or direct QA instructions, writes the canonical JSON
result, and creates or updates one pull-request report.

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
        uses: Vyspec/vyspec-action@v1
        with:
          project-api-key: ${{ secrets.VSY_PROJECT_API_KEY }}
          run-profile-id: 123e4567-e89b-42d3-a456-426614174000
```

The Action waits for the application, so a separate readiness loop is unnecessary.

## Direct QA instructions

For one-off verification, provide the QA instructions without creating a saved Run Profile:

```yaml
- name: Verify this change with Vyspec
  uses: Vyspec/vyspec-action@v1
  with:
    project-api-key: ${{ secrets.VSY_PROJECT_API_KEY }}
    instructions: Verify the corrected checkout total and report any regression.
```

For longer instructions committed to the repository, use a plain-text file:

```yaml
- name: Run Vyspec from QA instructions
  uses: Vyspec/vyspec-action@v1
  with:
    project-api-key: ${{ secrets.VSY_PROJECT_API_KEY }}
    instructions-file: .vyspec/checkout-qa.md
```

If the target page requires a signed-in user, attach an automatic-login Session Profile and an
optional page to open after login:

```yaml
- name: Verify an authenticated account page
  uses: Vyspec/vyspec-action@v1
  env:
    VSY_TEST_EMAIL: ${{ secrets.VSY_TEST_EMAIL }}
    VSY_TEST_PASSWORD: ${{ secrets.VSY_TEST_PASSWORD }}
  with:
    project-api-key: ${{ secrets.VSY_PROJECT_API_KEY }}
    instructions-file: .vyspec/account-qa.md
    session-profile-id: 423e4567-e89b-42d3-a456-426614174000
    start-path: /account
```

Exactly one of `run-profile-id`, `instructions`, or `instructions-file` is required. Session
Profile and start-path inputs apply only to direct instructions; saved Run Profiles already own
that configuration.

## Inputs

| Input | Required | Description |
| --- | --- | --- |
| `project-api-key` | Yes | Revocable Project API key stored in GitHub Actions secrets. |
| `run-profile-id` | One execution source | Saved Run Profile UUID. |
| `instructions` | One execution source | Direct QA instructions. |
| `instructions-file` | One execution source | Path to plain-text QA instructions. |
| `session-profile-id` | No | Session Profile UUID for a direct authenticated Run. |
| `start-path` | No | Origin-relative start path for a direct Run; defaults to `/`. |
| `run-notes-file` | No | Path to a JSON array of notes attached to the Run. |
| `app-ready-timeout` | No | Seconds to wait for port 3000; defaults to 120. |
| `github-token` | No | Token used for the PR report; defaults to `github.token`. |
| `pull-request-number` | No | Explicit PR number for comment-triggered or manually dispatched workflows. |
| `ci-branch` | No | Explicit source branch when the event does not expose `github.head_ref`. |

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
