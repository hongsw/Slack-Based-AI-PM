# SHARED_TASK_NOTES.md

## Current State
- spec.md: 13 sections with detailed specifications
- `.claude/agents/`: 2 workflow templates (daily-task-review, task-completion-verification)
- `.claude/commands/`: 4 slash commands defined (pm-verify, pm-status, pm-report, pm-create)
- `src/mcp/pm_tools.py`: PM-specific MCP tools implementation (NEW)
- `docker-compose.yml`: Full stack with TrendRadar MCP, SQLite viewer (dev), and Ofelia scheduler
- `.env.example`: Complete environment template

## PM MCP Tools Created (src/mcp/pm_tools.py)
The following tools are now implemented and ready for integration:

| Tool | Purpose |
|------|---------|
| `create_task` | Create a new PM task |
| `update_task_status` | Update task status with optional verification |
| `get_task_progress` | Get task details and progress updates |
| `add_progress_update` | Add progress update to a task |
| `generate_boss_report` | Generate formatted daily report |
| `push_to_slack` | Send messages via Slack webhook |
| `list_tasks` | List tasks with filters |

## Next Steps (Priority Order)

1. **Integrate pm_tools.py with TrendRadar MCP server**
   - Option A: Mount as volume and add import to TrendRadar's MCP handler
   - Option B: Create standalone MCP server container using FastMCP or similar
   - Option C: Submit PR to TrendRadar with PM tools extension

2. **Add GitHub Actions workflow** - For scheduled PM report generation
   - Create `.github/workflows/pm-report.yml`
   - Schedule daily at 9 AM PT (alternative to Ofelia scheduler)

3. **Create MCP server wrapper** - If going with standalone container:
   - Create `src/mcp/server.py` using FastMCP
   - Update docker-compose to add pm-mcp service
   - Configure port 3334 for PM-specific MCP

4. **Test end-to-end workflow** - Validate full pipeline:
   - Create task via `/pm create`
   - Check status via `/pm status`
   - Trigger verification via `/pm verify`
   - Generate report via `/pm report`

## Open Questions
- **MCP Integration Approach**: Standalone container vs TrendRadar extension?
  - Standalone: More flexibility, cleaner separation
  - Extension: Simpler setup, single MCP endpoint
- How to handle Slack thread context for multi-message task discussions?
- What's the authentication flow for oh-my-opencode model subscriptions?

## Notes
- Workflow files use markdown format with embedded YAML/JSON for node configs
- pm_tools.py uses SQLite (same schema as spec.md Section 8)
- CLI test available: `python src/mcp/pm_tools.py --test`
- Tool schemas available: `python src/mcp/pm_tools.py --list-tools`
