#!/usr/bin/env python3
"""
Local OpenSearch MCP Server Startup Script

This script starts the local OpenSearch MCP server that connects to
the local cluster at http://localhost:9200 using configuration from .env file.

Usage:
    python start_local_server.py
"""

import asyncio
import sys
import os

# Add src to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
sys.path.insert(0, src_dir)

from mcp_server_opensearch.simple_local_server import serve_simple_local

if __name__ == '__main__':
    print("Starting OpenSearch Log Search MCP Server...")
    print("Server will be available at: http://0.0.0.0:9900")
    print("Health check: http://0.0.0.0:9900/health")
    print("(Connecting to OpenSearch at localhost:9200)")
    print("")
    print("Available tools:")
    print("• search_logs_by_keyword - Search logs by keyword with smart formatting")
    print("• search_logs_advanced - Advanced search with custom query DSL") 
    print("• list_log_indices - List available log indices")
    print("• cluster_health - Get cluster health")
    print("")
    print("Press Ctrl+C to stop the server")
    
    try:
        asyncio.run(serve_simple_local())
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)