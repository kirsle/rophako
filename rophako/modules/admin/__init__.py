# -*- coding: utf-8 -*-

"""Endpoints for admin functions."""

from flask import g, Blueprint, request, redirect, url_for, session, flash

import rophako.model.user as User
from rophako.modules.account import validate_create_form
from rophako.utils import template, admin_required

mod = Blueprint("admin", __name__, url_prefix="/admin")

@mod.route("/")
@admin_required
def index():
    return template("admin/index.html")


@mod.route("/users")
@admin_required
def users():
    # Get the list of existing users.
    users = User.list_users()

    return template("admin/users.html",
        users=users,
    )


@mod.route("/users/create", methods=["POST"])
@admin_required
def create_user():
    # Submitting the form.
    username = request.form.get("username", "")
    name     = request.form.get("name", "")
    pw1      = request.form.get("password1", "")
    pw2      = request.form.get("password2", "")
    role     = request.form.get("role", "")

    # Default name = username.
    if name == "":
        name = username

    # Lowercase the user.
    username = username.lower()
    if User.exists(username=username):
        flash("That username already exists.")
        return redirect(url_for(".users"))

    # Validate the form.
    errors = validate_create_form(username, pw1, pw2)
    if errors:
        for error in errors:
            flash(error)
        return redirect(url_for(".users"))

    # Create the account.
    uid = User.create(
        username=username,
        password=pw1,
        name=name,
        role=role,
    )

    flash("User created!")
    return redirect(url_for(".users"))


@mod.route("/users/edit/<uid>", methods=["GET", "POST"])
@admin_required
def edit_user(uid):
    uid  = int(uid)
    user = User.get_user(uid=uid)

    # Submitting?
    if request.method == "POST":
        action   = request.form.get("action", "")
        username = request.form.get("username", "")
        name     = request.form.get("name", "")
        pw1      = request.form.get("password1", "")
        pw2      = request.form.get("password2", "")
        role     = request.form.get("role", "")

        username = username.lower()

        if action == "save":
            # Validate...
            errors = None

            # Don't allow them to change the username to one that exists.
            if username != user["username"]:
                if User.exists(username=username):
                    flash("That username already exists.")
                    return redirect(url_for(".edit_user", uid=uid))

            # Password provided?
            if len(pw1) > 0:
                errors = validate_create_form(username, pw1, pw2)
            elif username != user["username"]:
                # Just validate the username, then.
                errors = validate_create_form(username, skip_passwd=True)

            if errors:
                for error in errors:
                    flash(error)
                return redirect(url_for(".edit_user", uid=uid))

            # Update the user.
            user["username"] = username
            user["name"]     = name or username
            user["role"]     = role
            if len(pw1) > 0:
                user["password"] = User.hash_password(pw1)
            User.update_user(uid, user)

            flash("User account updated!")
            return redirect(url_for(".users"))

        elif action == "delete":
            # Don't let them delete themself!
            if uid == g.info["session"]["uid"]:
                flash("You shouldn't delete yourself!")
                return redirect(url_for(".edit_user", uid=uid))

            User.delete_user(uid)
            flash("User deleted!")
            return redirect(url_for(".users"))

    return template("admin/edit_user.html",
        info=user,
    )


@mod.route("/impersonate/<int:uid>")
@admin_required
def impersonate(uid):
    """Impersonate a user."""
    # Check that they exist.
    if not User.exists(uid=uid):
        flash("That user ID wasn't found.")
        return redirect(url_for(".users"))

    db = User.get_user(uid=uid)
    if db["role"] == "deleted":
        flash("That user was deleted!")
        return redirect(url_for(".users"))

    # Log them in!
    orig_uid = session["uid"]
    session.update(
        login=True,
        uid=uid,
        username=db["username"],
        name=db["name"],
        role=db["role"],
        impersonator=orig_uid,
    )

    flash("Now logged in as {}".format(db["name"]))
    return redirect(url_for("index"))

@mod.route("/unimpersonate")
def unimpersonate():
    """Unimpersonate a user."""

    # Must be impersonating, first!
    if not "impersonator" in session:
        flash("Stop messing around.")
        return redirect(url_for("index"))

    uid = session.pop("impersonator")
    db = User.get_user(uid=uid)
    session.update(
        login=True,
        uid=uid,
        username=db["username"],
        name=db["name"],
        role=db["role"],
    )

    flash("No longer impersonating.")
    return redirect(url_for("index"))
