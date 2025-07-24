# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0

import logging
import os
import sys
import uvicorn
import contextlib
import json
from typing import AsyncIterator, Dict, Any, List
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import TextContent, Tool
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import Scope, Receive, Send
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from opensearchpy import OpenSearch

# Add the src directory to Python path to fix imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, '..')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


def load_env_config():
    """Load configuration from .env file"""
    env_path = os.path.join(current_dir, '..', '..', '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()


def get_local_opensearch_client() -> OpenSearch:
    """Create a simple OpenSearch client for local cluster"""
    opensearch_url = os.getenv('OPENSEARCH_URL', 'http://localhost:9200')
    
    client_kwargs = {
        'hosts': [opensearch_url],
        'use_ssl': opensearch_url.startswith('https'),
        'verify_certs': False,  # For local development
        'ssl_show_warn': False,
    }
    
    return OpenSearch(**client_kwargs)


def format_log_search_results(hits: List[Dict], keyword: str) -> str:
    """Format search results for better readability"""
    if not hits:
        return f"No logs found containing '{keyword}'"
    
    summary = f"Found {len(hits)} logs containing '{keyword}':\n\n"
    
    for i, hit in enumerate(hits, 1):
        source = hit.get('_source', {})
        index = hit.get('_index', 'unknown')
        score = hit.get('_score', 0)
        
        summary += f"=== Log {i} (Score: {score:.2f}) ===\n"
        summary += f"Index: {index}\n"
        
        # Extract key fields commonly found in logs
        timestamp = source.get('@timestamp') or source.get('timestamp') or source.get('time')
        if timestamp:
            summary += f"Timestamp: {timestamp}\n"
        
        message = source.get('message') or source.get('msg') or source.get('log')
        if message:
            summary += f"Message: {message}\n"
        
        level = source.get('level') or source.get('severity') or source.get('log_level')
        if level:
            summary += f"Level: {level}\n"
        
        host = source.get('host') or source.get('hostname') or source.get('server')
        if host:
            if isinstance(host, dict):
                host = host.get('name', host)
            summary += f"Host: {host}\n"
        
        # Add other relevant fields
        for key, value in source.items():
            if key not in ['@timestamp', 'timestamp', 'time', 'message', 'msg', 'log', 'level', 'severity', 'log_level', 'host', 'hostname', 'server']:
                if len(str(value)) < 100:  # Only show short values
                    summary += f"{key}: {value}\n"
        
        summary += "\n"
    
    return summary


async def create_simple_local_server() -> Server:
    """Create a simple MCP server with log search capabilities"""
    load_env_config()
    
    opensearch_url = os.getenv('OPENSEARCH_URL', 'http://localhost:9200')
    logging.info(f"Connecting to local OpenSearch cluster: {opensearch_url}")
    
    server = Server('opensearch-log-search-server')
    
    # Define tools focused on log searching
    tools_info = {
        'search_logs_by_keyword': {
            'description': 'Search for logs containing specific keywords across indices. Provides detailed log information and summary.',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'keyword': {
                        'type': 'string', 
                        'description': 'Keyword to search for in log messages (e.g., "authentication", "error", "failed")'
                    },
                    'index_pattern': {
                        'type': 'string', 
                        'description': 'Index pattern to search in (e.g., "agent-inventory-log-*", "*", or specific index name)',
                        'default': '*'
                    },
                    'size': {
                        'type': 'integer', 
                        'description': 'Number of results to return (default: 10, max: 100)',
                        'default': 10
                    },
                    'time_range': {
                        'type': 'string',
                        'description': 'Time range for search (e.g., "1h", "24h", "7d"). Optional.',
                        'default': ''
                    }
                },
                'required': ['keyword']
            }
        },
        'search_logs_advanced': {
            'description': 'Advanced log search with custom OpenSearch query DSL for complex searches',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'index_pattern': {
                        'type': 'string', 
                        'description': 'Index pattern to search in',
                        'default': '*'
                    },
                    'query': {
                        'type': 'object', 
                        'description': 'OpenSearch query DSL for complex searches'
                    },
                    'size': {
                        'type': 'integer', 
                        'description': 'Number of results to return (default: 10)',
                        'default': 10
                    }
                },
                'required': ['query']
            }
        },
        'list_log_indices': {
            'description': 'List all available log indices in the cluster',
            'input_schema': {
                'type': 'object',
                'properties': {
                    'pattern': {
                        'type': 'string',
                        'description': 'Filter indices by pattern (e.g., "log", "agent")',
                        'default': ''
                    }
                },
                'required': []
            }
        },
        'cluster_health': {
            'description': 'Get cluster health information',
            'input_schema': {
                'type': 'object',
                'properties': {},
                'required': []
            }
        }
    }

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        tools = []
        for tool_name, tool_info in tools_info.items():
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
        try:
            client = get_local_opensearch_client()
            
            if name == 'search_logs_by_keyword':
                keyword = arguments.get('keyword')
                index_pattern = arguments.get('index_pattern', '*')
                size = min(arguments.get('size', 10), 100)  # Cap at 100
                time_range = arguments.get('time_range', '')
                
                if not keyword:
                    raise ValueError("'keyword' is required for log search")
                
                # Build query
                query = {
                    "query": {
                        "bool": {
                            "should": [
                                {"match": {"message": keyword}},
                                {"match": {"msg": keyword}},
                                {"match": {"log": keyword}},
                                {"wildcard": {"message": f"*{keyword}*"}},
                                {"wildcard": {"msg": f"*{keyword}*"}},
                                {"wildcard": {"log": f"*{keyword}*"}}
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "size": size,
                    "sort": [{"@timestamp": {"order": "desc"}}]
                }
                
                # Add time range if specified
                if time_range:
                    query["query"]["bool"]["filter"] = [{
                        "range": {
                            "@timestamp": {
                                "gte": f"now-{time_range}"
                            }
                        }
                    }]
                
                response = client.search(index=index_pattern, body=query)
                hits = response.get('hits', {}).get('hits', [])
                
                formatted_result = format_log_search_results(hits, keyword)
                return [TextContent(type='text', text=formatted_result)]
                
            elif name == 'search_logs_advanced':
                index_pattern = arguments.get('index_pattern', '*')
                query = arguments.get('query')
                size = arguments.get('size', 10)
                
                if not query:
                    raise ValueError("'query' is required for advanced search")
                
                # Ensure size is set in query
                if 'size' not in query:
                    query['size'] = size
                
                response = client.search(index=index_pattern, body=query)
                return [TextContent(type='text', text=json.dumps(response, indent=2))]
                
            elif name == 'list_log_indices':
                pattern = arguments.get('pattern', '')
                response = client.cat.indices(format='json')
                
                if pattern:
                    # Filter indices containing the pattern
                    filtered_indices = [idx for idx in response if pattern.lower() in idx.get('index', '').lower()]
                    response = filtered_indices
                
                # Format for better readability
                if response:
                    result = "Available indices:\n\n"
                    for idx in response:
                        index_name = idx.get('index', 'N/A')
                        doc_count = idx.get('docs.count', 'N/A')
                        size = idx.get('store.size', 'N/A')
                        result += f"• {index_name} (docs: {doc_count}, size: {size})\n"
                else:
                    result = "No indices found matching the pattern."
                
                return [TextContent(type='text', text=result)]
                
            elif name == 'cluster_health':
                response = client.cluster.health()
                return [TextContent(type='text', text=json.dumps(response, indent=2))]
                
            else:
                raise ValueError(f'Unknown tool: {name}')
                
        except Exception as e:
            return [TextContent(
                type='text',
                text=f'Error executing {name}: {str(e)}'
            )]

    return server


class SimpleMCPStarletteApp:
    """Simple Starlette app for local OpenSearch log search"""
    
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
        return Response('OpenSearch Log Search MCP Server - OK', status_code=200)

    @contextlib.asynccontextmanager
    async def lifespan(self, app: Starlette) -> AsyncIterator[None]:
        """Context manager for session manager lifecycle"""
        async with self.session_manager.run():
            logging.info('OpenSearch Log Search MCP Server started!')
            try:
                yield
            finally:
                logging.info('OpenSearch Log Search MCP Server shutting down...')

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


async def serve_simple_local(
    host: str = '0.0.0.0',
    port: int = 9900,
) -> None:
    """Start the simple local OpenSearch log search MCP streaming server"""
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Starting OpenSearch Log Search MCP Server on {host}:{port}")
    
    mcp_server = await create_simple_local_server()
    app_handler = SimpleMCPStarletteApp(mcp_server)
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
    asyncio.run(serve_simple_local())