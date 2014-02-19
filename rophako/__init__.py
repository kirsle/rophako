__version__ = '0.01'

from flask import Flask, g, request, session, render_template, send_file
import jinja2
import os.path

import config

app = Flask(__name__)
app.DEBUG      = config.DEBUG
app.SECRET_KEY = config.SECRET_KEY

# Load all the blueprints!
from rophako.modules.account import mod as AccountModule
app.register_blueprint(AccountModule)

# Custom Jinja handler to support custom- and default-template folders for
# rendering templates.
app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader("site/www"),    # Site specific.
    jinja2.FileSystemLoader("rophako/www"), # Default
])


@app.before_request
def before_request():
    """Called before all requests. Initialize global template variables."""

    # Default template vars.
    g.info = {
        "app": {
            "name": "Rophako",
            "version": __version__,
            "author": "Noah Petherbridge",
        },
        "uri": request.path.split("/")[1:],
    }


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
        print abspath
        print abspath + ".html"
        if os.path.isfile(abspath):
            return send_file(abspath)
        elif not "." in path and os.path.isfile(abspath + ".html"):
            return render_template(path + ".html")

    return not_found("404")


@app.route("/")
def index():
    print "INDEX PAGE"
    return catchall("index")


@app.errorhandler(404)
def not_found(error):
    print "NOT FOUND"
    return render_template('errors/404.html', **g.info), 404

# Domain specific endpoints.
if config.SITE_NAME == "kirsle.net":
    import rophako.modules.kirsle_legacy