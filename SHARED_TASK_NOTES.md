# SHARED_TASK_NOTES.md

## Current State
spec.md has been expanded from 7 sections to 13 sections with detailed specifications for:
- MCP integration (tools reference, configuration)
- Workflow node definitions (JSON schemas)
- Data model & storage (TypeScript interfaces, SQLite schema)
- Error handling & recovery patterns
- oh-my-opencode agent integration details
- Slack message formats and webhook config

## Next Steps (Priority Order)

1. **Create example workflow files** - Build actual `.claude` workflow files for the PM templates described in spec.md (Daily Task Review, Task Completion Verification)

2. **Add docker-compose.yml** - Create a complete Docker Compose file that spins up the full stack (TrendRadar + MCP server)

3. **Create environment template** - Add `.env.example` with all required environment variables

4. **Build custom MCP tools** - The spec describes PM-specific use cases, but TrendRadar's tools are news-focused. May need custom PM tools:
   - `create_task` - Create a new PM task
   - `update_task_status` - Update task status
   - `get_task_progress` - Get task progress updates
   - `generate_boss_report` - Generate formatted report

5. **Add GitHub Actions workflow** - For scheduled PM report generation

## Open Questions
- Should tasks be stored in TrendRadar's SQLite or a separate PM-specific database?
- How to handle Slack thread context for multi-message task discussions?
- What's the authentication flow for oh-my-opencode model subscriptions?

## Notes
- TrendRadar tools are news/trend focused - the spec adapts them for PM but custom tools would be cleaner
- oh-my-opencode uses `ultrawork` magic word to enable all features
- cc-wf-studio exports to `.claude/agents/` and `.claude/commands/`
