"""Real free-model quality test on the fork's two document fixtures.

Run only from a trusted workflow revision on GitHub. Four model calls maximum;
no retries, fixture checkout, or model tools. Publication stays report-only.
"""

import json
import os
from pathlib import Path

import review as r

FREE_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


def expected_result(branch, decision, result):
    if branch == "review-tests/docs-clean":
        return decision == "pass"
    if decision != "human-review" or not result["coverage_complete"]:
        return False
    # The label alone is insufficient: the actual known factual error must be
    # identified. These expectations are never sent to the model.
    for finding in result["findings"]:
        evidence = " ".join(finding[k] for k in ("title", "reason", "evidence")).replace(",", "")
        if (finding["category"] == "factual" and finding["side"] == "new"
                and finding["file"] == "docs/PR_REVIEW_PILOT.md"
                and "3220" in evidence and "724" in evidence):
            return True
    return False


def main():
    if os.environ["GITHUB_REPOSITORY"] != "YuanchenBei/JevAny":
        raise r.ReviewError("Live quality fixtures are restricted to the testing fork")
    provider, model, key = r.model_configuration()
    if provider != "openrouter" or not key or model != FREE_MODEL:
        raise r.ReviewError("Configure OPENROUTER_API_KEY and the fixed free model for this test")
    catalog = r.request_json("https://openrouter.ai/api/v1/models", key)
    matches = [m for m in catalog["data"] if m["id"] == FREE_MODEL]
    if len(matches) != 1:
        raise r.ReviewError("The selected free model is not available in the current catalog")
    model_info = matches[0]
    if any(float(model_info["pricing"].get(k, "-1")) != 0 for k in ("prompt", "completion")):
        raise r.ReviewError("The selected model is not listed at zero input/output token cost")
    if not {"response_format", "structured_outputs", "max_tokens"}.issubset(model_info["supported_parameters"]):
        raise r.ReviewError("The free model does not advertise the required structured-output parameters")
    gh = r.GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])
    branches = ("review-tests/docs-clean", "review-tests/docs-wrong-count")
    pulls = gh.pages("/pulls?state=open")
    fixtures = []
    # Verify both samples and all CI before making any model request.
    for branch in branches:
        matches = [p for p in pulls if p["head"]["ref"] == branch
                   and p["head"]["repo"] and p["head"]["repo"]["full_name"] == gh.repo]
        if len(matches) != 1:
            raise r.ReviewError(f"Expected one open fixture PR for {branch}")
        pr = r.load_pr(gh, matches[0]["number"])
        files = gh.pages(f"/pulls/{pr['number']}/files")
        if pr["draft"] or [f["filename"] for f in files] != ["docs/PR_REVIEW_PILOT.md"]:
            raise r.ReviewError("Live fixtures must be ready and change only docs/PR_REVIEW_PILOT.md")
        checks = r.ci_evidence(gh, pr, files)
        if r.ci_state(checks) != "passed":
            raise r.ReviewError(f"Fixture PR #{pr['number']} needs successful CI for its current head/base")
        context, sources = r.collect_context(gh, pr, files)
        fixtures.append((branch, pr, files, checks, context, sources))

    observations, records = [], []
    attempted_calls = 0
    error = None
    try:
        for branch, pr, files, checks, context, sources in fixtures:
            for repeat in range(1, 3):
                expected = r.snapshot(pr)
                if not r.current(r.load_pr(gh, pr["number"]), expected):
                    raise r.ReviewError("Fixture head/base changed during the live test")
                attempted_calls += 1
                result, metadata = r.review_model(context, sources, key, model, provider)
                decision, reasons = r.decide(files, checks, result)
                accepted = expected_result(branch, decision, result)
                observation = {"snapshot": expected, "repeat": repeat, "decision": decision,
                               "expected_result_observed": accepted, "result": result, "model": metadata}
                observations.append(observation)
                print(f"PR #{pr['number']} repeat {repeat}: {decision}; expected result observed={accepted}")
                if repeat == 2:
                    records.append({"snapshot": expected, "files": files, "ci": checks,
                                    "result": result, "model": metadata,
                                    "sources": {p: {"old_path": s["old_path"]} for p, s in sources.items()},
                                    "merge_base": context["merge_base"], "mode": "report-only",
                                    "fingerprint": r.digest(["live-free-model", expected, metadata["response_id"]]),
                                    "decision": decision, "reasons": reasons, "retryable": False})
    except r.ReviewError as exc:
        error = str(exc)
        raise
    finally:
        Path("live-review-observations.json").write_text(json.dumps({"ai_tested": bool(observations),
            "requested_model": model, "attempted_calls": attempted_calls, "error": error,
            "catalog": {k: model_info[k] for k in ("id", "pricing", "supported_parameters", "context_length")},
            "observations": observations}, indent=2))
    if len(observations) != 4 or not all(o["expected_result_observed"] for o in observations):
        raise r.ReviewError("Live model quality did not meet all fixture expectations; inspect the observations artifact")
    for record in records:
        if not r.current(r.load_pr(gh, record["snapshot"]["number"]), record["snapshot"]):
            raise r.ReviewError("Fixture changed; refusing publication of stale live-test results")
    Path("live-review-result.json").write_text(json.dumps({"repository": gh.repo, "records": records}, indent=2))
    print("All four live reviews matched the fixture expectations; publication remains report-only.")


if __name__ == "__main__":
    try:
        main()
    except r.ReviewError as exc:
        print(f"Live review incomplete: {exc}")
        raise SystemExit(1)
