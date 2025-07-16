# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0

from .stdio_server import serve as serve_stdio
from .streaming_server import serve as serve_streaming


def main() -> None:
    """
    Main entry point for the OpenSearch MCP Server.
    Handles command line arguments and starts the appropriate server based on transport type.
    """
    import argparse
    import asyncio
    import logging
    import os
    from pathlib import Path
    
    # Load .env file if it exists
    try:
        from dotenv import load_dotenv
        # Look for .env in current directory, parent directory, and src parent directory
        env_paths = [
            Path.cwd() / '.env',
            Path.cwd().parent / '.env',
            Path(__file__).parent.parent.parent / '.env'
        ]
        
        for env_path in env_paths:
            if env_path.exists():
                load_dotenv(env_path)
                logging.info(f'Loaded environment variables from {env_path}')
                break
        else:
            logging.info('No .env file found, using system environment variables')
    except ImportError:
        logging.warning('python-dotenv not installed, using system environment variables only')

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    logger.info('Starting MCP server...')

    # Set up command line argument parser
    parser = argparse.ArgumentParser(description='OpenSearch MCP Server')
    parser.add_argument(
        '--transport',
        choices=['stdio', 'stream'],
        default='stdio',
        help='Transport type (stdio or stream)',
    )
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (streaming only)')
    parser.add_argument(
        '--port', type=int, default=9900, help='Port to listen on (streaming only)'
    )
    parser.add_argument(
        '--mode',
        choices=['single', 'multi'],
        default='single',
        help='Server mode: single (default) uses environment variables for OpenSearch connection, multi requires explicit connection parameters',
    )
    parser.add_argument(
        '--profile', default='', help='AWS profile to use for OpenSearch connection'
    )
    parser.add_argument('--config', default='', help='Path to a YAML configuration file')

    args = parser.parse_args()

    # Start the appropriate server based on transport type
    if args.transport == 'stdio':
        asyncio.run(serve_stdio(mode=args.mode, profile=args.profile, config=args.config))
    else:
        asyncio.run(
            serve_streaming(
                host=args.host,
                port=args.port,
                mode=args.mode,
                profile=args.profile,
                config=args.config,
            )
        )


if __name__ == '__main__':
    main()
