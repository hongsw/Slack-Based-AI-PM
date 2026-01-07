# SHARED_TASK_NOTES.md

## Current State
- spec.md: 13 sections with detailed specs + PM Tools MCP reference (section 6.3)
- `.claude/agents/`: 2 workflow templates updated to use `pm-tools` server
- `.claude/commands/`: Directory created, awaiting slash command definitions
- `docker-compose.yml`: Full stack with TrendRadar, PM Tools MCP, SQLite viewer, Ofelia scheduler
- `.env.example`: Complete environment template
- `mcp-tools/`: New PM MCP tools module (pm_tools.py, Dockerfile, requirements.txt)

## What Was Done This Iteration
- Created `mcp-tools/pm_tools.py` with 6 PM-specific MCP tools:
  - `create_task`, `update_task_status`, `get_task_progress`, `get_task_by_id`, `generate_boss_report`, `push_to_slack`
- Added Dockerfile and requirements.txt for containerization
- Updated docker-compose.yml to include pm-tools service on port 3334
- Updated spec.md section 6 with PM Tools MCP reference
- Fixed workflow templates to reference `pm-tools` server instead of `trendradar`

## Next Steps (Priority Order)

1. **Add slash commands** - Populate `.claude/commands/` with:
   - `/pm verify <task_id>` - Manual task verification trigger
   - `/pm status` - Quick status check
   - `/pm report` - Generate on-demand report

2. **Add GitHub Actions workflow** - For scheduled PM report generation (alternative to Ofelia)

3. **Create scheduler config** - Add `scheduler/config.ini` for Ofelia if using Docker scheduler

4. **Test integration** - Run `docker compose up` and verify:
   - pm-tools health endpoint responds at :3334/health
   - Database initializes correctly at data/pm/tasks.db
   - Slack webhook integration works with push_to_slack

## Open Questions
- How to handle Slack thread context for multi-message task discussions?
- What's the authentication flow for oh-my-opencode model subscriptions?
- Should workflows call pm-tools directly or go through TrendRadar as proxy?

## Notes
- pm_tools.py can run standalone (`python pm_tools.py --port 3334`) or as Docker container
- Database schema matches spec.md section 8.2
- MCP_TOOLS_SCHEMA in pm_tools.py provides OpenAPI-style schema for tool discovery
- Workflows now reference `server: "pm-tools"` for task operations and Slack pushes
