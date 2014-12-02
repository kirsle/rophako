# -*- coding: utf-8 -*-

"""Endpoints for the commenting subsystem."""

from flask import Blueprint, g, request, redirect, url_for, session, flash
import re
import time

import rophako.model.user as User
import rophako.model.comment as Comment
from rophako.utils import (template, pretty_time, login_required, sanitize_name,
    remote_addr)
from rophako.plugin import load_plugin
from rophako.log import logger
from config import *

mod = Blueprint("comment", __name__, url_prefix="/comments")
load_plugin("rophako.modules.emoticons")


@mod.route("/")
def index():
    return template("blog/index.html")


@mod.route("/preview", methods=["POST"])
def preview():
    # Get the form fields.
    form   = get_comment_form(request.form)
    thread = sanitize_name(form["thread"])

    # Trap fields.
    trap1 = request.form.get("website", "x") != "http://"
    trap2 = request.form.get("email", "x") != ""
    if trap1 or trap2:
        flash("Wanna try that again?")
        return redirect(url_for("index"))

    # Validate things.
    if len(form["message"]) == 0:
        flash("You must provide a message with your comment.")
        return redirect(form["url"])

    # Gravatar?
    gravatar = Comment.gravatar(form["contact"])

    # Are they submitting?
    if form["action"] == "submit":
        Comment.add_comment(
            thread=thread,
            uid=g.info["session"]["uid"],
            ip=remote_addr(),
            time=int(time.time()),
            image=gravatar,
            name=form["name"],
            subject=form["subject"],
            message=form["message"],
            url=form["url"],
        )

        # Are we subscribing to the thread?
        if form["subscribe"] == "true":
            email = form["contact"]
            if "@" in email:
                Comment.add_subscriber(thread, email)
                flash("You have been subscribed to future comments on this page.")

        flash("Your comment has been added!")
        return redirect(form["url"])

    # Gravatar.
    g.info["gravatar"]    = gravatar
    g.info["preview"]     = Comment.format_message(form["message"])
    g.info["pretty_time"] = pretty_time(COMMENT_TIME_FORMAT, time.time())

    g.info.update(form)
    return template("comment/preview.html")


@mod.route("/delete/<thread>/<cid>")
@login_required
def delete(thread, cid):
    """Delete a comment."""
    url = request.args.get("url")
    Comment.delete_comment(thread, cid)
    flash("Comment deleted!")
    return redirect(url or url_for("index"))


@mod.route("/edit/<thread>/<cid>", methods=["GET", "POST"])
@login_required
def edit(thread, cid):
    """Edit an existing comment."""
    url = request.args.get("url")
    comment = Comment.get_comment(thread, cid)
    if not comment:
        flash("The comment wasn't found!")
        return redirect(url or url_for("index"))

    # Submitting?
    if request.method == "POST":
        action  = request.form.get("action")
        message = request.form.get("message")
        url     = request.form.get("url") # Preserve the URL!
        if len(message) == 0:
            flash("The comment must have a message!")
            return redirect(url_for(".edit", thread=thread, cid=cid, url=url))

        # Update the real comment data with the submitted message (for preview),
        # if they clicked Save it will then be saved back to disk.
        comment["message"] = message

        if action == "save":
            # Saving the changes!
            Comment.update_comment(thread, cid, comment)
            flash("Comment updated successfully!")
            return redirect(url or url_for("index"))

    # Render the Markdown.
    comment["formatted_message"] = Comment.format_message(comment["message"])

    g.info["thread"]  = thread
    g.info["cid"]     = cid
    g.info["comment"] = comment
    g.info["url"]     = url or ""
    return template("comment/edit.html")


@mod.route("/privacy")
def privacy():
    """The privacy policy and global unsubscribe page."""
    return template("comment/privacy.html")


@mod.route("/unsubscribe", methods=["GET", "POST"])
def unsubscribe():
    """Unsubscribe an e-mail from a comment thread (or all threads)."""

    # This endpoint can be called with either method. For the unsubscribe links
    # inside the e-mails, it uses GET. For the global out-opt, it uses POST.
    thread, email = None, None
    if request.method == "POST":
        thread = request.form.get("thread", "")
        email  = request.form.get("email", "")

        # Spam check.
        trap1 = request.form.get("url", "x") != "http://"
        trap2 = request.form.get("message", "x") != ""
        if trap1 or trap2:
            flash("Wanna try that again?")
            return redirect(url_for("index"))
    else:
        thread = request.args.get("thread", "")
        email  = request.args.get("who", "")

    # Input validation.
    if not thread:
        flash("Comment thread not found.")
        return redirect(url_for("index"))
    if not email:
        flash("E-mail address not provided.")
        return redirect(url_for("index"))

    # Do the unsubscribe. If thread is *, this means a global unsubscribe from
    # all threads.
    Comment.unsubscribe(thread, email)

    g.info["thread"] = thread
    g.info["email"]  = email
    return template("comment/unsubscribed.html")


def partial_index(thread, subject, header=True):
    """Partial template for including the index view of a comment thread."""

    comments = Comment.get_comments(thread)

    # Sort the comments by most recent on bottom.
    sorted_cids = [ x for x in sorted(comments, key=lambda y: comments[y]["time"]) ]
    sorted_comments = []
    for cid in sorted_cids:
        comment = comments[cid]
        comment["id"] = cid

        # Was the commenter logged in?
        if comment["uid"] > 0:
            user = User.get_user(uid=comment["uid"])
            avatar = User.get_picture(uid=comment["uid"])
            comment["name"] = user["name"]
            comment["username"] = user["username"]
            comment["image"] = avatar

        # Add the pretty time.
        comment["pretty_time"] = pretty_time(COMMENT_TIME_FORMAT, comment["time"])

        # Format the message for display.
        comment["formatted_message"] = Comment.format_message(comment["message"])

        sorted_comments.append(comment)

    g.info["header"] = header
    g.info["thread"] = thread
    g.info["subject"] = subject
    g.info["url"] = request.url
    g.info["comments"] = sorted_comments
    g.info["photo_url"] = PHOTO_ROOT_PUBLIC
    return template("comment/index.inc.html")


def get_comment_form(form):
    return dict(
        action  = request.form.get("action", ""),
        thread  = request.form.get("thread", ""),
        url     = request.form.get("url", ""),
        subject = request.form.get("subject", "[No Subject]"),
        name    = request.form.get("name", ""),
        contact = request.form.get("contact", ""),
        message = request.form.get("message", ""),
        subscribe = request.form.get("subscribe", "false"),
    )
