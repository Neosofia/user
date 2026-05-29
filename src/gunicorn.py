from logenvelope.gunicorn import JSONLogger

from src.bootstrap.config import settings

# --- Gunicorn Configuration ---
bind = f"0.0.0.0:{settings.port}"
workers = settings.web_concurrency
threads = settings.gunicorn_threads
timeout = settings.gunicorn_timeout
keepalive = settings.gunicorn_keepalive
preload_app = True
accesslog = "-"
errorlog = "/dev/stdout"
loglevel = settings.log_level
logger_class = JSONLogger
