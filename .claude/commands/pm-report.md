# /pm report

Generate and push on-demand boss report.

## Usage

```
/pm report [--date YYYY-MM-DD] [--no-push]
```

## Description

Generates a formatted PM report and optionally pushes it to Slack. By default, generates a report for today and pushes to the configured Slack channel.

## Arguments

- `--date` (optional): Report date in ISO format (YYYY-MM-DD). Defaults to today.
- `--no-push` (optional): Generate report without pushing to Slack.

## Report Contents

The boss report includes (matching spec.md format):

1. **Metrics Summary**
   - Completed task count
   - In-progress task count
   - Blocked task count

2. **Highlights**
   - Tasks completed in last 24 hours
   - Notable progress updates

3. **Risks**
   - Blocked tasks
   - Overdue tasks
   - Tasks due within 3 days

## MCP Tools Used

- `generate_boss_report` - Generate formatted report
- `push_to_slack` - Send to Slack channel

## Examples

### Today's report (default)
```
/pm report
```

Generates and pushes:
```
:bar_chart: *Daily PM Report - 2026-01-08*

*Completed:* 3
*In Progress:* 7
*Blocked:* 1

*Highlights:*
:bullet: Completed: User authentication feature
:bullet: Completed: API rate limiting
:bullet: Completed: Documentation update

*Risks:*
:warning: BLOCKED: OAuth integration (waiting on credentials)
:warning: Due soon: Database migration (due tomorrow)
```

### Custom date
```
/pm report --date 2026-01-07
```

### Preview only (no push)
```
/pm report --no-push
```

## Implementation

```yaml
name: pm-report
description: Generate boss report
arguments:
  - name: date
    type: string
    required: false
    description: Report date (ISO format)
  - name: no-push
    type: boolean
    required: false
    default: false
    description: Skip Slack push
steps:
  - type: mcp-tool
    server: trendradar
    tool: generate_boss_report
    parameters:
      date: "{{args.date}}"
      include_highlights: true
      include_risks: true
    output: report

  - type: conditional
    condition: "!{{args.no-push}}"
    true_branch:
      - type: mcp-tool
        server: trendradar
        tool: push_to_slack
        parameters:
          channel: "{{env.SLACK_CHANNEL}}"
          message:
            blocks:
              - type: header
                text:
                  type: plain_text
                  text: "Daily PM Report - {{report.date}}"
              - type: section
                text:
                  type: mrkdwn
                  text: "{{report.formatted}}"

  - type: output
    format: "{{report.formatted}}"
```

## Scheduling

This command is automatically run by the scheduler:
- Daily at 9 AM PT (weekdays) via Ofelia cron
- Can also be triggered manually at any time
