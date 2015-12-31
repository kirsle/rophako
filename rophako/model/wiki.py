# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

"""Wiki models."""

from flask import url_for
import time
import re
import hashlib

import rophako.jsondb as JsonDB
from rophako.utils import render_markdown
from rophako.log import logger

def render_page(content):
    """Render the Markdown content of a Wiki page, and support inter-page
    linking with [[double braces]].

    For simple links, just use the [[Page Name]]. To have a different link text
    than the page name, use [[Link Text|Page Name]]."""
    html = render_markdown(content)

    # Look for [[double brackets]]
    links = re.findall(r'\[\[(.+?)\]\]', html)
    for match in links:
        label = page = match
        if "|" in match:
            label, page = match.split("|", 2)

        # Does the page exist?
        output = '''<a href="{url}">{label}</a>'''
        if not JsonDB.exists("wiki/pages/{}".format(page)):
            output = '''<a href="{url}" class="wiki-broken">{label}</a>'''

        html = html.replace("[[{}]]".format(match),
            output.format(
                url=url_for("wiki.view_page", name=name_to_url(page)),
                label=label,
            )
        )

    return html


def get_page(name):
    """Get a Wiki page. Returns `None` if the page isn't found."""
    name = name.strip("/") # Remove any surrounding slashes.
    path = "wiki/pages/{}".format(name)
    if not JsonDB.exists(path):
        return None

    # TODO: case insensitive page names...

    db = JsonDB.get(path)
    return db


def list_pages():
    """Get a list of all existing wiki pages."""
    return JsonDB.list_docs("wiki/pages", recursive=True)


def edit_page(name, author, body, note, history=True):
    """Write to a page."""
    name = name.strip("/") # Remove any surrounding slashes.

    # Get the old page first.
    page = get_page(name)
    if not page:
        # Initialize the page.
        page = dict(
            revisions=[],
        )

    # The new revision to be added.
    rev = dict(
        id=hashlib.md5(str(int(time.time())).encode("utf-8")).hexdigest(),
        time=int(time.time()),
        author=author,
        body=body,
        note=note or "Updated the page.",
    )

    # Updating the history?
    if history:
        page["revisions"].insert(0, rev)
    else:
        # Replacing the original item.
        if len(page["revisions"]):
            page["revisions"][0] = rev
        else:
            page["revisions"].append(rev)

    # Write it.
    logger.info("Write to Wiki page {}".format(name))
    JsonDB.commit("wiki/pages/{}".format(name), page)
    return True


def delete_history(name, revision):
    """Delete a revision entry from the history."""
    name = name.strip("/")

    # Get page first.
    page = get_page(name)
    if not page:
        return None

    # Revise history.
    history = list()
    for rev in page["revisions"]:
        if rev["id"] == revision:
            logger.info("Delete history ID {} from Wiki page {}".format(revision, name))
            continue
        history.append(rev)

    # Empty history = delete the page.
    if len(history) == 0:
        logger.info("Deleted last history item; Remove Wiki page {}".format(name))
        return delete_page(name)

    page["revisions"] = history
    JsonDB.commit("wiki/pages/{}".format(name), page)

    return True


def delete_page(name):
    """Completely delete a wiki page."""
    name = name.strip("/")
    path = "wiki/pages/{}".format(name)

    if JsonDB.exists(path):
        logger.info("Delete Wiki page {}".format(name))
        JsonDB.delete(path)

    return True


def name_to_url(name):
    """Convert a Wiki page name into a URL safe version.

    All non-alphanumerics are replaced with dashes, multiple dashes in a row
    are flattened down to one, and any preceeding or trailing dashes are also
    stripped off."""
    name = re.sub(r'[^A-Za-z0-9/]', '-', name).replace('--', '-').strip('-')
    return name


def url_to_name(url):
    """Convert a URL to a page name, for 404'd links.

    Turns a link like /wiki/New-Page-Name into 'New Page Name'"""
    return url.replace("-", " ")
