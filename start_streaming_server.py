#!/usr/bin/env python3
"""
OpenSearch MCP Streaming Server Startup Script

This script starts the OpenSearch MCP streaming server with multi-cluster support
using configuration from example_clusters.yml.

Usage:
    python start_streaming_server.py
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    # Set environment variable for SSL verification
    os.environ['OPENSEARCH_SSL_VERIFY'] = 'false'
    
    # Get the directory of this script
    script_dir = Path(__file__).parent.absolute()
    
    # Change to the opensearch_mcp_server_py directory
    os.chdir(script_dir)
    
    # Set up PYTHONPATH
    src_path = script_dir / 'src'
    env = os.environ.copy()
    env['PYTHONPATH'] = str(src_path)
    
    # Prepare the command
    venv_python = script_dir / '.venv' / 'bin' / 'python'
    
    cmd = [
        str(venv_python),
        '-m', 'mcp_server_opensearch',
        '--transport', 'stream',
        '--mode', 'multi',
        '--config', 'example_clusters.yml'
    ]
    
    print("Starting OpenSearch MCP Streaming Server...")
    print(f"Working directory: {script_dir}")
    print(f"OPENSEARCH_SSL_VERIFY: {os.environ.get('OPENSEARCH_SSL_VERIFY')}")
    print(f"PYTHONPATH: {env.get('PYTHONPATH')}")
    print(f"Command: {' '.join(cmd)}")
    print("")
    print("Press Ctrl+C to stop the server")
    
    try:
        # Execute the command
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"Error running server: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Make sure the virtual environment is set up at .venv/")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()