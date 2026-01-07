# /pm verify

Manual task verification trigger for the PM system.

## Usage

```
/pm verify <task_id>
```

## Description

Triggers the task-completion-verification workflow for a specific task. This command:

1. Fetches the task and its progress updates
2. Runs sentiment analysis on completion messages
3. Checks documentation completeness via Librarian agent
4. Updates task status based on verification results
5. Posts verification result to Slack

## Arguments

- `task_id` (required): The task identifier to verify

## Workflow Reference

This command triggers the `task-completion-verification` agent workflow defined in `.claude/agents/task-completion-verification.md`.

## MCP Tools Used

- `get_task_progress` - Fetch task details and updates
- `analyze_sentiment` - Analyze completion sentiment
- `update_task_status` - Update with verification record
- `push_to_slack` - Post verification result

## Example

```
/pm verify abc123
```

Verifies task `abc123` and posts result:
```
:white_check_mark: *Task Verification: Implement login feature*

*Status:* VERIFIED
*Confidence:* 92%

All acceptance criteria met. Documentation updated.
```

## Implementation

```yaml
name: pm-verify
description: Manual task verification
arguments:
  - name: task_id
    required: true
    description: Task ID to verify
workflow: task-completion-verification
variables:
  task_id: "{{args.task_id}}"
```
