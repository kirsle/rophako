# -*- coding: utf-8 -*-

from flask import g, session, request, render_template, flash, redirect, url_for
from functools import wraps
import uuid
import datetime
import time
import re
import importlib

from rophako.log import logger


def login_required(f):
    """Wrapper for pages that require a logged-in user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.info["session"]["login"]:
            session["redirect_url"] = request.url
            flash("You must be logged in to do that!")
            return redirect(url_for("account.login"))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Wrapper for admin-only pages. Implies login_required."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.info["session"]["login"]:
            # Not even logged in?
            session["redirect_url"] = request.url
            flash("You must be logged in to do that!")
            return redirect(url_for("account.login"))

        if g.info["session"]["role"] != "admin":
            logger.warning("User tried to access an Admin page, but wasn't allowed!")
            return redirect(url_for("index"))

        return f(*args, **kwargs)
    return decorated_function


def template(name, **kwargs):
    """Render a template to the browser."""

    html = render_template(name, **kwargs)

    # Get the elapsed time for the request.
    time_elapsed = "%.03f" % (time.time() - g.info["time"])
    html = re.sub(r'\%time_elapsed\%', time_elapsed, html)
    return html


def generate_csrf_token():
    """Generator for CSRF tokens."""
    if "_csrf" not in session:
        session["_csrf"] = str(uuid.uuid4())
    return session["_csrf"]


def include(endpoint, *args, **kwargs):
    """Include another sub-page inside a template."""

    # The 'endpoint' should be in the format 'module.function', i.e. 'blog.index'.
    module, function = endpoint.split(".")

    # Dynamically import the module and call its function.
    m    = importlib.import_module("rophako.modules.{}".format(module))
    html = getattr(m, function)(*args, **kwargs)

    return html


def pretty_time(time_format, unix):
    """Pretty-print a time stamp."""
    date = datetime.datetime.fromtimestamp(unix)
    return date.strftime(time_format)


def sanitize_name(name):
    """Sanitize a name that may be used in the filesystem.

    Only allows numbers, letters, and some symbols."""
    return re.sub(r'[^A-Za-z0-9 .-_]+', '', name)