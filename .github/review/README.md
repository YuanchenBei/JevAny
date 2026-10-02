# PR review pilot

The pilot runs entirely on GitHub-hosted Ubuntu runners in `YuanchenBei/JevAny`.
It does not change the upstream repository or require local/GPU execution.
The workflow is deliberately restricted to this fork during validation.

## Results

- **Pass**: applicable CI jobs passed; every changed file was covered; no
  substantive findings or unresolved uncertainties; ordinary documentation only.
  In `auto-approve` mode the bot submits `APPROVE`.
- **Human Review**: substantive issues, code/configuration changes, failed or
  incomplete CI, or an unavailable/incomplete model review. The bot submits
  `COMMENT`, with evidence in one maintained summary.
- Running CI and draft PRs are temporary waiting states, never approvals.

There is no request-changes, close, merge, code-edit, or branch-protection action.
CI failures remain failures. Style preferences and lack of GPU tests do not
escalate an otherwise clean documentation PR. `ai:approved` and `ai:human-review`
are informational labels, not merge requirements.

## GitHub configuration

1. Enable Actions in the fork. To exercise actual approval, enable **Settings →
   Actions → General → Allow GitHub Actions to create and approve pull requests**.
   Workflow jobs request their own minimal permissions; global write access is
   unnecessary.
2. Add an Actions secret `OPENAI_API_KEY` in the fork. Never commit the key.
3. Add an Actions variable `PR_REVIEW_MODEL` with an accessible OpenAI model
   supporting Responses API Structured Outputs. There is deliberately no hidden
   model default. The request has no shell/tools and uses `store: false`.
4. `PR_REVIEW_MODE` defaults to `report-only`. Set the variable to `auto-approve`
   after inspecting the rule tests and pilot reviews. Then manually run **PR
   review** on `main` to reevaluate open PRs with the new configuration.

Missing key/model produces Human Review and explicitly states that AI review has
not completed. API usage is billed to the configured API project; no key is
needed for **Review workflow tests**.

## Evidence and trust boundaries

The controller checks out the exact trusted workflow commit. PR code, dependency
files, prompts, and workflow changes are never executed by a job with the model
key or review write permission. PR content is fetched through the GitHub API as
data. The evaluation job is read-only; a separate job publishes only its same-run
artifact. Neither job restores PR-controlled caches or artifacts from CI.
PR metadata events pass through a no-checkout, no-secret, no-permission signal
workflow. `workflow_run` executes the controller on the default branch. The
controller ignores the signal's contents and fetches GitHub state itself. No
`pull_request_target` exception or event-policy opt-out is needed. Standard
first-time fork contributor approvals for Actions still apply.

CI is collected from `pull_request` runs for the same PR, head and base, with all
expected jobs required to execute successfully. Main's green checks and skipped
jobs are not evidence. Pages is required only for its configured path patterns.
The rule tests detect drift between policy and the current CI/Pages definitions.
CPU CI is not evidence of GPU correctness or production-model performance.

Full old/new changed text and pinned base reference documents are supplied to the
model. Binary, missing, truncated, symlink/submodule, or oversized content routes
to Human Review. Defaults cap one review at 80 changed files, 60 KB per file,
240 KB source context, and 8,000 output tokens. Larger PRs need human review;
there is no silent truncation followed by approval. The first pilot does not
browse external URLs or execute code to substantiate claims.

The publisher rereads PR/CI state, pins each review to `commit_id`, and dismisses
only its own marked approvals when they become invalid. It also checks after
approval for a concurrent head/base change. GitHub's review API cannot atomically
compare-and-swap both head and base: this minimizes that race, not a merge lock.
No new merge restriction is installed. One repository-level concurrency group
serializes runs; each run scans open PRs so coalesced queued events lose no PRs.
Fingerprints deduplicate completed unchanged reviews. API/model failures remain
retryable. Run the workflow manually to retry a configuration or service failure.

## Validation

**Review workflow tests** runs policy, CI matching, schema/coverage, stale result,
publication/deduplication, and workflow-boundary tests on GitHub without a model.
These fixtures verify the program's decisions, not AI bug-detection quality.

After the `review-tests/docs-clean` PR passes its real CI, **Review publisher
integration** runs automatically once for that head/base, as a sequential step
after the controller publishes its results. It can also be run manually on
`main`. Sharing a concurrency group between two independently triggered
workflows could discard a pending integration run, so automatic integration is
part of the controller itself. This fork-only test uses a visibly marked
synthetic result to exercise actual GitHub approval, deduplication, COMMENT and
approval dismissal APIs. It always attempts to withdraw its temporary approval.
It has no model key, does not establish AI quality, and uploads its observations
as an artifact. The regular controller remains in report-only mode throughout.

Integration acceptance requires separate real PRs targeting this fork's `main`:

| Sample | Expected result |
| --- | --- |
| Clean docs spelling/translation | Pass; actual approval only in auto-approve mode |
| Documented metric changed to contradict a pinned source | Human Review, with the actual factual issue |
| Intentional legacy `letter` compatibility alias | No invented naming defect |
| Core-code change | Human Review regardless of clean CI |
| Failed CI | Human Review; CI stays red |
| CI still running | Wait; no approval |
| New head/base during review | Discard old result; withdraw obsolete bot approval |
| Repeated callbacks/reruns | Update one summary; no repeated identical review |
| Missing key/API failure/invalid output | Human Review; no claim of AI completion |

Also exercise draft-to-ready and a PR from another fork. Model-quality acceptance
must inspect the actual findings on known-bug and repaired samples, not merely
the Human Review label. Repeat clean/bug samples to assess model variability.
Passing deterministic tests cannot guarantee that AI finds every real bug.

After pilot acceptance, submit the portable controller as an upstream PR, update
the repository allowlist, and separately configure upstream secrets/permissions.
Start upstream in report-only mode before considering automatic approvals.

References: [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows),
[secure Actions use](https://docs.github.com/en/actions/reference/security/secure-use),
[reviews API](https://docs.github.com/en/rest/pulls/reviews),
[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
