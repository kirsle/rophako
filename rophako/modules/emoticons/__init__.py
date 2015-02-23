# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""Endpoints for the commenting subsystem."""

from flask import Blueprint, g

import rophako.model.emoticons as Emoticons
from rophako.utils import template
from rophako.settings import Config

mod = Blueprint("emoticons", __name__, url_prefix="/emoticons")


@mod.route("/")
def index():
    """List the available emoticons."""
    theme = Emoticons.load_theme()

    smileys = []
    for img in sorted(theme["map"]):
        smileys.append({
            "img": img,
            "triggers": theme["map"][img],
        })

    g.info["theme"] = Config.emoticons.theme
    g.info["theme_name"] = theme["name"]
    g.info["smileys"]    = smileys
    return template("emoticons/index.html")
