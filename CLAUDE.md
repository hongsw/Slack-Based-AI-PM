# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Slack-integrated AI Project Management system that automates PM workflows: task definition, next step checking, completion verification, and boss reporting.

## Architecture

The system integrates three external components via MCP (Model Context Protocol):

```
Slack Channel <--> TrendRadar (Monitor/Push) <--> MCP Server
                                    |
                                    v
cc-wf-studio (Design/Export) --> oh-my-opencode (Execute Agents)
```

### Components

1. **cc-wf-studio**: Visual workflow designer for PM processes, exports to `.claude` files
2. **oh-my-opencode**: Multi-agent orchestration harness (Sisyphus orchestrator with sub-agents)
3. **TrendRadar**: MCP server and Slack notifier for monitoring/reporting

### Integration Pattern

- MCP serves as the glue between all components
- TrendRadar exposes MCP tools (e.g., `analyze_topic_trend`) callable from workflows
- Data flow: Slack message → TrendRadar filter → MCP call → oh-my-opencode agents → Report to Slack

## Setup Commands

### cc-wf-studio
```bash
git clone https://github.com/breaking-brake/cc-wf-studio.git
cd cc-wf-studio
npm install
cd src/webview && npm install && cd ../..
npm run build
npx vsce package
```

### oh-my-opencode
```bash
bunx oh-my-opencode install --no-tui --claude=yes --chatgpt=yes --gemini=yes
```

### TrendRadar
```bash
git clone https://github.com/sansan0/TrendRadar.git
cd TrendRadar/docker
# Edit .env for Slack webhook
docker compose up -d
```

## MCP Configuration

Configure MCP endpoints to point to TrendRadar's `http://localhost:3333/mcp` in both cc-wf-studio and oh-my-opencode.

## PM Workflow Nodes

Workflows use these node types: Prompt, Sub-Agent, Skill, MCP, IfElse, AskUserQuestion
