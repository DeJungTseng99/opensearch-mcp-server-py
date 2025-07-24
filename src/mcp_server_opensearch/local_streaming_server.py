# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import uvicorn
import contextlib
from typing import AsyncIterator
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import Scope, Receive, Send
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

# Add the src directory to Python path to fix imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


def load_env_config():
    """Load configuration from .env file"""
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


async def create_local_mcp_server() -> Server:
    """Create MCP server configured for local OpenSearch cluster"""
    # Load environment configuration
    load_env_config()
    
    # Import tools after path is set
    from tools.tool_filter import get_tools
    from tools.tool_generator import generate_tools_from_openapi
    
    # Ensure we're connecting to the local cluster
    opensearch_url = os.getenv('OPENSEARCH_URL', 'http://localhost:9200')
    if 'localhost:9200' not in opensearch_url:
        logging.warning(f"Expected localhost:9200 but got {opensearch_url}, using localhost:9200")
        os.environ['OPENSEARCH_URL'] = 'http://localhost:9200'
    
    logging.info(f"Connecting to local OpenSearch cluster: {os.environ['OPENSEARCH_URL']}")
    
    server = Server('opensearch-local-mcp-server')
    
    try:
        # Generate tools and get enabled tools for single mode (local cluster)
        await generate_tools_from_openapi()
        enabled_tools = get_tools('single', '')
        logging.info(f'Enabled tools for local cluster: {list(enabled_tools.keys())}')
    except Exception as e:
        logging.error(f'Error generating tools: {e}')
        # Fall back to basic tools if tool generation fails
        enabled_tools = {}
        logging.info('Using fallback: no tools available due to configuration error')

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []
        for tool_name, tool_info in enabled_tools.items():
            tools.append(
                Tool(
                    name=tool_name,
                    description=tool_info['description'],
                    inputSchema=tool_info['input_schema'],
                )
            )
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        tool = enabled_tools.get(name)
        if not tool:
            raise ValueError(f'Unknown or disabled tool: {name}')
        parsed = tool['args_model'](**arguments)
        return await tool['function'](parsed)

    return server


class LocalMCPStarletteApp:
    """Starlette app configured for local OpenSearch cluster"""
    
    def __init__(self, mcp_server: Server):
        self.mcp_server = mcp_server
        self.sse = SseServerTransport('/messages/')
        self.session_manager = StreamableHTTPSessionManager(
            app=self.mcp_server,
            event_store=None,
            json_response=False,
            stateless=False,
        )

    async def handle_sse(self, request: Request) -> None:
        async with self.sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await self.mcp_server.run(
                read_stream,
                write_stream,
                self.mcp_server.create_initialization_options(),
            )
        return Response()

    async def handle_health(self, request: Request) -> Response:
        """Health check endpoint"""
        return Response('Local OpenSearch MCP Server - OK', status_code=200)

    @contextlib.asynccontextmanager
    async def lifespan(self, app: Starlette) -> AsyncIterator[None]:
        """Context manager for session manager lifecycle"""
        async with self.session_manager.run():
            logging.info('Local OpenSearch MCP Server started with StreamableHTTP session manager!')
            try:
                yield
            finally:
                logging.info('Local OpenSearch MCP Server shutting down...')

    async def handle_streamable_http(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Handle streamable HTTP requests"""
        await self.session_manager.handle_request(scope, receive, send)

    def create_app(self) -> Starlette:
        return Starlette(
            routes=[
                Route('/sse', endpoint=self.handle_sse, methods=['GET']),
                Route('/health', endpoint=self.handle_health, methods=['GET']),
                Mount('/messages/', app=self.sse.handle_post_message),
                Mount('/mcp', app=self.handle_streamable_http),
            ],
            lifespan=self.lifespan,
        )


async def serve_local(
    host: str = '0.0.0.0',
    port: int = 9200,
) -> None:
    """Start the local OpenSearch MCP streaming server"""
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Starting Local OpenSearch MCP Server on {host}:{port}")
    
    mcp_server = await create_local_mcp_server()
    app_handler = LocalMCPStarletteApp(mcp_server)
    app = app_handler.create_app()

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == '__main__':
    import asyncio
    asyncio.run(serve_local())