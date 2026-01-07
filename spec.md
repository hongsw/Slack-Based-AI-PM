# Slack-Based AI PM System Specification (MVP)

## 1. Overview
This specification outlines the Minimum Viable Product (MVP) for a Slack-integrated AI Project Management (PM) system. The system automates PM roles: **task definition**, **next step checking**, **completion verification**, and **boss reporting**. It leverages open-source components for low-cost implementation and high flexibility.

- **Core Goal**: Handle PM workflows in Slack channels, using AI agents for automation.
- **Key Principles**:
  - Minimal setup: Docker/CLI-based deployment.
  - Flexibility: Modular via MCP (Model Context Protocol) for easy agent/tool extensions.
  - Cost: Free/open-source, with optional paid AI model subscriptions (e.g., Claude, OpenAI).
- **Target Use Case**: Team Slack bot that monitors tasks, orchestrates AI agents, and pushes reports.

## 2. Components
The MVP combines three GitHub repositories:

### 2.1 cc-wf-studio (breaking-brake/cc-wf-studio)
- **Role**: Visual workflow designer for PM processes.
- **Key Features Used**:
  - Drag-and-drop editor for nodes: Prompt, Sub-Agent, Skill, MCP, IfElse, AskUserQuestion.
  - AI-assisted refinement via natural language.
  - Export to `.claude` files for execution.
  - Slack sharing (beta) for workflow previews and imports.
- **Why Selected**: Enables no-code workflow creation for PM steps (e.g., task def → check → verify → report).
- **Dependencies**: Claude Code CLI, VSCode.

### 2.2 oh-my-opencode (code-yeongyu/oh-my-opencode)
- **Role**: Multi-agent orchestration harness for task execution.
- **Key Features Used**:
  - Sisyphus orchestrator with sub-agents (e.g., oracle for strategy, librarian for docs).
  - Background parallel tasks and Ralph Loop for persistent completion.
  - LSP/AST tools for code-related PM (if tasks involve dev).
  - MCP integration for tool calling.
- **Why Selected**: Handles agent delegation and resilience in PM workflows.
- **Dependencies**: OpenCode CLI, auth plugins for AI models.

### 2.3 TrendRadar (sansan0/TrendRadar)
- **Role**: MCP server and Slack notifier for monitoring/reporting.
- **Key Features Used**:
  - Slack webhook pushes for reports and alerts.
  - MCP tools for AI analysis (e.g., trend analysis, sentiment on task updates).
  - Keyword filtering and incremental monitoring of Slack/RSS feeds.
  - Docker deployment for the backend.
- **Why Selected**: Provides Slack integration and MCP bridge for queries.
- **Dependencies**: Python, Docker.

## 3. Architecture
- **High-Level Flow**:
  1. **Workflow Design**: Use cc-wf-studio in VSCode to build PM workflow (e.g., nodes for each PM step).
  2. **Agent Execution**: Export to `.claude` and run via oh-my-opencode's harness for multi-agent handling.
  3. **Monitoring & Reporting**: TrendRadar monitors Slack inputs (via webhooks/RSS proxy), triggers workflows via MCP, and pushes reports.
- **Integration Points**:
  - **MCP as Glue**: All components support MCP. TrendRadar's MCP server exposes tools (e.g., `analyze_topic_trend`) callable from cc-wf-studio nodes and oh-my-opencode agents.
  - **Slack Interface**: TrendRadar handles inbound (webhooks) and outbound pushes. cc-wf-studio shares workflows to Slack for review.
  - **Data Flow**: Slack message → TrendRadar filter → MCP call to workflow → oh-my-opencode agents → Report back to Slack.
- **Tech Stack**:
  - Backend: Docker-compose (TrendRadar + MCP servers).
  - Frontend: Slack app (webhooks).
  - AI: Claude/OpenAI/Gemini via auth plugins.
- **Diagram** (Text-based):
  ```
  Slack Channel <--> TrendRadar (Monitor/Push) <--> MCP Server
                                      |
                                      v
  cc-wf-studio (Design/Export) --> oh-my-opencode (Execute Agents)
  ```

## 4. Workflow Implementation
### 4.1 PM Workflow Example
- **Task Definition**: Slack message with keywords (e.g., "Define task: Build feature X"). TrendRadar filters and triggers MCP `get_latest_news`-like tool to parse.
- **Next Step Check**: oh-my-opencode's oracle sub-agent analyzes progress, suggests steps via Ralph Loop.
- **Completion Verification**: cc-wf-studio's IfElse node checks via AskUserQuestion (Slack prompt) or AI sentiment analysis from TrendRadar.
- **Boss Report**: Aggregate results, push formatted report to Slack via TrendRadar.

### 4.2 Setup Steps
1. **Install cc-wf-studio**:
   ```
   git clone https://github.com/breaking-brake/cc-wf-studio.git
   cd cc-wf-studio
   npm install
   cd src/webview && npm install && cd ../..
   npm run build
   npx vsce package
   ```
   Install .vsix in VSCode. Verify Claude Code CLI.

2. **Install oh-my-opencode**:
   ```
   bunx oh-my-opencode install --no-tui --claude=yes --chatgpt=yes --gemini=yes
   ```
   Authenticate models.

3. **Install TrendRadar**:
   ```
   git clone https://github.com/sansan0/TrendRadar.git
   cd TrendRadar/docker
   ```
   Edit `.env` for Slack webhook. Run `docker compose up -d`.

4. **Integrate**:
   - Configure MCP in cc-wf-studio and oh-my-opencode to point to TrendRadar's `http://localhost:3333/mcp`.
   - Design workflow in cc-wf-studio, export, and load into oh-my-opencode.
   - Set TrendRadar keywords for PM terms (e.g., "task", "verify").

## 5. Deployment
- **Environment**: Local/Docker or GitHub Actions for scheduling.
- **Scaling**: Start local; extend to cloud (e.g., R2 storage in TrendRadar).
- **Security**: Use env vars for API keys; local SQLite for data.
- **Monitoring**: TrendRadar's `manage.py status`; oh-my-opencode session logs.

## 6. Limitations & Extensions
- **MVP Limits**: Basic Slack (no full bot interactivity); assumes manual workflow triggers.
- **Future**: Add full Slack bot via bolt-python; multi-agent scaling in oh-my-opencode.
- **Testing**: Prototype in VSCode, test Slack pushes.

## 7. References
- Repos: [cc-wf-studio](https://github.com/breaking-brake/cc-wf-studio), [oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode), [TrendRadar](https://github.com/sansan0/TrendRadar).
- Last Updated: January 08, 2026.