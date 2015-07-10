# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

"""Debug and logging functions."""

import logging

from rophako.settings import Config

class LogHandler(logging.Handler):
    """A custom logging handler."""

    def emit(self, record):
        # The initial log line, which has the $prefix$ in it.
        line = self.format(record)

        line = line.replace('$prefix$', '')
        print(line)

# Set up the logger.
logger = logging.getLogger("rophako")
handler = LogHandler()
handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] $prefix$%(message)s"))
logger.addHandler(handler)

# Log level.
if Config.site.debug == "true":
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
