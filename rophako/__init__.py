__version__ = '0.01'

from flask import Flask, g, request, session, render_template, send_file, abort
import jinja2
import os.path
import time

import config
import rophako.utils

app = Flask(__name__,
    static_url_path="/.static",
)
app.DEBUG      = config.DEBUG
app.secret_key = config.SECRET_KEY

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
    jinja2.FileSystemLoader("site/www"),    # Site specific.
    jinja2.FileSystemLoader("rophako/www"), # Default
])

app.jinja_env.globals["csrf_token"] = rophako.utils.generate_csrf_token
app.jinja_env.globals["include_page"] = rophako.utils.include

# Preload the emoticon data.
import rophako.model.emoticons as Emoticons
Emoticons.load_theme()


@app.before_request
def before_request():
    """Called before all requests. Initialize global template variables."""

    # CSRF protection.
    if request.method == "POST":
        token = session.pop("_csrf", None)
        if not token or str(token) != str(request.form.get("token")):
            abort(403)

    # Default template vars.
    g.info = {
        "time": time.time(),
        "app": {
            "name": "Rophako",
            "version": __version__,
            "author": "Noah Petherbridge",
            "photo_url": config.PHOTO_ROOT_PUBLIC,
        },
        "uri": request.path.split("/")[1:],
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
    for root in ["site/www", "rophako/www"]:
        abspath = os.path.abspath("{}/{}".format(root, path))
        if os.path.isfile(abspath):
            return send_file(abspath)
        elif not "." in path and os.path.isfile(abspath + ".html"):
            return rophako.utils.template(path + ".html")
        elif not "." in path and os.path.isfile(abspath + "/index.html"):
            return rophako.utils.template(path + "/index.html")

    return not_found("404")


@app.route("/")
def index():
    return catchall("index")


@app.errorhandler(404)
def not_found(error):
    return render_template('errors/404.html', **g.info), 404


# Domain specific endpoints.
if config.SITE_NAME == "kirsle.net":
    import rophako.modules.kirsle_legacy