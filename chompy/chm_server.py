#!/usr/bin/env python3
"""
Modern CHM file server - serves CHM files via HTTP without Symbian dependencies
"""

import argparse
import sys
import os
import time
import signal
from server import start, stop


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\nShutting down CHM server...")
    stop()
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Serve CHM files via HTTP")
    parser.add_argument("chm_file", help="Path to CHM file to serve")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8081, help="Port to bind to (default: 8081)"
    )
    parser.add_argument("--timeout", type=int, help="Auto-shutdown timeout in seconds")

    args = parser.parse_args()

    # Check if CHM file exists
    if not os.path.exists(args.chm_file):
        print(f"Error: CHM file '{args.chm_file}' not found")
        sys.exit(1)

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Update global host/port if specified
    import server

    server.HOST = args.host
    server.PORT = args.port

    try:
        print(f"Starting CHM server for: {args.chm_file}")
        print(f"Server will be available at: http://{args.host}:{args.port}/")

        server_instance = start(args.chm_file)

        if args.timeout:
            print(f"Server will auto-shutdown in {args.timeout} seconds")
            time.sleep(args.timeout)
            print("Timeout reached, shutting down...")
            stop()
        else:
            print("Press Ctrl+C to stop the server")
            # Keep the main thread alive
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
