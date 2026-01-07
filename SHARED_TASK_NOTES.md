# SHARED_TASK_NOTES.md

## Current State
- spec.md: 13 sections with detailed specifications
- `.claude/agents/`: 2 workflow templates (daily-task-review, task-completion-verification)
- `.claude/commands/`: Directory created, awaiting slash command definitions
- `docker-compose.yml`: Full stack with TrendRadar MCP, SQLite viewer (dev), and Ofelia scheduler
- `.env.example`: Complete environment template
- `pm_tools/`: **Complete Python module** with MCP tools implementation

### pm_tools Module (COMPLETED)
- `models.py`: Data models matching spec.md Section 8.1 (PMTask, ProgressUpdate, VerificationRecord)
- `database.py`: SQLite operations matching spec.md Section 8.2
- `slack_client.py`: Slack webhook client with retry logic and message formatters
- `tools.py`: MCP tool functions:
  - `create_task` - Create new PM task with Slack notification
  - `update_task_status` - Update status, add progress notes
  - `get_task_progress` - Get task with full history
  - `get_tasks_by_status` - Query tasks by status filter
  - `generate_boss_report` - Generate formatted daily report
  - `push_to_slack` - Send Slack messages with various formats
  - `verify_task_completion` - Mark task as verified with evidence
- `mcp_server.py`: MCP server with stdio (MCP SDK) and HTTP fallback modes

## Next Steps (Priority Order)

1. **Add pm_tools container to docker-compose** - Mount pm_tools as separate MCP server container:
   ```yaml
   pm-tools-mcp:
     build: ./pm_tools
     ports:
       - "3334:3334"
     environment:
       - PM_DATABASE_PATH=/data/tasks.db
       - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
   ```

2. **Create Dockerfile for pm_tools** - Simple Python container with pm_tools module

3. **Add slash commands** - Populate `.claude/commands/` with:
   - `/pm verify <task_id>` - Manual task verification trigger
   - `/pm status` - Quick status check
   - `/pm report` - Generate on-demand report

4. **Add GitHub Actions workflow** - For scheduled PM report generation

5. **Update workflow templates** - Ensure `.claude/agents/` workflows use correct MCP tool names

## Open Questions
- Should pm_tools run as separate container or be mounted into TrendRadar container?
- How to configure MCP endpoints in cc-wf-studio to point to pm_tools server?

## Notes
- pm_tools MCP server runs on port 3334 (TrendRadar is 3333)
- HTTP fallback mode available if MCP SDK not installed
- Database auto-initializes on first use
- All Slack messages use Block Kit format per spec.md Section 11.1
