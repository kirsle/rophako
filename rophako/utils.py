# -*- coding: utf-8 -*-

from flask import g, session, request, render_template, flash, redirect, url_for
from functools import wraps
import codecs
import uuid
import datetime
import time
import re
import importlib
import smtplib
import markdown

from rophako.log import logger
from config import *


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


def markdown_template(path):
    """Render a Markdown page to the browser."""

    # The path is the absolute path to the Markdown file, so open it directly.
    fh = codecs.open(path, "r", "utf-8")
    body = fh.read()
    fh.close()

    # Extract a title from the first line.
    first = body.split("\n")[0]
    if first.startswith("#"):
        first = first[1:].strip()

    rendered = render_markdown(body)
    return template("markdown.inc.html",
        title=first,
        markdown=rendered,
    )


def render_markdown(body, html_escape=True):
    """Render a block of Markdown text.

    This will default to escaping literal HTML characters. Set
    `html_escape=False` to trust HTML."""

    args = dict(
        lazy_ol=False, # If a numbered list starts at e.g. 4, show the <ol> there
        extensions=[
            "fenced_code",  # GitHub style code blocks
            "tables",       # http://michelf.ca/projects/php-markdown/extra/#table
            "smart_strong", # Handles double__underscore better.
            "codehilite",   # Code highlighting with Pygment!
            "nl2br",        # Line breaks inside a paragraph become <br>
            "sane_lists",   # Make lists less surprising
        ],
        extension_configs={
            "codehilite": {
                "linenums": False,
            }
        }
    )
    if html_escape:
        args["safe_mode"] = "escape"

    return markdown.markdown(body, **args)


def send_email(to, subject, message, sender=None):
    """Send an e-mail out."""
    if sender is None:
        sender = MAIL_SENDER

    if type(to) != list:
        to = [to]

    logger.info("Send email to {}".format(to))
    if MAIL_METHOD == "smtp":
        # Send mail with SMTP.
        for email in to:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            server.set_debuglevel(1)
            msg = """From: {}
To: {}
Subject: {}

{}""".format(sender, email, subject, message)
            server.sendmail(sender, email, msg)
            server.quit()


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
    return re.sub(r'[^A-Za-z0-9 .\-_]+', '', name)