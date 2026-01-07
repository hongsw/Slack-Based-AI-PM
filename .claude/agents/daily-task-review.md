# Daily Task Review Agent

An agent workflow for reviewing daily task progress and generating status updates.

## Workflow Pattern
`Prompt → MCP(get_latest_news) → Sub-Agent(oracle) → IfElse → AskUserQuestion → MCP(Slack push)`

## Agent Configuration

```yaml
name: daily-task-review
description: Reviews all active tasks and generates daily status reports
trigger: scheduled  # Run daily at configured time
model: claude-sonnet-4-5-20250514
```

## Workflow Steps

### Step 1: Initialize Review Context
**Type:** Prompt

Gather context for the daily review session.

```
You are conducting a daily task review for the PM system.
Current date: {{current_date}}
Slack channel: {{slack_channel}}

Review scope:
- All tasks with status: in_progress, review, blocked
- Tasks updated in the last 24 hours
- Tasks with approaching due dates (within 3 days)
```

### Step 2: Fetch Task Updates
**Type:** MCP Tool

Fetch recent task-related messages and updates from Slack.

```json
{
  "server": "trendradar",
  "tool": "get_latest_news",
  "parameters": {
    "count": 50,
    "source_filter": "slack"
  }
}
```

### Step 3: Analyze Progress
**Type:** Sub-Agent (Oracle)

Delegate to Oracle agent for strategic analysis of task progress.

```yaml
agent: oracle
task: |
  Analyze the following task updates and determine:
  1. Overall project health (healthy/at-risk/critical)
  2. Tasks making good progress
  3. Tasks that are stalled or blocked
  4. Risks that need escalation
  5. Recommended actions for today

  Task updates:
  {{mcp_result}}

  Provide structured analysis with confidence scores.
```

### Step 4: Check for Blockers
**Type:** IfElse

Branch based on whether blocking issues exist.

```json
{
  "condition": "{{oracle_analysis.blocked_count}} > 0",
  "trueBranch": "handle-blockers",
  "falseBranch": "generate-report"
}
```

### Step 5a: Handle Blockers (if any)
**Type:** AskUserQuestion

Prompt user for blocker resolution strategy.

```json
{
  "question": "The following tasks are blocked:\n\n{{oracle_analysis.blocked_tasks}}\n\nHow would you like to proceed?",
  "options": [
    "Escalate to stakeholders",
    "Reassign blocked tasks",
    "Add to risk report",
    "Skip for today"
  ],
  "timeout": 1800
}
```

### Step 5b: Generate Report
**Type:** Skill (Summarize)

Generate the daily report summary.

```yaml
skill: summarize
input: |
  Create a concise daily PM report with:
  - Executive summary (2-3 sentences)
  - Key metrics: completed, in progress, blocked counts
  - Highlights: major achievements
  - Risks: items needing attention
  - Action items for today

  Analysis data:
  {{oracle_analysis}}
```

### Step 6: Push to Slack
**Type:** MCP Tool

Send the daily report to Slack.

```json
{
  "server": "pm-tools",
  "tool": "push_to_slack",
  "parameters": {
    "channel": "{{slack_channel}}",
    "message": {
      "blocks": [
        {
          "type": "header",
          "text": {
            "type": "plain_text",
            "text": "Daily PM Report - {{current_date}}"
          }
        },
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "{{report_summary}}"
          }
        }
      ]
    }
  }
}
```

## Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `current_date` | System | Today's date (YYYY-MM-DD) |
| `slack_channel` | Config | Target Slack channel |
| `mcp_result` | Step 2 | Raw task updates from TrendRadar |
| `oracle_analysis` | Step 3 | Structured analysis from Oracle agent |
| `user_response` | Step 5a | User's blocker handling choice |
| `report_summary` | Step 5b | Final formatted report |

## Error Handling

- **MCP timeout**: Retry 3x with exponential backoff, then use cached data
- **Oracle failure**: Fall back to basic status aggregation
- **Slack push failure**: Queue message for retry, log for manual review

## Scheduling

```yaml
schedule:
  cron: "0 9 * * 1-5"  # 9 AM weekdays
  timezone: "America/Los_Angeles"
```
