"""
MCP Server for PM Tools.

Exposes PM tools via Model Context Protocol for integration with:
- cc-wf-studio workflow nodes
- oh-my-opencode agents
- Any MCP-compatible client

Run standalone: python -m pm_tools.mcp_server
Or import and mount with an existing server.
"""

import json
import logging
from typing import Any

# MCP server can use different implementations
# Try fastmcp first, fall back to basic HTTP if not available
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    HAS_MCP_SDK = True
except ImportError:
    HAS_MCP_SDK = False

from .tools import (
    create_task,
    update_task_status,
    get_task_progress,
    get_tasks_by_status,
    generate_boss_report,
    push_to_slack,
    verify_task_completion,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Tool schemas for MCP
TOOL_SCHEMAS = {
    "create_task": {
        "name": "create_task",
        "description": "Create a new PM task with title, description, and metadata",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Task title (required)",
                },
                "slack_channel": {
                    "type": "string",
                    "description": "Slack channel for notifications (required)",
                },
                "description": {
                    "type": "string",
                    "description": "Task description",
                },
                "assignee": {
                    "type": "string",
                    "description": "Assigned person or team",
                },
                "due_date": {
                    "type": "string",
                    "description": "Due date in ISO format (YYYY-MM-DD)",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Task priority level",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for categorization",
                },
                "notify_slack": {
                    "type": "boolean",
                    "description": "Send Slack notification on creation",
                    "default": True,
                },
            },
            "required": ["title", "slack_channel"],
        },
    },
    "update_task_status": {
        "name": "update_task_status",
        "description": "Update task status and add progress notes",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to update (required)",
                },
                "status": {
                    "type": "string",
                    "enum": ["defined", "in_progress", "review", "completed", "blocked"],
                    "description": "New task status",
                },
                "progress_note": {
                    "type": "string",
                    "description": "Progress update content",
                },
                "sentiment_score": {
                    "type": "number",
                    "minimum": -1,
                    "maximum": 1,
                    "description": "Sentiment score from -1 (negative) to 1 (positive)",
                },
                "agent_analysis": {
                    "type": "string",
                    "description": "AI agent analysis text",
                },
                "assignee": {
                    "type": "string",
                    "description": "Update assignee",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Update priority",
                },
                "notify_slack": {
                    "type": "boolean",
                    "description": "Send Slack notification",
                    "default": False,
                },
            },
            "required": ["task_id"],
        },
    },
    "get_task_progress": {
        "name": "get_task_progress",
        "description": "Get task details including all progress updates and verification status",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to retrieve (required)",
                },
            },
            "required": ["task_id"],
        },
    },
    "get_tasks_by_status": {
        "name": "get_tasks_by_status",
        "description": "Query tasks by status with optional channel filter",
        "inputSchema": {
            "type": "object",
            "properties": {
                "statuses": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["defined", "in_progress", "review", "completed", "blocked"],
                    },
                    "description": "List of status values to filter by (required)",
                },
                "slack_channel": {
                    "type": "string",
                    "description": "Optional channel filter",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "description": "Maximum number of tasks to return",
                    "default": 50,
                },
            },
            "required": ["statuses"],
        },
    },
    "generate_boss_report": {
        "name": "generate_boss_report",
        "description": "Generate a formatted daily PM report with task counts, highlights, and risks",
        "inputSchema": {
            "type": "object",
            "properties": {
                "slack_channel": {
                    "type": "string",
                    "description": "Filter by channel (omit for all channels)",
                },
                "include_highlights": {
                    "type": "boolean",
                    "description": "Include highlights section",
                    "default": True,
                },
                "include_risks": {
                    "type": "boolean",
                    "description": "Include risks section",
                    "default": True,
                },
                "days_for_due_soon": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 30,
                    "description": "Days ahead to check for due tasks",
                    "default": 3,
                },
            },
        },
    },
    "push_to_slack": {
        "name": "push_to_slack",
        "description": "Send a formatted message to Slack channel",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Simple text message",
                },
                "channel": {
                    "type": "string",
                    "description": "Target Slack channel",
                },
                "thread_ts": {
                    "type": "string",
                    "description": "Thread timestamp for replies",
                },
                "message_type": {
                    "type": "string",
                    "enum": ["task_alert", "progress_update", "boss_report", "verification"],
                    "description": "Type of message for auto-formatting",
                },
                "task_title": {"type": "string"},
                "priority": {"type": "string"},
                "assignee": {"type": "string"},
                "due_date": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string"},
                "sentiment_score": {"type": "number"},
                "content": {"type": "string"},
            },
        },
    },
    "verify_task_completion": {
        "name": "verify_task_completion",
        "description": "Mark a task as verified/completed with evidence",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "Task ID to verify (required)",
                },
                "verified_by": {
                    "type": "string",
                    "enum": ["user", "agent"],
                    "description": "Who verified the task",
                    "default": "agent",
                },
                "method": {
                    "type": "string",
                    "enum": ["manual", "automated", "hybrid"],
                    "description": "Verification method",
                    "default": "automated",
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Evidence strings supporting verification",
                },
                "notify_slack": {
                    "type": "boolean",
                    "description": "Send Slack notification",
                    "default": True,
                },
            },
            "required": ["task_id"],
        },
    },
}

# Tool function mapping
TOOL_FUNCTIONS = {
    "create_task": create_task,
    "update_task_status": update_task_status,
    "get_task_progress": get_task_progress,
    "get_tasks_by_status": get_tasks_by_status,
    "generate_boss_report": generate_boss_report,
    "push_to_slack": push_to_slack,
    "verify_task_completion": verify_task_completion,
}


def call_tool(name: str, arguments: dict) -> dict:
    """Call a PM tool by name with arguments."""
    if name not in TOOL_FUNCTIONS:
        return {"success": False, "error": f"Unknown tool: {name}"}

    try:
        return TOOL_FUNCTIONS[name](**arguments)
    except TypeError as e:
        return {"success": False, "error": f"Invalid arguments: {e}"}
    except Exception as e:
        logger.exception(f"Error calling tool {name}")
        return {"success": False, "error": str(e)}


def get_tool_schemas() -> list[dict]:
    """Get all tool schemas for MCP registration."""
    return list(TOOL_SCHEMAS.values())


# MCP SDK Server Implementation
if HAS_MCP_SDK:
    app = Server("pm-tools")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """List available PM tools."""
        tools = []
        for schema in TOOL_SCHEMAS.values():
            tools.append(
                Tool(
                    name=schema["name"],
                    description=schema["description"],
                    inputSchema=schema["inputSchema"],
                )
            )
        return tools

    @app.call_tool()
    async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls."""
        result = call_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    async def run_server():
        """Run the MCP server using stdio transport."""
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options(),
            )


# HTTP Server fallback for environments without MCP SDK
def create_http_handler():
    """Create a simple HTTP handler for MCP-like requests."""
    from http.server import BaseHTTPRequestHandler

    class MCPHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            request = json.loads(body)

            if self.path == "/tools/list":
                response = {"tools": get_tool_schemas()}
            elif self.path == "/tools/call":
                name = request.get("name")
                arguments = request.get("arguments", {})
                response = call_tool(name, arguments)
            else:
                response = {"error": "Unknown endpoint"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())

        def do_GET(self):
            if self.path == "/health":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "healthy"}).encode())
            elif self.path == "/tools":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(get_tool_schemas()).encode())
            else:
                self.send_response(404)
                self.end_headers()

    return MCPHandler


def run_http_server(port: int = 3334):
    """Run HTTP server fallback."""
    from http.server import HTTPServer

    handler = create_http_handler()
    server = HTTPServer(("0.0.0.0", port), handler)
    logger.info(f"PM Tools MCP server running on http://0.0.0.0:{port}")
    logger.info(f"  Tools list: http://localhost:{port}/tools")
    logger.info(f"  Health check: http://localhost:{port}/health")
    server.serve_forever()


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="PM Tools MCP Server")
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default="stdio",
        help="Server mode: stdio (MCP standard) or http (REST fallback)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=3334,
        help="Port for HTTP mode (default: 3334)",
    )
    args = parser.parse_args()

    if args.mode == "stdio" and HAS_MCP_SDK:
        asyncio.run(run_server())
    else:
        if args.mode == "stdio" and not HAS_MCP_SDK:
            logger.warning("MCP SDK not available, falling back to HTTP mode")
        run_http_server(args.port)
