# -*- coding: utf-8 -*-

"""Debug and logging functions."""

from flask import g, request
import logging

import config

class LogHandler(logging.Handler):
    """A custom logging handler."""

    def emit(self, record):
        # The initial log line, which has the $prefix$ in it.
        line = self.format(record)

        # Is the user logged in?
        name = "-nobody-"

        line = line.replace('$prefix$', '')
        print line

# Set up the logger.
logger = logging.getLogger("rophako")
handler = LogHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] $prefix$%(message)s"))
logger.addHandler(handler)

# Log level.
if config.DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)