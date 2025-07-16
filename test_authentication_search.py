#!/usr/bin/env python3
"""
Test SearchIndexTool to find authentication events in agent-alerts-000001
"""

import asyncio
import json
import sys
import os

# Add src to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from mcp.client.streamable_http import streamablehttp_client
from mcp.client.session import ClientSession


async def test_authentication_events():
    """Test SearchIndexTool to find authentication events."""
    
    print("🔍 Testing SearchIndexTool for authentication events...")
    print("📋 Target: agent-alerts-000001 index")
    print("📋 Query: event.category = authentication")
    print()
    
    try:
        # Connect to MCP Server
        async with streamablehttp_client("http://localhost:9900/mcp") as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                print("✅ Connected to MCP Server")
                
                # Initialize the session
                await session.initialize()
                print("✅ Session initialized")
                
                # List available tools
                tools_response = await session.list_tools()
                available_tools = [tool.name for tool in tools_response.tools]
                print(f"✅ Available tools: {available_tools}")
                
                if "SearchIndexTool" not in available_tools:
                    print("❌ SearchIndexTool not available")
                    return
                
                # Test 1: Check if agent-alerts-000001 index exists
                print("\n🔍 Step 1: Check if agent-alerts-000001 index exists...")
                if "ListIndexTool" in available_tools:
                    result = await session.call_tool("ListIndexTool", {})
                    indices_text = result.content[0].text
                    if "agent-alerts-000001" in indices_text:
                        print("✅ agent-alerts-000001 index found")
                    else:
                        print("⚠️ agent-alerts-000001 index not found")
                        print("📋 Available indices:")
                        print(indices_text[:500] + "...")
                
                # Test 2: Search for authentication events
                print("\n🔍 Step 2: Search for authentication events...")
                search_params = {
                    "index": "agent-alerts-000001",
                    "query": {
                        "match": {
                            "event.category": "authentication"
                        }
                    }
                }
                
                try:
                    result = await session.call_tool("SearchIndexTool", search_params)
                    print("✅ Authentication events search completed")
                    print("📊 Search result:")
                    print(result.content[0].text[:1000] + "...")
                    
                    # Parse the result to count hits
                    result_text = result.content[0].text
                    if "Search results from" in result_text:
                        json_part = result_text.split("Search results from agent-alerts-000001:\n")[1]
                        try:
                            parsed_result = json.loads(json_part)
                            total_hits = parsed_result.get("hits", {}).get("total", {})
                            if isinstance(total_hits, dict):
                                count = total_hits.get("value", 0)
                            else:
                                count = total_hits
                            print(f"📊 Total authentication events found: {count}")
                        except:
                            print("📊 Could not parse hit count")
                    
                except Exception as e:
                    print(f"❌ Authentication events search failed: {e}")
                
                # Test 3: Try alternative search patterns
                print("\n🔍 Step 3: Alternative search patterns...")
                
                alternative_searches = [
                    {
                        "name": "Exact match (keyword)",
                        "query": {
                            "term": {
                                "event.category.keyword": "authentication"
                            }
                        }
                    },
                    {
                        "name": "Wildcard search",
                        "query": {
                            "wildcard": {
                                "event.category": "*auth*"
                            }
                        }
                    },
                    {
                        "name": "Match with size limit",
                        "query": {
                            "match": {
                                "event.category": "authentication"
                            }
                        },
                        "size": 5
                    }
                ]
                
                for search in alternative_searches:
                    try:
                        print(f"\n   Testing: {search['name']}")
                        search_params = {
                            "index": "agent-alerts-000001",
                            "query": search["query"]
                        }
                        if "size" in search:
                            search_params["size"] = search["size"]
                        
                        result = await session.call_tool("SearchIndexTool", search_params)
                        print(f"   ✅ {search['name']} completed")
                        print(f"   📊 Result: {result.content[0].text[:300]}...")
                        
                    except Exception as e:
                        print(f"   ❌ {search['name']} failed: {e}")
                
                # Test 4: Search all event categories to see what's available
                print("\n🔍 Step 4: Search all event categories...")
                try:
                    search_params = {
                        "index": "agent-alerts-000001",
                        "query": {
                            "match_all": {}
                        },
                        "size": 10
                    }
                    
                    result = await session.call_tool("SearchIndexTool", search_params)
                    print("✅ Sample events search completed")
                    print("📊 Sample events to check available fields:")
                    print(result.content[0].text[:800] + "...")
                    
                except Exception as e:
                    print(f"❌ Sample events search failed: {e}")
                
                # Test 5: Get index mapping to understand structure
                print("\n🔍 Step 5: Get index mapping...")
                if "IndexMappingTool" in available_tools:
                    try:
                        result = await session.call_tool("IndexMappingTool", {
                            "index": "agent-alerts-000001"
                        })
                        print("✅ Index mapping retrieved")
                        print("📊 Index mapping:")
                        print(result.content[0].text[:500] + "...")
                    except Exception as e:
                        print(f"❌ Index mapping failed: {e}")
                
                print("\n🎉 Authentication events testing completed!")
                
    except Exception as e:
        print(f"❌ Error testing authentication events: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Starting Authentication Events Test")
    print("📝 Prerequisites:")
    print("   1. MCP Server running on http://localhost:9900")
    print("   2. OpenSearch running on http://localhost:9200")
    print("   3. agent-alerts-000001 index exists with data")
    print("   4. Virtual environment activated")
    print()
    
    asyncio.run(test_authentication_events())