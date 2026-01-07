# SHARED_TASK_NOTES.md

## Current State
- spec.md: 13 sections with detailed specifications
- `.claude/agents/`: 2 workflow templates (daily-task-review, task-completion-verification)
- `.claude/commands/`: Directory created, awaiting slash command definitions
- `docker-compose.yml`: Full stack with TrendRadar MCP, SQLite viewer (dev), and Ofelia scheduler
- `.env.example`: Complete environment template

## Next Steps (Priority Order)

1. **Build custom PM MCP tools** - TrendRadar's tools are news-focused. Need PM-specific tools:
   - `create_task` - Create a new PM task
   - `update_task_status` - Update task status (referenced in task-completion-verification)
   - `get_task_progress` - Get task progress updates
   - `generate_boss_report` - Generate formatted report
   - `push_to_slack` - Send formatted Slack messages (wrapper for webhook)

   **Implementation approach**: Create a Python module `pm_tools.py` that extends TrendRadar's MCP server with PM-specific tools. This could be mounted as a volume or submitted as a PR to TrendRadar.

2. **Add slash commands** - Populate `.claude/commands/` with:
   - `/pm verify <task_id>` - Manual task verification trigger
   - `/pm status` - Quick status check
   - `/pm report` - Generate on-demand report

3. **Add GitHub Actions workflow** - For scheduled PM report generation (alternative to Ofelia scheduler in docker-compose)

4. **Create scheduler config** - Add `scheduler/config.ini` for Ofelia if using Docker scheduler

## Open Questions
- Should PM tools be a TrendRadar PR or a separate MCP server container?
- How to handle Slack thread context for multi-message task discussions?
- What's the authentication flow for oh-my-opencode model subscriptions?

## Notes
- Workflow files use markdown format with embedded YAML/JSON for node configs
- cc-wf-studio exports to `.claude/agents/` and `.claude/commands/`
- oh-my-opencode uses `ultrawork` magic word to enable all features
- Workflows reference custom MCP tools (`update_task_status`, `push_to_slack`) that don't exist yet in TrendRadar
- docker-compose uses Ofelia for cron scheduling inside containers
- SQLite viewer available in dev profile: `docker compose --profile dev up`
