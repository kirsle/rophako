# -*- coding: utf-8 -*-

from flask import Blueprint

mod = Blueprint("account", __name__, url_prefix="/account")

@mod.route("/")
def index():
    return "Test"