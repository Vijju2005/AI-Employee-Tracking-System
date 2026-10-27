"""
EBT System — Production WSGI Entry Point (Waitress for Windows)
Usage:
    python wsgi_prod.py

Or from command line:
    waitress-serve --host=0.0.0.0 --port=5000 run:app
"""

import os
import logging
from waitress import serve
from app import create_app
from config import ProductionConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("waitress")

# Initialize production application
app = create_app(ProductionConfig)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))
    threads = int(os.environ.get("WAITRESS_THREADS", 6))

    logger.info("Starting EBT System on Waitress WSGI server (http://%s:%s) with %s threads...", host, port, threads)
    serve(
        app,
        host=host,
        port=port,
        threads=threads,
        channel_timeout=30,
        cleanup_interval=30
    )
