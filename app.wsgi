#!/usr/bin/env python

"""WSGI runner script for the Rophako CMS."""

import sys
import os

# Add the CWD to the path.
sys.path.append(".")

# Use the 'rophako' virtualenv.
activate_this = os.environ['HOME']+'/.virtualenv/rophako/bin/activate_this.py'
execfile(activate_this, dict(__file__=activate_this))

from rophako import app as application

# vim:ft=python
