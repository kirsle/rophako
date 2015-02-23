# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""Endpoints for contacting the site owner."""

from flask import Blueprint, request, redirect, url_for, flash

from rophako.utils import template, send_email, remote_addr
from rophako.settings import Config

mod = Blueprint("contact", __name__, url_prefix="/contact")


@mod.route("/")
def index():
    return template("contact/index.html")


@mod.route("/send", methods=["POST"])
def send():
    """Submitting the contact form."""
    name    = request.form.get("name", "") or "Anonymous"
    email   = request.form.get("email", "")
    subject = request.form.get("subject", "") or "[No Subject]"
    message = request.form.get("message", "")

    # Spam traps.
    trap1 = request.form.get("contact", "x") != ""
    trap2 = request.form.get("website", "x") != "http://"
    if trap1 or trap2:
        flash("Wanna try that again?")
        return redirect(url_for(".index"))

    # Message is required.
    if len(message) == 0:
        flash("The message is required.")
        return redirect(url_for(".index"))

    # Email looks valid?
    reply_to = None
    if "@" in email and "." in email:
        reply_to = email

    # Send the e-mail.
    send_email(
        to=Config.site.notify_address,
        reply_to=reply_to,
        subject="Contact Form on {}: {}".format(Config.site.site_name, subject),
        message="""A visitor to {site_name} has sent you a message!

IP Address: {ip}
User Agent: {ua}
Referrer: {referer}
Name: {name}
E-mail: {email}
Subject: {subject}

{message}""".format(
            site_name=Config.site.site_name,
            ip=remote_addr(),
            ua=request.user_agent.string,
            referer=request.headers.get("Referer", ""),
            name=name,
            email=email,
            subject=subject,
            message=message,
        )
    )

    flash("Your message has been delivered.")
    return redirect(url_for("index"))
