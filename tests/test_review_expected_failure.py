"""Deliberate CI failure used only on the PR review test branch; do not merge."""

raise RuntimeError("Intentional PR-review fixture: verify failed CI routes to Human Review")
