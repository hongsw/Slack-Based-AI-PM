# SHARED_TASK_NOTES.md

## Current State
- spec.md: 13 sections with detailed specifications
- `.claude/agents/`: Contains 2 workflow templates
  - `daily-task-review.md` - Daily status report generation workflow
  - `task-completion-verification.md` - Task verification workflow with sentiment analysis
- `.claude/commands/`: Directory created, awaiting slash command definitions

## Next Steps (Priority Order)

1. **Add docker-compose.yml** - Create complete Docker Compose for full stack (TrendRadar + MCP)

2. **Create .env.example** - Environment template with all required variables

3. **Build custom PM MCP tools** - TrendRadar's tools are news-focused. Need PM-specific tools:
   - `create_task` - Create a new PM task
   - `update_task_status` - Update task status (referenced in task-completion-verification)
   - `get_task_progress` - Get task progress updates
   - `generate_boss_report` - Generate formatted report
   - `push_to_slack` - Send formatted Slack messages (wrapper for webhook)

4. **Add slash commands** - Populate `.claude/commands/` with:
   - `/pm verify <task_id>` - Manual task verification trigger
   - `/pm status` - Quick status check
   - `/pm report` - Generate on-demand report

5. **Add GitHub Actions workflow** - For scheduled PM report generation

## Open Questions
- Should tasks be stored in TrendRadar's SQLite or a separate PM-specific database?
- How to handle Slack thread context for multi-message task discussions?
- What's the authentication flow for oh-my-opencode model subscriptions?

## Notes
- Workflow files use markdown format with embedded YAML/JSON for node configs
- cc-wf-studio exports to `.claude/agents/` and `.claude/commands/`
- oh-my-opencode uses `ultrawork` magic word to enable all features
- Workflows reference custom MCP tools (`update_task_status`, `push_to_slack`) that don't exist yet in TrendRadar
