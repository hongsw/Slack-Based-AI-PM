# /pm create

Create a new PM task.

## Usage

```
/pm create "<title>" [--desc "<description>"] [--assignee <user>] [--priority <level>] [--due <date>] [--tags <tag1,tag2>]
```

## Description

Creates a new task in the PM system and optionally notifies the team via Slack.

## Arguments

- `title` (required): Task title (quoted string)
- `--desc` (optional): Task description
- `--assignee` (optional): Assigned team member
- `--priority` (optional): low, medium, high, critical (default: medium)
- `--due` (optional): Due date in ISO format (YYYY-MM-DD)
- `--tags` (optional): Comma-separated tags
- `--notify` (optional): Post task creation to Slack

## MCP Tools Used

- `create_task` - Create task in database
- `push_to_slack` - Notify team (if --notify)

## Examples

### Simple task
```
/pm create "Fix login bug"
```

### Full task specification
```
/pm create "Implement OAuth" --desc "Add Google/GitHub OAuth support" --assignee @alice --priority high --due 2026-01-15 --tags auth,feature --notify
```

Output:
```
Task created: abc123
Title: Implement OAuth
Status: defined
Priority: high
Assignee: @alice
Due: 2026-01-15
Tags: auth, feature
```

Slack notification (if --notify):
```
:clipboard: *New Task Defined*
*Title:* Implement OAuth
*Priority:* high
*Assigned:* @alice
*Due:* 2026-01-15

> Add Google/GitHub OAuth support

_React with :white_check_mark: to acknowledge_
```

## Implementation

```yaml
name: pm-create
description: Create a new PM task
arguments:
  - name: title
    type: string
    required: true
    description: Task title
  - name: desc
    type: string
    required: false
    description: Task description
  - name: assignee
    type: string
    required: false
    description: Assignee
  - name: priority
    type: string
    required: false
    default: medium
    enum: [low, medium, high, critical]
  - name: due
    type: string
    required: false
    description: Due date (ISO format)
  - name: tags
    type: string
    required: false
    description: Comma-separated tags
  - name: notify
    type: boolean
    required: false
    default: false
steps:
  - type: mcp-tool
    server: trendradar
    tool: create_task
    parameters:
      title: "{{args.title}}"
      description: "{{args.desc}}"
      slack_channel: "{{env.SLACK_CHANNEL}}"
      assignee: "{{args.assignee}}"
      priority: "{{args.priority}}"
      due_date: "{{args.due}}"
      tags: "{{args.tags | split: ','}}"
    output: task

  - type: conditional
    condition: "{{args.notify}}"
    true_branch:
      - type: mcp-tool
        server: trendradar
        tool: push_to_slack
        parameters:
          channel: "{{env.SLACK_CHANNEL}}"
          message:
            blocks:
              - type: section
                text:
                  type: mrkdwn
                  text: ":clipboard: *New Task Defined*\n*Title:* {{task.title}}\n*Priority:* {{task.priority}}\n*Assigned:* {{task.assignee | default: 'Unassigned'}}\n*Due:* {{task.due_date | default: 'Not set'}}\n\n> {{task.description}}"

  - type: output
    format: |
      Task created: {{task.id}}
      Title: {{task.title}}
      Status: {{task.status}}
      Priority: {{task.priority}}
```
