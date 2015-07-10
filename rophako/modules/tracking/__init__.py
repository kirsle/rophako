# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

"""Endpoints for visitor tracking functions."""

from flask import Blueprint, g
import re

import rophako.model.tracking as Tracking
from rophako.utils import template

mod = Blueprint("tracking", __name__, url_prefix="/tracking")


@mod.route("/")
def index():
    return template("tracking/index.html")


@mod.route("/visitors")
def visitors():
    g.info["history"] = Tracking.get_visitor_details()
    return template("tracking/visitors.html")


@mod.route("/referrers")
def referrers():
    g.info["referrers"] = Tracking.get_referrers()

    # Filter some of the links.
    for i, link in enumerate(g.info["referrers"]["referrers"]):
        # Clean up useless Google links.
        if "google" in link[0] and re.search(r'/(?:imgres|url|search|translate\w+)?/', link[0]):
            g.info["referrers"]["referrers"][i] = None

    # Make the links word-wrap properly.
    filtered = [
        [ re.sub(r'(.{20})', r'\1<wbr>', x[0]), x[1] ]
        for x in g.info["referrers"]["referrers"]
        if x is not None
    ]
    g.info["referrers"]["referrers"] = filtered

    return template("tracking/referrers.html")
