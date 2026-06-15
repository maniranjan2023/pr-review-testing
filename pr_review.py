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
  5. Check the PR -> the review should appear as a comment.
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, Runner
from composio_openai_agents import OpenAIAgentsProvider

from composio import Composio

# ---------------------------------------------------------------------------
# Config (from .env)
# ---------------------------------------------------------------------------
GITHUB_REPO = os.environ.get("GITHUB_REPO")  # e.g. "your-username/test-repo"
PR_NUMBER = os.environ.get("PR_NUMBER")      # optional; blank = latest open PR
USER_ID = os.environ.get("COMPOSIO_USER_ID", "user_123")

if not GITHUB_REPO:
    raise SystemExit("Set GITHUB_REPO in your .env, e.g. GITHUB_REPO=your-username/test-repo")

# ---------------------------------------------------------------------------
# Composio + tools
# ---------------------------------------------------------------------------
composio = Composio(provider=OpenAIAgentsProvider())

session = composio.create(
    user_id=USER_ID,
    toolkits=["github"],
)
tools = session.tools()

# ---------------------------------------------------------------------------
# Reviewer agent
# ---------------------------------------------------------------------------
agent = Agent(
    name="PR Reviewer",
    instructions="""You are PR-Reviewer, an AI code reviewer for GitHub pull requests.

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

**Step 3: Post your review as a PR comment**
You MUST post the review by calling the GitHub "create issue comment" tool
on the pull request (a PR is an issue for the comments API). Do not just
return the text. After posting, confirm you posted it.
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
    owner, _, name = GITHUB_REPO.partition("/")

    if PR_NUMBER:
        task = (
            f"Review pull request #{PR_NUMBER} in the {GITHUB_REPO} repository, "
            f"then post your review as a comment on that pull request."
        )
    else:
        task = (
            f"Find the most recently opened OPEN pull request in the {GITHUB_REPO} "
            f"repository (owner='{owner}', repo='{name}'). Review it, then post your "
            f"review as a comment on that pull request. Tell me which PR number you reviewed."
        )

    result = await Runner.run(starting_agent=agent, input=task)
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
