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
  

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
async def main():
    args = parse_args()