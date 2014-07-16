__version__ = '0.01'

from flask import Flask, g, request, session, render_template, send_file, abort
from flask_sslify import SSLify
import jinja2
import os.path
import time
import sys

import config
import rophako.utils

app = Flask(__name__,
    static_url_path="/.static",
)
app.DEBUG      = config.DEBUG
app.secret_key = config.SECRET_KEY

# Security?
if config.FORCE_SSL:
    app.config['SESSION_COOKIE_SECURE'] = True
    sslify = SSLify(app)

# Load all the blueprints!
from rophako.modules.admin import mod as AdminModule
from rophako.modules.account import mod as AccountModule
from rophako.modules.blog import mod as BlogModule
from rophako.modules.photo import mod as PhotoModule
from rophako.modules.comment import mod as CommentModule
from rophako.modules.emoticons import mod as EmoticonsModule
from rophako.modules.contact import mod as ContactModule
app.register_blueprint(AdminModule)
app.register_blueprint(AccountModule)
app.register_blueprint(BlogModule)
app.register_blueprint(PhotoModule)
app.register_blueprint(CommentModule)
app.register_blueprint(EmoticonsModule)
app.register_blueprint(ContactModule)

# Custom Jinja handler to support custom- and default-template folders for
# rendering templates.
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(config.SITE_ROOT), # Site specific.
    jinja2.FileSystemLoader("rophako/www"),    # Default/fall-back
])

app.jinja_env.globals["csrf_token"] = rophako.utils.generate_csrf_token
app.jinja_env.globals["include_page"] = rophako.utils.include

# Preload the emoticon data.
import rophako.model.emoticons as Emoticons
Emoticons.load_theme()


@app.before_request
def before_request():
    """Called before all requests. Initialize global template variables."""

    # Default template vars.
    g.info = {
        "time": time.time(),
        "app": {
            "name": "Rophako",
            "version": __version__,
            "python_version": "{}.{}".format(sys.version_info.major, sys.version_info.minor),
            "author": "Noah Petherbridge",
            "photo_url": config.PHOTO_ROOT_PUBLIC,
        },
        "uri": request.path,
        "session": {
            "login": False, # Not logged in, until proven otherwise.
            "username": "guest",
            "uid": 0,
            "name": "Guest",
            "role": "user",
        }
    }

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

    # Search for this file.
    for root in [config.SITE_ROOT, "rophako/www"]:
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


@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html', **g.info), 404


@app.errorhandler(403)
def forbidden(error):
    return render_template('errors/403.html', **g.info), 403


# Domain specific endpoints.
if config.SITE_NAME == "kirsle.net":
    import rophako.modules.kirsle_legacy
