"""Exercise real GitHub review APIs on a dedicated, human-authored test PR.

This is a publisher integration test using a clearly marked synthetic model
result. It does NOT test AI reasoning and always withdraws its test approval.
"""

import json
import os
from pathlib import Path

import review as r


def main():
    if os.environ["GITHUB_REPOSITORY"] != "YuanchenBei/JevAny":
        raise r.ReviewError("Integration fixture is restricted to the testing fork")
    gh = r.GitHub(os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"])

    def skip(reason):
        Path("integration-result.json").write_text(json.dumps({"status": "not-run", "reason": reason, "ai_tested": False}))
        print(reason)

    candidates = [p for p in gh.pages("/pulls?state=open")
                  if p["head"]["ref"] == "review-tests/docs-clean"
                  and p["head"]["repo"]["full_name"] == gh.repo]
    if len(candidates) != 1:
        return skip("Waiting for the dedicated review-tests/docs-clean fixture PR")
    pr = gh.repo_call(f"/pulls/{candidates[0]['number']}")
    number = pr["number"]
    files = gh.pages(f"/pulls/{number}/files")
    if [f["filename"] for f in files] != ["docs/PR_REVIEW_PILOT.md"] or pr["draft"]:
        raise r.ReviewError("Integration PR must only change docs/PR_REVIEW_PILOT.md and be ready")
    checks = r.ci_evidence(gh, pr, files)
    if r.ci_state(checks) != "passed":
        return skip("Waiting for the fixture PR's actual CI to pass at the current head/base")
    integration_key = r.digest(["api-integration", r.snapshot(pr)])
    completed_key = r.digest([integration_key, "withdraw"])
    reviews = gh.pages(f"/pulls/{number}/reviews")
    if any(r.own(v) and f"<!-- review:{completed_key}:COMMENT -->" in v["body"] for v in reviews):
        return skip("Publisher integration already completed for this fixture head/base")
    context, sources = r.collect_context(gh, pr, files)
    result = {"summary": "SYNTHETIC INTEGRATION FIXTURE: no AI call was made. This tests only GitHub publication and approval withdrawal.",
              "coverage_complete": True, "uncertainties": [], "findings": []}
    r.validate_result(result, sources)
    record = {"snapshot": r.snapshot(pr), "files": files, "ci": checks, "result": result,
              "sources": {path: {"old_path": source["old_path"]} for path, source in sources.items()},
              "merge_base": context["merge_base"], "model": {"model": "synthetic-integration-fixture-NOT-AI"},
              "fingerprint": integration_key,
              "mode": "auto-approve", "decision": "pass", "retryable": True,
              "reasons": ["Synthetic publisher test; any approval is temporary and is withdrawn before this test finishes."]}
    outcomes = []
    try:
        assert r.publish_one(gh, record, "auto-approve") == "pass"
        reviews = gh.pages(f"/pulls/{number}/reviews")
        approved = [v for v in reviews if r.own(v) and v["state"] == "APPROVED"
                    and v["commit_id"] == pr["head"]["sha"]]
        assert len(approved) == 1, "Expected one real GitHub approval on the exact head"
        outcomes.append("Real APPROVE accepted and pinned to the tested head")
        assert r.publish_one(gh, record, "auto-approve") == "pass"
        assert len(gh.pages(f"/pulls/{number}/reviews")) == len(reviews), "Duplicate approval was posted"
        outcomes.append("Repeated publication did not duplicate the review")
        record.update(decision="human-review", fingerprint=r.digest([record["fingerprint"], "withdraw"]),
                      reasons=["Synthetic integration completed: the test approval has been withdrawn. Real AI quality testing is separate."])
        assert r.publish_one(gh, record, "auto-approve") == "human-review"
        reviews = gh.pages(f"/pulls/{number}/reviews")
        assert not any(r.own(v) and v["state"] == "APPROVED" for v in reviews)
        assert reviews[-1]["state"] == "COMMENTED", "Human Review must be a COMMENT"
        outcomes.append("Human Review posted COMMENT and dismissed the prior test approval")
        comments = [c for c in gh.pages(f"/issues/{number}/comments") if r.own(c)]
        assert len(comments) == 1, "Expected one maintained summary"
        outcomes.append("Only one maintained PR summary exists")
    finally:
        # Even an assertion/API failure must not intentionally leave a fixture approval.
        r.withdraw_approvals(gh, number)
        Path("integration-result.json").write_text(json.dumps({"pr": number, "head": pr["head"]["sha"],
                                                               "outcomes": outcomes, "ai_tested": False}, indent=2))
    print("\n".join(outcomes))


if __name__ == "__main__":
    main()
