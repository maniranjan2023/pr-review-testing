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
    parser.add_argument(
        "--focus",
        choices=FOCUS_CHOICES,
        default="all",
        help="What the reviewer should emphasize",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also write review metadata to a .json file next to the markdown output",
    )
    return parser.parse_args()


def save_review(
    output_path: str,
    repo: str,
    pr_number: int | None,
    content: str,
    *,
    dry_run: bool,
    focus: str,
) -> Path:
    path = Path(output_path)
    link = pr_url(repo, pr_number)
    header = (
        f"# PR Review\n\n"
        f"- **Repo**: `{repo}`\n"
        f"- **PR**: `{pr_number or 'latest open'}`\n"
    )
    if link:
        header += f"- **Link**: {link}\n"
    header += (
        f"- **Mode**: {'dry-run' if dry_run else 'live'}\n"
        f"- **Focus**: {focus}\n"
        f"- **Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"---\n\n"
    )
    path.write_text(header + content.strip() + "\n", encoding="utf-8")
    return path


def save_metadata_json(
    output_path: str,
    *,
    repo: str,
    pr_number: int | None,
    dry_run: bool,
    focus: str,
    elapsed_seconds: float,
    review_path: Path,
) -> Path:
    path = Path(output_path).with_suffix(".json")
    payload = {
        "repo": repo,
        "pr_number": pr_number,
        "pr_url": pr_url(repo, pr_number),
        "dry_run": dry_run,
        "focus": focus,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "review_file": str(review_path.resolve()),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def build_agent(tools, *, dry_run: bool = False, focus: str = "all") -> Agent:
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

**Review focus for this run**
{focus_instructions(focus)}

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

### Recommended next steps
[2-4 concrete actions for the author: fix, test, document, or merge]

Be specific and actionable. Don't invent issues to seem thorough.
If the PR looks good, say so.""",
        tools=tools,
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
async def main():
    args = parse_args()