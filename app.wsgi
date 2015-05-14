#!/usr/bin/env python

"""WSGI runner script for the Rophako CMS."""

import sys
import os

# Add the CWD to the path.
sys.path.append(".")

# Use the 'rophako' virtualenv.
activate_this = os.environ['HOME']+'/.virtualenv/rophako/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

def application(environ, start_response):
    if "ROPHAKO_SETTINGS" in environ:
        os.environ["ROPHAKO_SETTINGS"] = environ["ROPHAKO_SETTINGS"]
    from rophako.app import app as _application
    return _application(environ, start_response)

# vim:ft=python
