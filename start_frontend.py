#!/usr/bin/env python
"""Simple script to launch the API server and open frontend in browser."""

import os
import sys
import time
import webbrowser
import subprocess
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def start_frontend():
    """Start the frontend server and open browser."""
    print("\n" + "=" * 70)
    print("ACME Model Registry - Frontend & API Server")
    print("=" * 70)
    
    print("\n� Starting API Server...")
    print("   Command: uvicorn src.acme_cli.api.main:app --host 0.0.0.0 --port 8000 --reload")
    
    try:
        # Start the uvicorn server
        cmd = [
            sys.executable, "-m", "uvicorn",
            "acme_cli.api.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload"
        ]
        
        process = subprocess.Popen(
            cmd,
            cwd=str(src_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        print("   Waiting for server to start...")
        time.sleep(3)
        
        # Check if server started successfully
        if process.poll() is None:
            print("Server started successfully!")
        else:
            print("Server failed to start")
            return False
        
        # Open browser
        print("\nOpening Frontend in Browser...")
        frontend_url = "http://localhost:8000"
        print(f"   URL: {frontend_url}")
        
        webbrowser.open(frontend_url)
        time.sleep(1)
        
        print("\n" + "=" * 70)
        print("Frontend is Ready!")
        print("=" * 70)
        print("\n Available Pages:")
        print("    Home:          http://localhost:8000/")
        print("    Upload:        http://localhost:8000/upload.html")
        print("    Ingest:        http://localhost:8000/ingest.html")
        print("    License Check: http://localhost:8000/license_check.html")
        print("    Search:        http://localhost:8000/enumerate.html")
        
        print("\n API Documentation:")
        print("    OpenAPI Docs:  http://localhost:8000/docs")
        print("    ReDoc:         http://localhost:8000/redoc")
        
        print("\n Tips:")
        print("    Press Ctrl+C to stop the server")
        print("    Changes to .html/.js files auto-reload (check browser)")
        print("    Check browser Console (F12) for errors")
        print("    Check terminal for API server logs")
        
        print("\n" + "=" * 70)
        print("Server is running... Press Ctrl+C to stop")
        print("=" * 70 + "\n")
        
        # Keep the process running
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
        if process and process.poll() is None:
            process.terminate()
        return True
    except Exception as e:
        print(f"\nError starting server: {e}")
        return False


if __name__ == "__main__":
    success = start_frontend()
    sys.exit(0 if success else 1)
