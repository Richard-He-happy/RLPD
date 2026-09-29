import logging
from pathlib import Path


def configure_logging(level: str = "INFO", path: str | Path | None = None) -> logging.Logger:
    logger = logging.getLogger("rlpd")
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(stream)
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(target, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(file_handler)
    return logger
