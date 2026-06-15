"""
Standalone AI PR Reviewer
=========================

What it does:
  - Reads a target repo from .env
  - Finds the latest open PR in that repo (or a specific one if you set PR_NUMBER)
  - Reviews the diff with an AI agent
  - Posts the review as a comment on the PR

How to test:
  1. pip install composio composio-openai-agents openai-agents python-dotenv
  2. Copy this file + a .env into any folder (see .env keys at the bottom).
  3. Raise a PR to your target repo from your local clone.
  4. Run:  python pr_review.py
     Optional flags:
       --repo owner/name   override GITHUB_REPO
       --pr 42             review a specific PR
       --dry-run           review without posting to GitHub
       --output file.md    save review locally (default: review_output.md)
  5. Check the PR -> the review should appear as a comment (unless --dry-run).
"""

import argparse
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, Runner
from composio import Composio
from composio_openai_agents import OpenAIAgentsProvider


# ---------------------------------------------------------------------------
# Config (from .env)
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT_FILE = os.environ.get("REVIEW_OUTPUT_FILE", "review_output.md")


def parse_args():
    parser = argparse.ArgumentParser(description="Run an AI review on a GitHub pull request.")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPO"),
        help="GitHub repo as owner/name (overrides GITHUB_REPO in .env)",
    )
    parser.add_argument(
        "--pr",
        type=int,
        default=int(os.environ["PR_NUMBER"]) if os.environ.get("PR_NUMBER") else None,
        help="PR number to review (overrides PR_NUMBER in .env)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help="Local file to save the review text",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the review but do not post a comment on GitHub",
    )
    return parser.parse_args()


def save_review(output_path: str, repo: str, pr_number: int | None, content: str) -> Path:
    path = Path(output_path)
    header = (
        f"# PR Review\n\n"
        f"- **Repo**: `{repo}`\n"
        f"- **PR**: `{pr_number or 'latest open'}`\n"
        f"- **Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"---\n\n"
    )
    path.write_text(header + content.strip() + "\n", encoding="utf-8")
    return path

def build_agent(tools, *, dry_run: bool = False) -> Agent:
    post_step = (
        "Return the full review text only. Do NOT post anything to GitHub."
        if dry_run
        else """You MUST post the review by calling the GitHub "create issue comment" tool
on the pull request (a PR is an issue for the comments API). Do not just
return the text. After posting, confirm you posted it."""
    )

    return Agent(
        name="PR Reviewer",
        instructions=f"""You are PR-Reviewer, an AI code reviewer for GitHub pull requests.

**Step 1: Gather context**
- Fetch the PR details (title, description, author).
- List all changed files and read the diff.
- Check if the repo has a CLAUDE.md or AGENTS.md at the root.
  If found, read it and treat its rules as your review checklist.

**Step 2: Analyze the diff**
Focus only on new code added in the PR. For each changed file, look for:
- Bugs and logic errors
- Security issues (exposed secrets, injection, XSS)
- Performance problems (unnecessary loops, N+1 queries)
- Violations of CLAUDE.md / AGENTS.md rules (if the file exists)
- Whether tests were added or updated

Do NOT flag:
- Style preferences or minor wording changes
- Issues in unchanged code that existed before the PR
- Missing docstrings, type hints, or comments
- Things that would be caught by a linter or CI

For each file, ask: "Would this change break something or mislead someone?"
If no, move on.

**Step 3: Deliver your review**
{post_step}
Use this format:

## PR Review

**Summary**: [2-3 sentences on what this PR does]

**Review effort [1-5]**: [1 = trivial, 5 = complex and risky]

### Key issues
| # | File | Lines | Category | Description |
|---|------|-------|----------|-------------|
| 1 | `file.py` | 12-15 | Possible bug | [description] |

Categories: `possible bug`, `security`, `performance`, `best practice`

If no issues found, write "No issues found" instead of the table.

### Security concerns
[Any security issues, or "None"]

### CLAUDE.md / AGENTS.md compliance
[Rule violations, or "No project rules file found" / "All rules followed"]

### Tests
[Were relevant tests added? Yes/No with brief explanation]

Be specific and actionable. Don't invent issues to seem thorough.
If the PR looks good, say so.""",
        tools=tools,
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
async def main():
    args = parse_args()

    if not args.repo:
        raise SystemExit("Set GITHUB_REPO in your .env or pass --repo owner/name")

    user_id = os.environ.get("COMPOSIO_USER_ID", "user_123")
    owner, _, name = args.repo.partition("/")

    composio = Composio(provider=OpenAIAgentsProvider())
    session = composio.create(user_id=user_id, toolkits=["github"])
    agent = build_agent(session.tools(), dry_run=args.dry_run)

    mode = "dry-run (no GitHub comment)" if args.dry_run else "live (post comment)"
    print(f"[pr-review] repo={args.repo} pr={args.pr or 'latest open'} mode={mode}")

    if args.pr:
        task = (
            f"Review pull request #{args.pr} in the {args.repo} repository, "
            f"then {'return' if args.dry_run else 'post'} your review "
            f"{'as text only' if args.dry_run else 'as a comment on that pull request'}."
        )
    else:
        task = (
            f"Find the most recently opened OPEN pull request in the {args.repo} "
            f"repository (owner='{owner}', repo='{name}'). Review it, then "
            f"{'return' if args.dry_run else 'post'} your review "
            f"{'as text only' if args.dry_run else 'as a comment on that pull request'}. "
            f"Tell me which PR number you reviewed."
        )

    started = datetime.now(timezone.utc)
    result = await Runner.run(starting_agent=agent, input=task)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    output = result.final_output or ""
    print(output)

    saved_to = save_review(args.output, args.repo, args.pr, output)
    print(f"\n[pr-review] Saved review to {saved_to.resolve()}")
    print(f"[pr-review] Finished in {elapsed:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
