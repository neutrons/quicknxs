import logging
import logging.handlers
import os
import sys


class OriginFormatter(logging.Formatter):
    """Display the source module for root logger records."""

    def format(self, record):
        record.origin = record.module if record.name == "root" else record.name
        return super().format(record)


def setup_logging():
    log_level = os.environ.get("QUICKNXS_LOGLEVEL", "INFO").upper()
    if log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        log_level = "INFO"

    logging.getLogger().setLevel(log_level)

    # Shorten level names to 4 characters for better log formatting
    logging.addLevelName(logging.DEBUG, "DBUG")
    logging.addLevelName(logging.INFO, "INFO")
    logging.addLevelName(logging.WARNING, "WARN")
    logging.addLevelName(logging.ERROR, "ERR")
    logging.addLevelName(logging.CRITICAL, "CRIT")

    _fmt = "%(asctime)s | %(levelname)-4s | %(origin)-12s | %(message)s"
    _date_fmt = "%Y-%m-%d %H:%M:%S"
    LOG_FMT = OriginFormatter(fmt=_fmt, datefmt=_date_fmt)

    # Setup timed rotating file handler
    fh = logging.handlers.TimedRotatingFileHandler(
        os.path.join(os.path.expanduser("~"), "quicknxs.log"), when="midnight", backupCount=15
    )
    fh.setLevel(log_level)
    fh.setFormatter(LOG_FMT)
    logging.getLogger().addHandler(fh)

    # Setup stream handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(log_level)
    sh.setFormatter(LOG_FMT)
    logging.getLogger().addHandler(sh)
