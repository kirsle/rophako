# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function, absolute_import

from flask import (g, session, request, render_template, flash, redirect,
    url_for, current_app)
from functools import wraps
import codecs
import uuid
import datetime
import time
import pytz
import re
import importlib
import smtplib
import markdown
import json
import sys
try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from rophako import __version__
from rophako.log import logger
from rophako.settings import Config


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


def ajax_response(status, msg):
    """Return a standard JSON response."""
    status = "ok" if status else "error"
    return json.dumps(dict(
        status=status,
        msg=msg,
    ))


def default_vars():
    """Default template variables."""
    return {
        "time": time.time(),
        "app": {
            "name": "Rophako",
            "version": __version__,
            "python_version": "{}.{}".format(sys.version_info.major, sys.version_info.minor),
            "author": "Noah Petherbridge",
            "photo_url": Config.photo.root_public,
            "config": Config,
        },
        "uri": request.path,
        "session": {
            "login": False, # Not logged in, until proven otherwise.
            "username": "guest",
            "uid": 0,
            "name": "Guest",
            "role": "user",
        },
        #"tracking": Tracking.track_visit(request, session),
    }


def template(name, **kwargs):
    """Render a template to the browser."""

    html = render_template(name, **kwargs)

    # Get the elapsed time for the request.
    time_elapsed = "%.03f" % (time.time() - g.info["time"])
    html = re.sub(r'\%time_elapsed\%', time_elapsed, html)
    return html


def markdown_template(path):
    """Render a Markdown page to the browser.

    The first line in the Markdown page should be an H1 header beginning with
    the # sign. This will set the page's <title> to match the header value.

    Pages can include lines that begin with the keyword `:meta` to apply
    meta information to control the Markdown parser. Supported meta lines
    and examples:

    To 'blacklist' extensions, i.e. to turn off line breaks inside a paragraph
    getting translated into a <br> tag (the key is the minus sign):
    :meta extensions -nl2br

    To add an extension, i.e. the abbreviations from PHP Markdown Extra:
    :meta extensions abbr"""

    # The path is the absolute path to the Markdown file, so open it directly.
    fh = codecs.open(path, "r", "utf-8")
    body = fh.read()
    fh.close()

    # Look for meta information in the file.
    lines      = body.split("\n")
    content    = list() # New set of lines, without meta info.
    extensions = set()
    blacklist  = set() # Blacklisted extensions
    toc        = False # Render a table of contents
    for line in lines:
        if line.startswith(":meta"):
            parts = line.split(" ")
            if len(parts) >= 3:
                # Supported meta commands.
                if parts[1] == "extensions":
                    # Extension toggles.
                    for extension in parts[2:]:
                        if extension.startswith("-"):
                            extension = extension[1:]
                            blacklist.add(extension)
                        else:
                            extensions.add(extension)
                elif parts[1] == "toc":
                    # Table of contents.
                    toc = parts[2] == "on"
        else:
            content.append(line)

    # Extract a title from the first line.
    first = content[0]
    if first.startswith("#"):
        first = first[1:].strip()

    rendered = render_markdown("\n".join(content),
        extensions=extensions,
        blacklist=blacklist,
    )

    # Including a table of contents?
    nav = None
    if toc:
        nav = parse_anchors(rendered)

    return template("markdown.inc.html",
        title=first,
        markdown=rendered,
        toc=nav,
    )


def render_markdown(body, html_escape=True, extensions=None, blacklist=None):
    """Render a block of Markdown text.

    This will default to escaping literal HTML characters. Set
    `html_escape=False` to trust HTML.

    * extensions should be a set() of extensions to add.
    * blacklist should be a set() of extensions to blacklist."""

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

    # Additional extensions?
    if extensions is not None:
        for ext in extensions:
            args["extensions"].append(ext)
    if blacklist is not None:
        for ext in blacklist:
            args["extensions"].remove(str(ext))

    return u'<div class="markdown">{}</div>'.format(
        markdown.markdown(body, **args)
    )


def parse_anchors(html):
    """Parse HTML code and identify anchor tags for Table of Contents.

    Args:
        * str html: HTML code generated by `render_markdown()`

    Returns:
        * list of dicts containing the parsed table of contents, with keys
          including `id`, `level` (<h1> level as int) and `text`
    """
    toc = []

    regexp = re.compile(r'<h(\d) id="(.+?)">(.+?)</h\d>')
    for match in re.findall(regexp, html):
        toc.append(dict(
            id=match[1],
            level=int(match[0]),
            text=match[2],
        ))

    return toc


def send_email(to, subject, message, header=None, footer=None, sender=None,
               reply_to=None):
    """Send a (markdown-formatted) e-mail out.

    This will deliver an HTML-formatted e-mail (using the ``email.inc.html``
    template) using the rendered Markdown contents of ``message`` and
    ``footer``. It will also send a plain text version using the raw Markdown
    formatting in case the user can't accept HTML.

    Parameters:
        to ([]str): list of addresses to send the message to.
        subject (str): email subject and title.
        message (str): the email body, in Markdown format.
        header (str): the header text for the HTML email (plain text).
        footer (str): optional email footer, in Markdown format. The default
            footer is defined in the ``email.inc.html`` template.
        sender (str): optional sender email address. Defaults to the one
            specified in the site configuration.
        reply_to (str): optional Reply-To address header.
    """
    if sender is None:
        sender = Config.mail.sender

    if type(to) != list:
        to = [to]

    # Render the Markdown bits.
    if footer:
        footer = render_markdown(footer)

    # Default header matches the subject.
    if not header:
        header = subject

    html_message = render_template("email.inc.html",
        title=subject,
        header=header,
        message=render_markdown(message),
        footer=footer,
    )

    logger.info("Send email to {}".format(to))
    if Config.mail.method == "smtp":
        # Send mail with SMTP.
        for email in to:
            msg = MIMEMultipart("alternative")
            msg.set_charset("utf-8")

            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = email
            if reply_to is not None:
                msg["Reply-To"] = reply_to

            text = MIMEText(message, "plain", "utf-8")
            msg.attach(text)

            html = MIMEText(html_message, "html", "utf-8")
            msg.attach(html)

            # Send the e-mail.
            try:
                server = smtplib.SMTP(Config.mail.server, Config.mail.port)
                server.sendmail(sender, [email], msg.as_string())
            except:
                pass


def handle_exception(error):
    """Send an e-mail to the site admin when an exception occurs."""
    if current_app.config.get("DEBUG"):
        print(traceback.format_exc())
        raise

    import rophako.jsondb as JsonDB

    # Don't spam too many e-mails in a short time frame.
    cache = JsonDB.get_cache("exception_catcher")
    if cache:
        last_exception = int(cache)
        if int(time.time()) - last_exception < 120:
            # Only one e-mail per 2 minutes, minimum
            logger.error("RAPID EXCEPTIONS, DROPPING")
            return
    JsonDB.set_cache("exception_catcher", int(time.time()))

    username = "anonymous"
    try:
        if hasattr(g, "info") and "session" in g.info and "username" in g.info["session"]:
            username = g.info["session"]["username"]
    except:
        pass

    # Get the timestamp.
    timestamp = time.ctime(time.time())

    # Exception's traceback.
    error = str(error.__class__.__name__) + ": " + str(error)
    stacktrace = error + "\n\n" \
        + "==== Start Traceback ====\n" \
        + traceback.format_exc() \
        + "==== End Traceback ====\n\n" \
        + "Request Information\n" \
        + "-------------------\n" \
        + "Address: " + remote_addr() + "\n" \
        + "User Agent: " + request.user_agent.string + "\n" \
        + "Referrer: " + request.referrer

    # Construct the subject and message
    subject = "Internal Server Error on {} - {} - {}".format(
        Config.site.site_name,
        username,
        timestamp,
    )
    message = "{} has experienced an exception on the route: {}".format(
        username,
        request.path,
    )
    message += "\n\n" + stacktrace

    # Send the e-mail.
    send_email(
        to=Config.site.notify_address,
        subject=subject,
        message=message,
    )


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


def remote_addr():
    """Retrieve the end user's remote IP address. If the site is configured
    to honor X-Forwarded-For and this header is present, it's returned."""
    if Config.security.use_forwarded_for:
        return request.access_route[0]
    return request.remote_addr


def server_name():
    """Get the server's hostname."""
    urlparts = list(urlparse.urlparse(request.url_root))
    return urlparts[1]


def pretty_time(time_format, unix):
    """Pretty-print a time stamp."""
    tz   = pytz.timezone(Config.site.timezone)
    date = datetime.datetime.fromtimestamp(unix, pytz.utc)
    return date.astimezone(tz).strftime(time_format)


def sanitize_name(name):
    """Sanitize a name that may be used in the filesystem.

    Only allows numbers, letters, and some symbols."""
    return re.sub(r'[^A-Za-z0-9 .\-_]+', '', name)
