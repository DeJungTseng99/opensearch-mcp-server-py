#!/usr/bin/env python3
"""
Survey all available MCP tools and their capabilities
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add src to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


async def survey_all_tools():
    """Survey all available MCP tools and test their basic functionality."""
    
    print("🔍 Surveying All MCP Tools")
    print("=" * 50)
    print(f"🕒 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Connect to MCP Server
        async with streamablehttp_client("http://localhost:9900/mcp") as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("✅ Connected to MCP Server")
                
                # Initialize the session
                await session.initialize()
                print("✅ Session initialized")
                
                # Get server info
                print("\n📊 Server Information:")
                print("-" * 30)
                
                # List available tools
                tools_response = await session.list_tools()
                available_tools = tools_response.tools
                
                print(f"📊 Total tools available: {len(available_tools)}")
                print(f"📊 Tool names: {[tool.name for tool in available_tools]}")
                
                # Survey each tool
                for i, tool in enumerate(available_tools, 1):
                    print(f"\n🔧 Tool {i}/{len(available_tools)}: {tool.name}")
                    print("-" * 40)
                    print(f"📝 Description: {tool.description}")
                    print(f"📋 Input Schema: {json.dumps(tool.inputSchema, indent=2)}")
                    
                    # Test each tool based on its type
                    await test_tool_functionality(session, tool)
                    
                    print()
                
                print("\n🎉 All tools survey completed!")
                
    except Exception as e:
        print(f"❌ Error surveying tools: {e}")
        import traceback
        traceback.print_exc()


async def test_tool_functionality(session, tool):
    """Test basic functionality of each tool."""
    
    tool_name = tool.name
    print(f"\n🧪 Testing {tool_name} functionality...")
    
    try:
        # Test based on tool type
        if tool_name == "ListIndexTool":
            await test_list_index_tool(session)
        elif tool_name == "IndexMappingTool":
            await test_index_mapping_tool(session)
        elif tool_name == "SearchIndexTool":
            await test_search_index_tool(session)
        elif tool_name == "GetShardsTool":
            await test_get_shards_tool(session)
        elif tool_name == "ClusterHealthTool":
            await test_cluster_health_tool(session)
        elif tool_name == "CountTool":
            await test_count_tool(session)
        elif tool_name == "ExplainTool":
            await test_explain_tool(session)
        elif tool_name == "MsearchTool":
            await test_msearch_tool(session)
        else:
            print(f"⚠️ Unknown tool type: {tool_name}")
            
    except Exception as e:
        print(f"❌ Error testing {tool_name}: {e}")


async def test_list_index_tool(session):
    """Test ListIndexTool functionality."""
    
    print("   📋 Testing ListIndexTool...")
    
    try:
        # Test 1: List all indices
        result = await session.call_tool("ListIndexTool", {})
        print(f"   ✅ List all indices: Success")
        print(f"   📊 Result preview: {result.content[0].text[:200]}...")
        
        # Test 2: Get specific index info (if we can find an index)
        indices_text = result.content[0].text
        if "agent-alerts-000001" in indices_text:
            specific_result = await session.call_tool("ListIndexTool", {"index": "agent-alerts-000001"})
            print(f"   ✅ Specific index query: Success")
            print(f"   📊 Specific result preview: {specific_result.content[0].text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ ListIndexTool test failed: {e}")


async def test_index_mapping_tool(session):
    """Test IndexMappingTool functionality."""
    
    print("   📋 Testing IndexMappingTool...")
    
    try:
        # Test with common system index
        result = await session.call_tool("IndexMappingTool", {"index": ".opensearch-observability"})
        print(f"   ✅ Index mapping: Success")
        print(f"   📊 Mapping preview: {result.content[0].text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ IndexMappingTool test failed: {e}")


async def test_search_index_tool(session):
    """Test SearchIndexTool functionality."""
    
    print("   📋 Testing SearchIndexTool...")
    
    try:
        # Test 1: Basic match_all query
        result = await session.call_tool("SearchIndexTool", {
            "index": "_all",
            "query": {"match_all": {}}
        })
        print(f"   ✅ Basic search: Success")
        print(f"   📊 Search preview: {result.content[0].text[:200]}...")
        
        # Test 2: Search with size limit
        result = await session.call_tool("SearchIndexTool", {
            "index": "_all",
            "query": {"match_all": {}},
            "size": 1
        })
        print(f"   ✅ Limited search: Success")
        
    except Exception as e:
        print(f"   ❌ SearchIndexTool test failed: {e}")


async def test_get_shards_tool(session):
    """Test GetShardsTool functionality."""
    
    print("   📋 Testing GetShardsTool...")
    
    try:
        # Test with all shards
        result = await session.call_tool("GetShardsTool", {"index": "_all"})
        print(f"   ✅ Get shards: Success")
        print(f"   📊 Shards preview: {result.content[0].text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ GetShardsTool test failed: {e}")


async def test_cluster_health_tool(session):
    """Test ClusterHealthTool functionality."""
    
    print("   📋 Testing ClusterHealthTool...")
    
    try:
        result = await session.call_tool("ClusterHealthTool", {})
        print(f"   ✅ Cluster health: Success")
        print(f"   📊 Health preview: {result.content[0].text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ ClusterHealthTool test failed: {e}")


async def test_count_tool(session):
    """Test CountTool functionality."""
    
    print("   📋 Testing CountTool...")
    
    try:
        result = await session.call_tool("CountTool", {
            "index": "_all",
            "body": {"query": {"match_all": {}}}
        })
        print(f"   ✅ Count documents: Success")
        print(f"   📊 Count preview: {result.content[0].text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ CountTool test failed: {e}")


async def test_explain_tool(session):
    """Test ExplainTool functionality."""
    
    print("   📋 Testing ExplainTool...")
    
    try:
        # This tool requires a specific document ID, which we might not have
        print("   ⚠️ ExplainTool requires specific document ID - skipping detailed test")
        
    except Exception as e:
        print(f"   ❌ ExplainTool test failed: {e}")


async def test_msearch_tool(session):
    """Test MsearchTool functionality."""
    
    print("   📋 Testing MsearchTool...")
    
    try:
        # Multi-search query
        msearch_body = [
            {"index": "_all"},
            {"query": {"match_all": {}}, "size": 1},
            {"index": "_all"},
            {"query": {"match_all": {}}, "size": 1}
        ]
        
        result = await session.call_tool("MsearchTool", {
            "index": "_all",
            "body": msearch_body
        })
        print(f"   ✅ Multi-search: Success")
        print(f"   📊 Multi-search preview: {result.content[0].text[:200]}...")
        
    except Exception as e:
        print(f"   ❌ MsearchTool test failed: {e}")


if __name__ == "__main__":
    print("🚀 Starting MCP Tools Survey")
    print("📝 Prerequisites:")
    print("   1. MCP Server running on http://localhost:9900")
    print("   2. OpenSearch running on http://localhost:9200")
    print("   3. Virtual environment activated")
    print()
    
    asyncio.run(survey_all_tools())