# -*- coding: utf-8 -*-

# Legacy endpoint compatibility from kirsle.net.

from flask import request, redirect, url_for
from rophako import app
import rophako.model.blog as Blog

@app.route("/+")
def google_plus():
    return redirect("https://plus.google.com/+NoahPetherbridge/posts")

@app.route("/blog.html")
def ancient_legacy_blog():
    post_id = request.args.get("id", None)
    if post_id is None:
        return redirect(url_for("blog.index"))

    # Look up the friendly ID.
    post = Blog.get_entry(post_id)
    if not post:
        flash("That blog entry wasn't found.")
        return redirect(url_for("blog.index"))

    return redirect(url_for("blog.entry", fid=post["fid"]))

@app.route("/blog/kirsle/<fid>")
def legacy_blog(fid):
    return redirect(url_for("blog.entry", fid=fid))

@app.route("/<page>.html")
def legacy_url(page):
    return "/{}".format(page)