# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

"""Endpoints for the wiki."""

from flask import Blueprint, g, request, redirect, url_for, flash

import rophako.model.user as User
import rophako.model.wiki as Wiki
import rophako.model.emoticons as Emoticons
from rophako.utils import template, pretty_time, render_markdown, login_required
from rophako.settings import Config

mod = Blueprint("wiki", __name__, url_prefix="/wiki")

@mod.route("/")
def index():
    """Wiki index. Redirects to the default page from the config."""
    default = Wiki.name_to_url(Config.wiki.default_page)
    return redirect(url_for("wiki.view_page", name=default))


@mod.route("/_pages")
def list_pages():
    """Wiki page list."""
    g.info["pages"] = [
        {"name": name, "link": Wiki.name_to_url(name)} \
            for name in Wiki.list_pages()
    ]
    return template("wiki/list.html")


@mod.route("/<path:name>")
def view_page(name):
    """Show a specific wiki page."""
    link = name
    name = Wiki.url_to_name(name)

    g.info["link"] = link
    g.info["title"] = name

    # Look up the page.
    page = Wiki.get_page(name)
    if not page:
        # Page doesn't exist... yet!
        g.info["title"] = Wiki.url_to_name(name)
        return template("wiki/missing.html"), 404

    # Which revision to show?
    version = request.args.get("revision", None)
    if version:
        # Find this one.
        rev = None
        for item in page["revisions"]:
            if item["id"] == version:
                rev = item
                break

        if rev is None:
            flash("That revision was not found for this page.")
            rev = page["revisions"][0]
    else:
        # Show the latest one.
        rev = page["revisions"][0]

    # Getting the plain text source?
    if request.args.get("source", None):
        g.info["markdown"] = render_markdown("\n".join([
            "# Source: {}".format(name),
            "",
            "```markdown",
            rev["body"],
            "```"
        ]))
        return template("markdown.inc.html")

    # Render it!
    g.info["rendered_body"] = Wiki.render_page(rev["body"])
    g.info["rendered_body"] = Emoticons.render(g.info["rendered_body"])
    g.info["pretty_time"] = pretty_time(Config.wiki.time_format, rev["time"])

    # Author info
    g.info["author"] = User.get_user(uid=rev["author"])

    return template("wiki/page.html")


@mod.route("/<path:name>/_revisions")
def history(name):
    """Page history."""
    name = Wiki.url_to_name(name)

    # Look up the page.
    page = Wiki.get_page(name)
    if not page:
        flash("Wiki page not found.")
        return redirect(url_for(".index"))

    authors = dict()
    history = list()
    for rev in page["revisions"]:
        uid = rev["author"]
        if not uid in authors:
            authors[uid] = User.get_user(uid=uid)

        history.append(dict(
            id=rev["id"],
            author=authors[uid],
            note=rev["note"],
            pretty_time=pretty_time(Config.wiki.time_format, rev["time"]),
        ))

    g.info["link"] = Wiki.name_to_url(name)
    g.info["title"] = name
    g.info["history"] = history
    return template("wiki/history.html")


@mod.route("/_edit", methods=["GET", "POST"])
@login_required
def edit():
    """Wiki page editor."""
    title   = request.args.get("name", "")
    body    = ""
    history = True # Update History box is always checked by default
    note    = request.args.get("note", "")

    # Editing an existing page?
    page = Wiki.get_page(title)
    if page:
        head = page["revisions"][0]
        body = head["body"]

    if request.method == "POST":
        # Submitting the form.
        action  = request.form.get("action", "preview")
        title   = request.form.get("name", "")
        body    = request.form.get("body", "")
        history = request.form.get("history", "false") == "true"
        note    = request.form.get("note", "")

        if action == "preview":
            # Just previewing it.
            g.info["preview"] = True

            # Render markdown
            g.info["rendered_body"] = Wiki.render_page(body)

            # Render emoticons.
            g.info["rendered_body"] = Emoticons.render(g.info["rendered_body"])
        elif action == "publish":
            # Publishing! Validate inputs.
            invalid = False

            if len(title) == 0:
                invalid = True
                flash("You must have a page title.")
            if len(body) == 0:
                invalid = True
                flash("You must have a page body.")

            if not invalid:
                # Update the page.
                Wiki.edit_page(
                    author=g.info["session"]["uid"],
                    name=title,
                    body=body,
                    note=note,
                    history=history,
                )
                return redirect(url_for("wiki.view_page",
                    name=Wiki.name_to_url(title)
                ))


    g.info["title"]   = title
    g.info["body"]    = body
    g.info["note"]    = note
    g.info["history"] = history
    return template("wiki/edit.html")


@mod.route("/_delete_history/<path:name>/<revision>", methods=["GET", "POST"])
@login_required
def delete_revision(name, revision):
    """Delete a wiki page revision from history."""
    link = name
    name = Wiki.url_to_name(name)

    if request.method == "POST":
        Wiki.delete_history(name, revision)
        flash("Revision deleted.")
        return redirect(url_for("wiki.view_page", name=Wiki.name_to_url(name)))

    g.info["confirm_url"] = url_for("wiki.delete_revision", name=link, revision=revision)
    g.info["title"] = name
    g.info["type"] = "revision"
    return template("wiki/delete.html")


@mod.route("/_delete_page/<path:name>", methods=["GET", "POST"])
@login_required
def delete_page(name):
    """Delete a wiki page entirely."""
    link = name
    name = Wiki.url_to_name(name)

    if request.method == "POST":
        Wiki.delete_page(name)
        flash("Page completely deleted.")
        return redirect(url_for("wiki.index"))

    g.info["confirm_url"] = url_for("wiki.delete_page", name=link)
    g.info["title"] = name
    g.info["type"] = "page"
    return template("wiki/delete.html")
