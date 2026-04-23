from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
import logging
import os

from app.api.v1.router import api_router
from fastapi.middleware.cors import CORSMiddleware

# Configure root logging early so other modules log correctly
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(level=numeric_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Keep third-party network logs quiet by default; enable only when explicitly requested
trace_http = os.getenv("TRACE_HTTP", "false").strip().lower() in {"1", "true", "yes", "on"}
for logger_name in ("httpx", "httpcore", "qdrant_client"):
    logging.getLogger(logger_name).setLevel(logging.DEBUG if trace_http else logging.WARNING)

# Add a rotating file handler to persist logs for requests and diagnostics
try:
    from logging.handlers import RotatingFileHandler

    logs_folder = os.getenv("LOGS_FOLDER", "./logs")
    os.makedirs(logs_folder, exist_ok=True)
    file_path = os.path.join(logs_folder, "app.log")
    file_handler = RotatingFileHandler(file_path, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s]: %(message)s")
    file_handler.setFormatter(file_formatter)

    # Add a filter to avoid KeyError when request_id not provided
    class RequestIdFilter(logging.Filter):
        def filter(self, record):
            if not hasattr(record, "request_id"):
                record.request_id = "-"
            return True

    file_handler.addFilter(RequestIdFilter())
    logging.getLogger().addHandler(file_handler)
except Exception:
    logging.getLogger(__name__).exception("Failed to configure RotatingFileHandler for logs")

logging.getLogger(__name__).info("Application bootstrap initialized")

app = FastAPI(title="AI Sales & Booking Assistant API", version="1.0.0")
# Enable CORS for any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")

# Mount media folder for demo purposes at /media/static
media_folder = "./media"
os.makedirs(media_folder, exist_ok=True)
app.mount("/media/static", StaticFiles(directory=media_folder), name="media")

