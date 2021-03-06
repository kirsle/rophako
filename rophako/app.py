#!/usr/bin/env python
from __future__ import unicode_literals, absolute_import

"""Flask app for Rophako."""

from flask import (Flask, g, request, session, render_template, send_file,
    abort, redirect)
from flask_sslify import SSLify
from flask_compress import Compress
import jinja2
import os.path
import datetime
import sys

# Get the Flask app object ready right away so other modules can import it
# without getting a circular import error.
app = Flask(__name__,
    static_url_path="/.static",
)
Compress(app)

# We use a custom Jinja loader to support multiple template paths for custom
# and default templates. The base list of template paths to check includes
# your custom path (from config.SITE_ROOT), the "rophako/www" path for normal
# pages, and then the blueprint paths for all imported plugins. This list will
# be extended while blueprints are being loaded and passed in below to the
# jinja2.ChoiceLoader.
BLUEPRINT_PATHS = []

from rophako.settings import Config
Config.load_settings()
Config.load_plugins()

from rophako.plugin import load_plugin
from rophako.log import logger
#import rophako.model.tracking as Tracking
import rophako.utils

# String escaping for the secret key (processes \ escapes properly), the
# escape encoding name varies between Python 2 and 3.
string_escape = "string_escape" if sys.version_info[0] == 2 \
                else "unicode_escape"

app.DEBUG      = Config.site.debug == "true"
app.secret_key = bytes(Config.security.secret_key.encode("utf-8")) \
                 .decode(string_escape)

# Make templates easier to edit live.
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Security?
if Config.security.force_ssl == True:
    app.config['SESSION_COOKIE_SECURE'] = True
    sslify = SSLify(app)

# Load all the built-in essential plugins.
load_plugin("rophako.modules.admin")
load_plugin("rophako.modules.account")

# Custom Jinja handler to support custom- and default-template folders for
# rendering templates.
template_paths = [
   Config.site.site_root, # Site specific.
   "rophako/www",         # Default/fall-back
]
template_paths.extend(BLUEPRINT_PATHS)
app.jinja_loader = jinja2.ChoiceLoader([ jinja2.FileSystemLoader(x) for x in template_paths])

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.jinja_env.globals["csrf_token"] = rophako.utils.generate_csrf_token
app.jinja_env.globals["include_page"] = rophako.utils.include
app.jinja_env.globals["settings"] = lambda: Config
app.jinja_env.globals["strftime"] = lambda x: datetime.datetime.utcnow().strftime(x)

# Preload the emoticon data.
import rophako.model.emoticons as Emoticons
Emoticons.load_theme()


@app.before_request
def before_request():
    """Called before all requests. Initialize global template variables."""

    # Session lifetime.
    app.permanent_session_lifetime = datetime.timedelta(days=Config.security.session_lifetime)
    session.permanent = True

    # Default template vars.
    g.info = rophako.utils.default_vars()

    # Default session vars.
    if not "login" in session:
        session.update(g.info["session"])

    # CSRF protection.
    if request.method == "POST":
        token = session.pop("_csrf", None)
        if not token or str(token) != str(request.form.get("token")):
            abort(403)

    # Refresh their login status from the DB.
    if session["login"]:
        import rophako.model.user as User
        if not User.exists(uid=session["uid"]):
            # Weird! Log them out.
            from rophako.modules.account import logout
            logout()
            return

        db = User.get_user(uid=session["uid"])
        session["username"] = db["username"]
        session["name"]     = db["name"]
        session["role"]     = db["role"]

    # Copy session params into g.info. The only people who should touch the
    # session are the login/out pages.
    for key in session:
        g.info["session"][key] = session[key]


@app.context_processor
def after_request():
    """Called just before render_template. Inject g.info into the template vars."""
    return g.info


@app.route("/<path:path>")
def catchall(path):
    """The catch-all path handler. If it exists in the www folders, it's sent,
    otherwise we give the 404 error page."""

    if path.endswith("/"):
        path = path.strip("/") # Remove trailing slashes.
        return redirect(path)

    # Search for this file.
    for root in [Config.site.site_root, "rophako/www"]:
        abspath = os.path.abspath("{}/{}".format(root, path))
        if os.path.isfile(abspath):
            return send_file(abspath)

        # The exact file wasn't found, look for some extensions and index pages.
        suffixes = [
            ".html",
            "/index.html",
            ".md",         # Markdown formatted pages.
            "/index.md",
        ]
        for suffix in suffixes:
            if not "." in path and os.path.isfile(abspath + suffix):
                # HTML, or Markdown?
                if suffix.endswith(".html"):
                    return rophako.utils.template(path + suffix)
                else:
                    return rophako.utils.markdown_template(abspath + suffix)

    return not_found("404")


@app.route("/")
def index():
    return catchall("index")


@app.errorhandler(Exception)
def catch_exception(error):
    """Catch unexpected Python exceptions and e-mail them out."""
    logger.error("INTERNAL SERVER ERROR: {}".format(str(error)))

    # E-mail it out.
    rophako.utils.handle_exception(error)
    return rophako.utils.template("errors/500.html")


@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html', **g.info), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html', **g.info), 403
