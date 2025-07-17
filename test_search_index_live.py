#!/usr/bin/env python3
"""
Live test for SearchIndexTool against real OpenSearch MCP Server
"""

import asyncio
import json
import sys
import os

# Add src to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


async def test_search_index_tool():
    """Test SearchIndexTool against running MCP Server."""
    
    print("🔍 Testing SearchIndexTool with live MCP Server...")
    print("📋 Make sure MCP Server is running on http://localhost:9900")
    
    try:
        # Connect to MCP Server
        async with streamablehttp_client("http://localhost:9900/mcp") as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("✅ Connected to MCP Server")
                
                # Initialize the session
                await session.initialize()
                print("✅ Session initialized")
                
                # Test 1: List available tools
                print("\n📋 Test 1: List available tools...")
                # streamibg_server.py 的server.list_tools功能
                tools_response = await session.list_tools()
                available_tools = [tool.name for tool in tools_response.tools]
                print(f"✅ Available tools: {available_tools}")
                
                # Show detailed tool information
                for tool in tools_response.tools:
                    print(f"  • {tool.name}: {tool.description}")
                
                if "SearchIndexTool" not in available_tools:
                    print("❌ SearchIndexTool not available")
                    return
                
                # Test 2: List all indices with remote-production cluster
                print("\n🔍 Test 2: List all indices for remote-production cluster...")
                if "ListIndexTool" in available_tools:
                    result = await session.call_tool("ListIndexTool", {
                        "opensearch_cluster_name": "remote-production"
                    })
                    print(f"📊 Indices result:")
                    print(result.content[0].text[:1000] + "...")
                
                # Test 3: Basic search on all indices
                print("\n🔍 Test 3: Basic search on all indices...")
                search_params = {
                    "opensearch_cluster_name": "remote-production",
                    "index": "_all",
                    "query": {
                        "query": {
                            "match_all": {}
                        },
                        "size": 5
                    }
                }
                
                if "SearchIndexTool" in available_tools:
                    result = await session.call_tool("SearchIndexTool", search_params)
                    print(f"📊 Search result:")
                    print(result.content[0].text[:500] + "...")
                
                # Test 4: Search with size limit
                print("\n🔍 Test 4: Search with limited results...")
                search_params = {
                    "opensearch_cluster_name": "remote-production",
                    "index": "_all",
                    "query": {
                        "query": {
                            "match_all": {}
                        },
                        "size": 5
                    }
                }
                
                if "SearchIndexTool" in available_tools:
                    result = await session.call_tool("SearchIndexTool", search_params)
                    print(f"📊 Limited search result:")
                    print(result.content[0].text[:500] + "...")
                
                # Test 5: Search system indices
                print("\n🔍 Test 5: Search system indices...")
                search_params = {
                    "opensearch_cluster_name": "remote-production",
                    "index": ".opensearch*",
                    "query": {
                        "query": {
                            "match_all": {}
                        }
                    }
                }
                
                if "SearchIndexTool" in available_tools:
                    try:
                        result = await session.call_tool("SearchIndexTool", search_params)
                        print(f"📊 System indices result:")
                        print(result.content[0].text[:300] + "...")
                    except Exception as e:
                        print(f"⚠️ System indices search failed: {e}")
                
                # Test 6: Search with range query
                print("\n🔍 Test 6: Search with range query...")
                search_params = {
                    "opensearch_cluster_name": "remote-production",
                    "index": "_all",
                    "query": {
                        "bool": {
                            "must": [
                                {"match_all": {}}
                            ],
                            "filter": [
                                {
                                    "range": {
                                        "@timestamp": {
                                            "gte": "now-1d"
                                        }
                                    }
                                }
                            ]
                        }
                    }
                }
                
                if "SearchIndexTool" in available_tools:
                    try:
                        result = await session.call_tool("SearchIndexTool", search_params)
                        print(f"📊 Range query result:")
                        print(result.content[0].text[:300] + "...")
                    except Exception as e:
                        print(f"⚠️ Range query failed: {e}")
                
                print("\n🎉 SearchIndexTool testing completed successfully!")
                
    except Exception as e:
        print(f"❌ Error testing SearchIndexTool: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Starting SearchIndexTool Live Test")
    print("📝 Prerequisites:")
    print("   1. MCP Server running on http://localhost:9900")
    print("   2. OpenSearch running on https://192.168.50.68:8000")
    print("   3. Virtual environment activated")
    print()
    
    asyncio.run(test_search_index_tool())