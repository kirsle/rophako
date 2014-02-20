# -*- coding: utf-8 -*-

from flask import g, session, request, render_template
from functools import wraps
import uuid

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
    return html


def generate_csrf_token():
    """Generator for CSRF tokens."""
    if "_csrf" not in session:
        session["_csrf"] = str(uuid.uuid4())
    return session["_csrf"]