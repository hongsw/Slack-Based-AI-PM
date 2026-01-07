# /pm status

Quick status check for the PM system.

## Usage

```
/pm status [task_id]
```

## Description

Get a quick status overview. Without arguments, shows system-wide task counts. With a task ID, shows detailed status for that specific task.

## Arguments

- `task_id` (optional): Specific task to check

## Modes

### System Status (no arguments)

Shows:
- Total task counts by status
- Blocked tasks requiring attention
- Tasks due within 3 days
- Recent activity summary

### Task Status (with task_id)

Shows:
- Task details (title, assignee, priority, due date)
- Current status
- Recent progress updates
- Verification status if applicable

## MCP Tools Used

- `list_tasks` - Get task counts and lists
- `get_task_progress` - Get specific task details

## Examples

### System status
```
/pm status
```

Output:
```
PM System Status

Completed: 12
In Progress: 5
Blocked: 2
Review: 1

:warning: Blocked Tasks:
- Implement OAuth (blocked on API keys)
- Database migration (waiting for review)

:alarm_clock: Due Soon:
- API documentation (due tomorrow)
```

### Task status
```
/pm status abc123
```

Output:
```
Task: Implement login feature (abc123)

Status: in_progress
Assignee: @alice
Priority: high
Due: 2026-01-10

Recent Updates:
- [Jan 7] Started frontend implementation
- [Jan 6] Backend API complete
```

## Implementation

```yaml
name: pm-status
description: Quick status check
arguments:
  - name: task_id
    required: false
    description: Optional task ID for detailed view
steps:
  - type: conditional
    condition: "{{args.task_id}}"
    true_branch:
      - type: mcp-tool
        server: trendradar
        tool: get_task_progress
        parameters:
          task_id: "{{args.task_id}}"
    false_branch:
      - type: mcp-tool
        server: trendradar
        tool: list_tasks
        parameters:
          limit: 20
      - type: skill
        name: summarize
        input: "Format as status overview: {{mcp_result}}"
```
