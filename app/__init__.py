import logging
from pathlib import Path

from flask import Flask

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
LOG_LEVEL = logging.INFO


def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
    root_logger.setLevel(LOG_LEVEL)


def create_app() -> Flask:
    """Application factory for the SA2 chokepoint analysis tool."""
    _configure_logging()

    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )

    # Late import to avoid circulars
    from .routes import bp as main_bp

    app.register_blueprint(main_bp)

    return app


