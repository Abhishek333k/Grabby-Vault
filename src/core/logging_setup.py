"""Application logging and crash hooks."""
from __future__ import annotations

import logging
import sys
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler

from core.paths import logs_dir


_configured = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    global _configured
    logger = logging.getLogger("grabbyvault")
    if _configured:
        return logger

    log_dir = logs_dir()
    log_file = f"{log_dir}/grabbyvault.log"

    logger.setLevel(level)
    logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.setLevel(level)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(level)
    logger.addHandler(sh)

    def _excepthook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        logger.critical(
            "Unhandled exception:\n%s",
            "".join(traceback.format_exception(exc_type, exc, tb)),
        )
        crash_path = f"{log_dir}/crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        try:
            with open(crash_path, "w", encoding="utf-8") as f:
                f.write("".join(traceback.format_exception(exc_type, exc, tb)))
        except OSError:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook
    _configured = True
    logger.info("Logging initialized → %s", log_file)
    return logger


def get_logger(name: str = "grabbyvault") -> logging.Logger:
    if not _configured:
        return setup_logging()
    return logging.getLogger(name)
