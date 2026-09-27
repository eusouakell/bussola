"""Shared registration constants of the MCP tools."""

from mcp.types import ToolAnnotations

# Every tool is read-only, idempotent and closed-world (contratos §5).
TOOL_ANNOTATIONS = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
