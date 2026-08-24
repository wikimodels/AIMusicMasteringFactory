#!/usr/bin/env python3
"""
Audio Similarity Server — single entry point, detailed logging.
"""

import os
import sys
import logging
from pathlib import Path

# --- Setup logging FIRST ---
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("server.log", encoding="utf-8", mode="w"),
    ],
)
logger = logging.getLogger("server")

# Reduce noise from libs
logging.getLogger("werkzeug").setLevel(logging.INFO)
logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Ensure we're in the right directory ---
ROOT = Path(__file__).parent.resolve()
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

logger.info("=" * 60)
logger.info("SERVER STARTUP")
logger.info("=" * 60)
logger.info(f"Working directory: {ROOT}")
logger.info(f"Python: {sys.executable}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Audio Similarity Dashboard Server")
    parser.add_argument("--port", type=int, default=5050, help="Port to run on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    # Check dependencies with detailed logging
    logger.info("Checking dependencies...")
    try:
        import flask
        logger.debug(f"  flask: {flask.__version__}")
        import librosa
        logger.debug(f"  librosa: {librosa.__version__}")
        import numpy
        logger.debug(f"  numpy: {numpy.__version__}")
        import pandas
        logger.debug(f"  pandas: {pandas.__version__}")
        import yaml
        logger.debug(f"  yaml: OK")
        import tqdm
        logger.debug(f"  tqdm: {tqdm.__version__}")
        import flask_cors
        logger.debug(f"  flask_cors: OK")
    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Run: poetry install (from project root)")
        sys.exit(1)

    # Import dashboard
    logger.info("Importing dashboard module...")
    from dashboard import app
    logger.info("Dashboard imported successfully")

    import webbrowser
    import threading
    import time

    url = f"http://127.0.0.1:{args.port}"

    def open_browser():
        time.sleep(1.5)
        logger.info(f"Opening browser: {url}")
        webbrowser.open(url)

    if not args.no_browser:
        threading.Thread(target=open_browser, daemon=True).start()

    logger.info(f"Starting Flask on {args.host}:{args.port}")
    logger.info(f"Dashboard URL: {url}")
    logger.info("Press Ctrl+C to stop")

    try:
        app.run(host=args.host, port=args.port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    except Exception as e:
        logger.exception(f"Server crashed: {e}")
        sys.exit(1)
    finally:
        logger.info("Server stopped")

if __name__ == "__main__":
    main()