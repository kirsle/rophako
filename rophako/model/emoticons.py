# -*- coding: utf-8 -*-

"""Emoticon models."""

import os
import codecs
import json
import re

from rophako.settings import Config
from rophako.log import logger


_cache = {}


def load_theme():
    """Pre-load and cache the emoticon theme. This happens on startup."""
    theme = Config.emoticons.theme
    global _cache

    # Cached?
    if _cache:
        return _cache

    # Only if the theme file exists.
    settings = os.path.join(Config.emoticons.root_private, theme, "emoticons.json")
    if not os.path.isfile(settings):
        logger.error("Failed to load smiley theme {}: not found!")

        # Try the default (tango).
        theme = "tango"
        settings = os.path.join(Config.emoticons.root_private, theme, "emoticons.json")
        if os.path.isfile(settings):
            logger.info("Falling back to default theme: tango")
        else:
            # Give up.
            return {}

    # Read it.
    fh = codecs.open(settings, "r", "utf-8")
    text = fh.read()
    fh.close()

    try:
        data = json.loads(text)
    except Exception as e:
        logger.error("Couldn't load JSON from emoticon file: {}".format(e))
        data = {}

    # Cache and return it.
    _cache = data
    return data


def render(message):
    """Render the emoticons into a message.

    The message should already be stripped of HTML and otherwise be 'safe' to
    embed on a web page. The output of this function includes `<img>` tags and
    these won't work otherwise."""

    # Get the smileys config.
    smileys = load_theme()

    # Process all smileys.
    for img in sorted(smileys["map"]):
        for trigger in smileys["map"][img]:
            if trigger in message:
                # Substitute it.
                sub = """<img src="{url}" class="rophako-emoticon" alt="{trigger}" title="{trigger}">""".format(
                    url="/static/smileys/{}/{}".format(Config.emoticons.theme, img),
                    trigger=trigger,
                )
                pattern = r'([^A-Za-z0-9:\-]|^){}([^A-Za-z0-9:\-]|$)'.format(re.escape(trigger))
                result = r'\1{}\2'.format(sub)
                message = re.sub(pattern, result, message)

    return message
