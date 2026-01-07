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

## 6. MCP Integration Specification

### 6.1 MCP Architecture Overview
MCP (Model Context Protocol) serves as the unified communication layer between all components. Each component exposes and/or consumes MCP tools.

```
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Communication Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  TrendRadar MCP Server (http://localhost:3333/mcp)              │
│  ├── News Tools: aggregate_news, search_news, get_latest_news   │
│  ├── Analysis: get_trending_topics, analyze_sentiment           │
│  ├── Comparison: compare_periods (WoW/MoM analysis)             │
│  └── Storage: sync_from_remote, get_storage_status              │
├─────────────────────────────────────────────────────────────────┤
│  PM Tools MCP Server (http://localhost:3334)                    │
│  ├── Task CRUD: create_task, get_task_by_id, get_task_progress  │
│  ├── Status: update_task_status (with verification records)     │
│  ├── Reporting: generate_boss_report (daily/weekly/custom)      │
│  └── Slack: push_to_slack (webhook wrapper)                     │
├─────────────────────────────────────────────────────────────────┤
│  oh-my-opencode Curated MCPs                                    │
│  ├── Exa (web search)                                           │
│  ├── Context7 (official documentation)                          │
│  └── Grep.app (GitHub code search)                              │
├─────────────────────────────────────────────────────────────────┤
│  cc-wf-studio MCP Tool Nodes                                    │
│  └── Dynamic form generation based on tool schemas              │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 TrendRadar MCP Tools Reference

| Tool Name | Purpose | Parameters | Returns |
|-----------|---------|------------|---------|
| `get_latest_news` | Fetch recent news items | `count`, `source_filter` | Array of news objects |
| `search_news` | Search news by keywords | `query`, `date_range`, `limit` | Filtered news array |
| `aggregate_news` | Cross-platform deduplication | `sources[]`, `time_window` | Deduplicated results |
| `get_trending_topics` | Extract trending themes | `category`, `limit` | Topic array with scores |
| `analyze_sentiment` | Sentiment analysis on text | `text`, `context` | Sentiment score (-1 to 1) |
| `find_related_news` | Find similar articles | `article_id`, `threshold` | Related articles array |
| `compare_periods` | Week-over-week/Month-over-month | `metric`, `period_type` | Comparison report |
| `resolve_date_range` | Natural language date parsing | `query` (e.g., "last week") | Start/end timestamps |
| `sync_from_remote` | Sync from S3/R2 storage | `bucket`, `prefix` | Sync status |
| `get_storage_status` | Check storage health | None | Storage metrics |

### 6.3 PM Tools MCP Reference

Custom PM-specific tools for task management, verification, and Slack integration.

| Tool Name | Purpose | Parameters | Returns |
|-----------|---------|------------|---------|
| `create_task` | Create new PM task | `title`, `description`, `slack_channel`, `priority?`, `due_date?`, `assignee?`, `tags?` | Task object with ID |
| `update_task_status` | Update status + verification | `task_id`, `status`, `verification?`, `progress_note?` | Updated task object |
| `get_task_progress` | Query tasks with updates | `task_id?`, `status_filter?`, `include_updates?`, `limit?` | Tasks array + summary |
| `get_task_by_id` | Get single task details | `task_id` | Task with updates + verification |
| `generate_boss_report` | Generate formatted report | `report_type`, `date_range?`, `include_metrics?` | Report object |
| `push_to_slack` | Send Slack message | `message` (Block Kit), `channel?`, `thread_ts?` | Push result |

**Status Values**: `defined`, `in_progress`, `review`, `completed`, `blocked`

**Report Types**: `daily`, `weekly`, `custom`

### 6.4 MCP Configuration

**Full Docker Stack** (`docker-compose.yml`):
```yaml
services:
  trendradar-mcp:
    image: wantcat/trendradar-mcp
    ports:
      - "3333:3333"
    volumes:
      - ./data/output:/app/output
    environment:
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}

  pm-tools:
    build: ./mcp-tools
    ports:
      - "3334:3334"
    volumes:
      - ./data/pm:/app/output/pm
    environment:
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
      - PM_DATABASE_PATH=/app/output/pm/tasks.db
```

**cc-wf-studio MCP Configuration** (`.claude/settings.json`):
```json
{
  "mcpServers": {
    "trendradar": {
      "url": "http://localhost:3333/mcp",
      "description": "News monitoring and sentiment analysis"
    },
    "pm-tools": {
      "url": "http://localhost:3334",
      "description": "PM task management, reports, and Slack integration"
    }
  }
}
```

**oh-my-opencode MCP Configuration**:
```yaml
# ~/.config/opencode/config.yaml
mcp:
  trendradar:
    endpoint: http://localhost:3333/mcp
    enabled: true
  pm-tools:
    endpoint: http://localhost:3334
    enabled: true
  context7:
    enabled: true  # Built-in
  exa:
    enabled: true  # Built-in
```

## 7. Workflow Node Definitions

### 7.1 Node Types Schema

cc-wf-studio workflows use the following node types for PM automation:

#### Prompt Node
```json
{
  "type": "prompt",
  "id": "unique-id",
  "config": {
    "template": "Define task: {{task_description}}",
    "variables": ["task_description"],
    "outputVariable": "task_definition"
  }
}
```

#### Sub-Agent Node
```json
{
  "type": "sub-agent",
  "id": "unique-id",
  "config": {
    "agentType": "oracle|librarian|frontend|explore",
    "task": "Analyze task progress and suggest next steps",
    "context": "{{previous_output}}",
    "outputVariable": "agent_result"
  }
}
```

#### MCP Tool Node
```json
{
  "type": "mcp-tool",
  "id": "unique-id",
  "config": {
    "server": "trendradar",
    "tool": "analyze_sentiment",
    "parameters": {
      "text": "{{task_update}}",
      "context": "pm_workflow"
    },
    "outputVariable": "sentiment_score"
  }
}
```

#### IfElse Node
```json
{
  "type": "ifelse",
  "id": "unique-id",
  "config": {
    "condition": "{{sentiment_score}} > 0.5",
    "trueBranch": "node-complete",
    "falseBranch": "node-needs-work"
  }
}
```

#### AskUserQuestion Node
```json
{
  "type": "ask-user",
  "id": "unique-id",
  "config": {
    "question": "Is task '{{task_name}}' complete?",
    "options": ["Yes, verified", "No, needs more work", "Skip for now"],
    "timeout": 3600,
    "outputVariable": "user_response"
  }
}
```

#### Skill Node
```json
{
  "type": "skill",
  "id": "unique-id",
  "config": {
    "skillName": "summarize",
    "input": "{{all_task_updates}}",
    "outputVariable": "summary"
  }
}
```

### 7.2 PM Workflow Templates

**Template: Daily Task Review**
```
Nodes: [Prompt → MCP(get_latest_news) → Sub-Agent(oracle) → IfElse → AskUserQuestion → MCP(Slack push)]
```

**Template: Task Completion Verification**
```
Nodes: [Prompt → MCP(analyze_sentiment) → IfElse → Sub-Agent(librarian) → Skill(summarize) → MCP(Slack push)]
```

## 8. Data Model & Storage

### 8.1 Task Data Schema
```typescript
interface PMTask {
  id: string;
  title: string;
  description: string;
  status: 'defined' | 'in_progress' | 'review' | 'completed' | 'blocked';
  assignee?: string;
  slack_channel: string;
  slack_thread_ts?: string;
  created_at: string;
  updated_at: string;
  due_date?: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  tags: string[];
  progress_updates: ProgressUpdate[];
  verification: VerificationRecord | null;
}

interface ProgressUpdate {
  timestamp: string;
  source: 'slack' | 'agent' | 'manual';
  content: string;
  sentiment_score?: number;
  agent_analysis?: string;
}

interface VerificationRecord {
  verified_by: 'user' | 'agent';
  verified_at: string;
  method: 'manual' | 'automated' | 'hybrid';
  evidence: string[];
}
```

### 8.2 Storage Architecture

**TrendRadar SQLite Schema** (`output/pm/{date}.db`):
```sql
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'defined',
  slack_channel TEXT NOT NULL,
  slack_thread_ts TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  due_date TEXT,
  priority TEXT DEFAULT 'medium',
  tags TEXT,  -- JSON array
  metadata TEXT  -- JSON object
);

CREATE TABLE progress_updates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT REFERENCES tasks(id),
  timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
  source TEXT NOT NULL,
  content TEXT NOT NULL,
  sentiment_score REAL,
  agent_analysis TEXT
);

CREATE TABLE verifications (
  task_id TEXT PRIMARY KEY REFERENCES tasks(id),
  verified_by TEXT NOT NULL,
  verified_at TEXT DEFAULT CURRENT_TIMESTAMP,
  method TEXT NOT NULL,
  evidence TEXT  -- JSON array
);
```

### 8.3 Remote Storage (Optional)
- **S3/R2 Sync**: Use TrendRadar's `sync_from_remote` for persistence across GitHub Actions runs
- **Backup Strategy**: Daily SQLite exports to `output/pm/backup/`

## 9. Error Handling & Recovery

### 9.1 Error Categories

| Category | Examples | Recovery Strategy |
|----------|----------|-------------------|
| **Network** | MCP timeout, Slack webhook failure | Retry with exponential backoff (3 attempts) |
| **Agent** | Sub-agent crash, model rate limit | Fallback to different model/agent |
| **Workflow** | Invalid node transition, missing variable | Log error, skip to error handler node |
| **Data** | SQLite lock, corrupt JSON | Transaction rollback, restore from backup |
| **Auth** | Expired API key, invalid token | Alert admin via Slack, pause workflow |

### 9.2 Recovery Patterns

**oh-my-opencode Ralph Loop**: Persistent completion enforcer that retries incomplete tasks:
```
1. Task starts → 2. Checkpoint saved → 3. If failure, restore checkpoint → 4. Retry with modified strategy
```

**TrendRadar Slack Retry**:
```python
def push_to_slack(message, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(webhook_url, json=message)
            if response.status_code == 200:
                return True
        except RequestException:
            time.sleep(2 ** attempt)  # Exponential backoff
    return False  # Log failure, queue for manual review
```

### 9.3 Monitoring & Alerts

**Health Check Endpoints**:
- TrendRadar: `http://localhost:3333/health`
- MCP Status: `manage.py status`
- oh-my-opencode: Session logs in `~/.opencode/logs/`

**Alert Triggers**:
- MCP server unresponsive for >60 seconds
- Slack webhook failure rate >10%
- Agent error rate >5%
- Storage sync failure

## 10. oh-my-opencode Agent Integration

### 10.1 Agent Roles in PM Context

| Agent | Model | PM Role | Usage |
|-------|-------|---------|-------|
| **Sisyphus** | Claude Opus 4.5 High | Orchestrator | Delegates PM tasks, maintains context |
| **Oracle** | GPT 5.2 Medium | Strategy | Debugging, design decisions, progress analysis |
| **Librarian** | Claude Sonnet 4.5 | Documentation | Codebase exploration, task documentation |
| **Frontend** | Gemini 3 Pro | UI/Reports | Report formatting, dashboard generation |
| **Explore** | (lightweight) | Search | Rapid codebase scanning for task context |

### 10.2 Magic Words for PM

- `ultrawork` / `ulw`: Enable all features for complex PM tasks
- Sub-agent delegation happens automatically based on task type
- Background parallel tasks for multi-task monitoring

### 10.3 Agent Configuration for PM
```yaml
# Custom agent prompt for PM context
agents:
  sisyphus:
    system_prompt_append: |
      You are managing a PM workflow. Focus on:
      - Task definition clarity
      - Progress verification
      - Stakeholder communication
      - Risk identification
```

## 11. Slack Integration Details

### 11.1 Message Formats

**Task Definition Alert**:
```
📋 *New Task Defined*
*Title:* {{task_title}}
*Priority:* {{priority}}
*Assigned:* {{assignee}}
*Due:* {{due_date}}

> {{description}}

_React with ✅ to acknowledge_
```

**Progress Update**:
```
🔄 *Task Update: {{task_title}}*
*Status:* {{status}}
*Sentiment:* {{sentiment_emoji}} ({{sentiment_score}})

{{update_content}}

📊 <{{dashboard_link}}|View Dashboard>
```

**Boss Report**:
```
📊 *Daily PM Report - {{date}}*

*Completed:* {{completed_count}}
*In Progress:* {{in_progress_count}}
*Blocked:* {{blocked_count}}

*Highlights:*
{{#each highlights}}
• {{this}}
{{/each}}

*Risks:*
{{#each risks}}
⚠️ {{this}}
{{/each}}
```

### 11.2 Webhook Configuration
```bash
# .env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
SLACK_CHANNEL=#pm-updates
SLACK_MENTION_ON_BLOCK=@channel
```

## 12. Limitations & Future Extensions

### 12.1 MVP Limitations
- **Slack Interaction**: Incoming webhooks only; no full bot interactivity (reactions, threads)
- **Workflow Triggers**: Manual or scheduled; no real-time Slack message parsing
- **Single Workspace**: One Slack workspace per deployment
- **Storage**: Local SQLite; no real-time sync across instances

### 12.2 Post-MVP Roadmap

| Phase | Feature | Components |
|-------|---------|------------|
| **v1.1** | Full Slack Bot | Add bolt-python for event subscriptions, slash commands |
| **v1.2** | Real-time Triggers | Slack RTM API, keyword-based workflow triggers |
| **v2.0** | Multi-tenant | Support multiple Slack workspaces, team isolation |
| **v2.1** | Dashboard | Web UI for workflow monitoring, task analytics |
| **v3.0** | Advanced Agents | Custom agent training, organization-specific knowledge |

### 12.3 Testing Strategy
1. **Unit**: Test individual MCP tools, node logic
2. **Integration**: Workflow execution with mock Slack
3. **E2E**: Full pipeline with test Slack workspace
4. **Load**: Multi-task concurrent processing

## 13. References
- Repos: [cc-wf-studio](https://github.com/breaking-brake/cc-wf-studio), [oh-my-opencode](https://github.com/code-yeongyu/oh-my-opencode), [TrendRadar](https://github.com/sansan0/TrendRadar).
- Last Updated: January 08, 2026.