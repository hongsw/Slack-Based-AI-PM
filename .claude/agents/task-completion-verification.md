# Task Completion Verification Agent

An agent workflow for verifying task completion through multi-signal analysis.

## Workflow Pattern
`Prompt → MCP(analyze_sentiment) → IfElse → Sub-Agent(librarian) → Skill(summarize) → MCP(Slack push)`

## Agent Configuration

```yaml
name: task-completion-verification
description: Verifies task completion using sentiment analysis and documentation review
trigger: event  # Triggered when task status changes to 'review'
model: claude-sonnet-4-5-20250514
```

## Workflow Steps

### Step 1: Initialize Verification Context
**Type:** Prompt

Set up the verification context for the task under review.

```
You are verifying completion of a PM task.

Task Details:
- ID: {{task_id}}
- Title: {{task_title}}
- Description: {{task_description}}
- Assignee: {{assignee}}
- Due Date: {{due_date}}

Recent Updates:
{{progress_updates}}

Verification criteria:
1. All acceptance criteria met
2. Positive sentiment in completion messages
3. Documentation updated (if applicable)
4. No open blockers or dependencies
```

### Step 2: Analyze Completion Sentiment
**Type:** MCP Tool

Use TrendRadar's sentiment analysis on completion-related messages.

```json
{
  "server": "trendradar",
  "tool": "analyze_sentiment",
  "parameters": {
    "text": "{{latest_update_content}}",
    "context": "task_completion"
  }
}
```

### Step 3: Check Sentiment Threshold
**Type:** IfElse

Branch based on sentiment analysis results.

```json
{
  "condition": "{{sentiment_score}} > 0.5",
  "trueBranch": "verify-documentation",
  "falseBranch": "request-clarification"
}
```

### Step 4a: Request Clarification (negative sentiment)
**Type:** AskUserQuestion

If sentiment indicates uncertainty, ask for clarification.

```json
{
  "question": "Task '{{task_title}}' has uncertain completion status (sentiment: {{sentiment_score}}).\n\nRecent update: {{latest_update_content}}\n\nIs this task actually complete?",
  "options": [
    "Yes, mark as completed",
    "No, needs more work",
    "Needs manager review"
  ],
  "timeout": 3600
}
```

### Step 4b: Verify Documentation
**Type:** Sub-Agent (Librarian)

Delegate to Librarian agent to check documentation completeness.

```yaml
agent: librarian
task: |
  Verify that task completion includes proper documentation:

  Task: {{task_title}}
  Description: {{task_description}}

  Check for:
  1. Updated README or docs if applicable
  2. Code comments for complex logic
  3. Test coverage for new functionality
  4. Changelog entry if required

  Search the codebase for evidence of completion.

  Return:
  - documentation_complete: boolean
  - missing_items: string[]
  - evidence: string[]
```

### Step 5: Generate Verification Summary
**Type:** Skill (Summarize)

Create a verification summary combining all signals.

```yaml
skill: summarize
input: |
  Generate a task verification report:

  Task: {{task_title}} ({{task_id}})

  Verification Signals:
  - Sentiment Score: {{sentiment_score}} (threshold: 0.5)
  - Documentation Check: {{librarian_result.documentation_complete}}
  - Missing Items: {{librarian_result.missing_items}}

  Evidence:
  {{librarian_result.evidence}}

  Determine final verification status:
  - VERIFIED: All criteria met
  - NEEDS_WORK: Missing documentation or low sentiment
  - MANUAL_REVIEW: Conflicting signals
```

### Step 6: Update Task Status
**Type:** MCP Tool (Custom PM Tool)

Update the task record with verification results.

```json
{
  "server": "trendradar",
  "tool": "update_task_status",
  "parameters": {
    "task_id": "{{task_id}}",
    "status": "{{verification_status}}",
    "verification": {
      "verified_by": "agent",
      "verified_at": "{{current_timestamp}}",
      "method": "automated",
      "evidence": "{{verification_evidence}}"
    }
  }
}
```

### Step 7: Push Verification Result to Slack
**Type:** MCP Tool

Notify the team of verification results.

```json
{
  "server": "trendradar",
  "tool": "push_to_slack",
  "parameters": {
    "channel": "{{slack_channel}}",
    "thread_ts": "{{slack_thread_ts}}",
    "message": {
      "blocks": [
        {
          "type": "section",
          "text": {
            "type": "mrkdwn",
            "text": "{{verification_emoji}} *Task Verification: {{task_title}}*\n\n*Status:* {{verification_status}}\n*Confidence:* {{confidence_score}}%\n\n{{verification_summary}}"
          }
        },
        {
          "type": "context",
          "elements": [
            {
              "type": "mrkdwn",
              "text": "Verified by AI Agent | {{current_timestamp}}"
            }
          ]
        }
      ]
    }
  }
}
```

## Variables

| Variable | Source | Description |
|----------|--------|-------------|
| `task_id` | Trigger | Unique task identifier |
| `task_title` | Task Record | Task title |
| `task_description` | Task Record | Task description |
| `assignee` | Task Record | Assigned team member |
| `progress_updates` | Task Record | Array of progress update content |
| `latest_update_content` | Task Record | Most recent update text |
| `sentiment_score` | Step 2 | Sentiment analysis result (-1 to 1) |
| `librarian_result` | Step 4b | Documentation verification results |
| `verification_status` | Step 5 | Final status (VERIFIED/NEEDS_WORK/MANUAL_REVIEW) |
| `verification_emoji` | Computed | Status emoji (check/warning/question) |
| `slack_thread_ts` | Task Record | Original Slack thread for reply |

## Verification Status Mapping

| Status | Emoji | Conditions |
|--------|-------|------------|
| VERIFIED | :white_check_mark: | sentiment > 0.5 AND documentation_complete |
| NEEDS_WORK | :warning: | sentiment <= 0.5 OR missing_items.length > 0 |
| MANUAL_REVIEW | :question: | Conflicting signals or user requested |

## Error Handling

- **Sentiment analysis failure**: Default to neutral (0.0), flag for manual review
- **Librarian timeout**: Skip documentation check, note in verification record
- **Slack push failure**: Queue notification, continue with task update

## Trigger Configuration

```yaml
triggers:
  - type: task_status_change
    from: ["in_progress", "blocked"]
    to: "review"
  - type: manual
    command: "/pm verify {{task_id}}"
  - type: scheduled
    cron: "0 17 * * 1-5"  # EOD verification sweep
```
