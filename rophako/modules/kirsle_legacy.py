# -*- coding: utf-8 -*-

# Legacy endpoint compatibility from kirsle.net.

from flask import request, redirect
from rophako import app

@app.route("/+")
def google_plus():
    return redirect("https://plus.google.com/+NoahPetherbridge/posts")

@app.route("/blog.html")
def legacy_blog():
    post_id = request.args.get("id", "")

    # All of this is TO-DO.
    # friendly_id = get friendly ID
    # return redirect(...)
    return "TO-DO"

@app.route("/<page>.html")
def legacy_url(page):
    return "/{}".format(page)