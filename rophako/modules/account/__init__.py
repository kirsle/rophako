# -*- coding: utf-8 -*-

"""Endpoints for user login and out."""

from flask import Blueprint, request, redirect, url_for, session, flash
import re

import rophako.model.user as User
from rophako.utils import template

mod = Blueprint("account", __name__, url_prefix="/account")

@mod.route("/")
def index():
    return redirect(url_for(".login"))


@mod.route("/login", methods=["GET", "POST"])
def login():
    """Log into an account."""

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Lowercase the username.
        username = username.lower()

        if User.check_auth(username, password):
            # OK!
            db = User.get_user(username=username)
            session["login"] = True
            session["username"] = username
            session["uid"]  = db["uid"]
            session["name"] = db["name"]
            session["role"] = db["role"]

            # Redirect them to a local page?
            url = request.form.get("url", "")
            if url.startswith("/"):
                return redirect(url)

            return redirect(url_for("index"))
        else:
            flash("Authentication failed.")
            return redirect(url_for(".login"))

    return template("account/login.html")


@mod.route("/logout")
def logout():
    """Log out the user."""
    session["login"] = False
    session["username"] = "guest"
    session["uid"] = 0
    session["name"] = "Guest"
    session["role"] = "user"

    flash("You have been signed out.")
    return redirect(url_for(".login"))


@mod.route("/setup", methods=["GET", "POST"])
def setup():
    """Initial setup to create the Admin user account."""

    # This can't be done if users already exist on the CMS!
    if User.exists(uid=1):
        flash("This website has already been configured (users already created).")
        return redirect(url_for("index"))

    if request.method == "POST":
        # Submitting the form.
        username = request.form.get("username", "")
        name     = request.form.get("name", "")
        pw1      = request.form.get("password1", "")
        pw2      = request.form.get("password2", "")

        # Default name = username.
        if name == "":
            name = username

        # Lowercase the user.
        username = username.lower()
        if User.exists(username=username):
            flash("That username already exists.")
            return redirect(url_for(".setup"))

        # Validate the form.
        errors = validate_create_form(username, pw1, pw2)
        if errors:
            for error in errors:
                flash(error)
            return redirect(url_for(".setup"))

        # Create the account.
        uid = User.create(
            username=username,
            password=pw1,
            name=name,
            role="admin",
        )

        flash("Admin user created! Please log in now.".format(uid))
        return redirect(url_for(".login"))


    return template("account/setup.html")


def validate_create_form(username, pw1=None, pw2=None, skip_passwd=False):
    """Validate the submission of a create-user form.

    Returns a list of error messages if there were errors, otherwise
    it returns None."""
    errors = list()

    if len(username) == 0:
        errors.append("You must provide a username.")

    if re.search(r'[^A-Za-z0-9-_]', username):
        errors.append("Usernames can only contain letters, numbers, dashes or underscores.")

    if not skip_passwd:
        if len(pw1) < 3:
            errors.append("You should use at least 3 characters in your password.")

        if pw1 != pw2:
            errors.append("Your passwords don't match.")

    if len(errors):
        return errors
    else:
        return None
