
# An introduction to MCP

## How is MCP Designed
1. Directly plugin to LLMs
2. Not coupled to any LLM Vendor. You can use any LLM model and switch between any vendor.

## Components of MCP
MCP Host: The AI application that coordinates and manages one or multiple MCP clients[Claude Desktop, VS Code, Etc.]
MCP Client: A component that maintains a connection to an MCP server and obtains context from an MCP server for the MCP host to use
MCP Server: A program that provides context to MCP clients

## Transport Layer
1. STDIO Transfer - For Local / on-premise MCP Server
2. Streamable HTTP / SSE transport - For connecting to Remote MCP Server

* The connection between an MCP Client to an MCP Server is always one-to-one. No one MCP client can connect to more than one MCP Server, i.e., an MCP client inside a host say VS Code can't be used to connect a Slack as well as AWS S3. You need two different clients to connect to two of these servers.

### Security
Security wise HTTP is more secure than STDIO

## Ways to Implement MCP Serve Requests

### Low Level Server(uv add "mcp[cli]")
<code:Python>
from mcp.server.server import Server
</code>

### FastMCP 1.0 (uv add "mcp[cli]")
<code:Python>
from mcp.server.fastmcp import FastMCP
</code>

* FastMCP Makes life simpler by providing Decorators to build tools in the simplest way

#### Create Server
mcp = FastMCP("Eco Server")

#### Create Tool
@mcp.tool()
def echo(text:str) -> str:
    """Echos the input Text"""
    return text


### FastMCP 2.0 (uv add fastmcp)
from fastmcp import FastMCP

mcp = FastMCP("Demo 🚀")

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b

if __name__ == "__main__":
    mcp.run()

## Core Components
### MCP Servers
 - Exposes Tools
 - Exposes Resources
 - Exposes Propmpts

### MCP Client
- Invoke Tools
- Queries for Resources
- Interpolates Propmts

### Tools: (Model-Controlled)
Functions invoked by the model

### Resources:(Application-Controlled)
Data exposed to the application

### Prompts:(User-Controlled)
Pre-defined templates for AI interactions

## Observability:
### MCP Inspector
An observability tool to monitor MCP
More details can be found here: https://modelcontextprotocol.io/docs/tools/inspector#python

### LLM.txt
Built for making Agents understand better about the context
https://docs.langchain.com/llms.txt
https://docs.langchain.com/llms-full.txt

### mcp doc
https://github.com/langchain-ai/mcpdoc

## MCPilot Design Implication
MCPilot exposes itself as a SINGLE MCP server to any client.
Internally it maintains N MCP clients — one per upstream server.
LlamaIndex RAG layer resolves intent → selects correct internal client → routes call.
This is the core architectural pattern of the gateway.


