# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

"""Blog models."""

from flask import g
import time
import re
import glob
import os
import sys

if sys.version_info[0] > 2:
    def unicode(s):
        return s

from rophako.settings import Config
import rophako.jsondb as JsonDB
from rophako.log import logger

def get_index():
    """Get the blog index.

    The index is the cache of available blog posts. It has the format:

    ```
    {
        'post_id': {
            fid: Friendly ID for the blog post (for URLs)
            time: epoch time of the post
            sticky: the stickiness of the post (shows first on global views)
            author: the author user ID of the post
            categories: [ list of categories ]
            privacy: the privacy setting
            subject: the post subject
        },
        ...
    }
    ```
    """

    # Index doesn't exist?
    if not JsonDB.exists("blog/index"):
        return rebuild_index()
    db = JsonDB.get("blog/index")

    # Hide any private posts if we aren't logged in.
    new_db = dict()
    if not g.info["session"]["login"]:
        for post_id, data in db.items():
            if data["privacy"] == "private":
                continue
            new_db[post_id] = db[post_id]

    return new_db


def rebuild_index():
    """Rebuild the index.json if it goes missing."""
    index = {}

    entries = JsonDB.list_docs("blog/entries")
    for post_id in entries:
        db = JsonDB.get("blog/entries/{}".format(post_id))
        update_index(post_id, db, index, False)

    JsonDB.commit("blog/index", index)
    return index


def update_index(post_id, post, index=None, commit=True):
    """Update a post's meta-data in the index. This is also used for adding a
    new post to the index for the first time.

    * post_id: The ID number for the post
    * post: The DB object for a blog post
    * index: If you already have the index open, you can pass it here
    * commit: Write the DB after updating the index (default True)"""
    if index is None:
        index = get_index()

    index[post_id] = dict(
        fid        = post["fid"],
        time       = post["time"] or int(time.time()),
        categories = post["categories"],
        sticky     = False, # TODO
        author     = post["author"],
        privacy    = post["privacy"] or "public",
        subject    = post["subject"],
    )
    if commit:
        JsonDB.commit("blog/index", index)


def get_categories():
    """Get the blog categories and their popularity."""
    index = get_index()

    # Group by tags.
    tags = {}
    for post, data in index.items():
        for tag in data["categories"]:
            if not tag in tags:
                tags[tag] = 0
            tags[tag] += 1

    return tags


def get_entry(post_id):
    """Load a full blog entry."""
    if not JsonDB.exists("blog/entries/{}".format(post_id)):
        return None

    db = JsonDB.get("blog/entries/{}".format(post_id))

    # If no FID, set it to the ID.
    if len(db["fid"]) == 0:
        db["fid"] = str(post_id)

    # If no "format" option, set it to HTML (legacy)
    if db.get("format", "") == "":
        db["format"] = "html"

    return db


def post_entry(post_id, fid, epoch, author, subject, avatar, categories,
               privacy, ip, emoticons, comments, format, body):
    """Post (or update) a blog entry."""

    # Fetch the index.
    index = get_index()

    # Editing an existing post?
    if not post_id:
        post_id = get_next_id(index)

    logger.debug("Posting blog post ID {}".format(post_id))

    # Get a unique friendly ID.
    if not fid:
        # The default friendly ID = the subject.
        fid = subject.lower()
        fid = re.sub(r'[^A-Za-z0-9]', '-', fid)
        fid = re.sub(r'\-+', '-', fid)
        fid = fid.strip("-")
        logger.debug("Chosen friendly ID: {}".format(fid))

    # Make sure the friendly ID is unique!
    if len(fid):
        test = fid
        loop = 1
        logger.debug("Verifying the friendly ID is unique: {}".format(fid))
        while True:
            collision = False

            for k, v in index.items():
                # Skip the same post, for updates.
                if k == post_id: continue

                if v["fid"] == test:
                    # Not unique.
                    loop += 1
                    test = fid + "_" + unicode(loop)
                    collision = True
                    logger.debug("Collision with existing post {}: {}".format(k, v["fid"]))
                    break

            # Was there a collision?
            if collision:
                continue # Try again.

            # Nope!
            break
        fid = test

    # DB body for the post.
    db = dict(
        fid        = fid,
        ip         = ip,
        time       = epoch or int(time.time()),
        categories = categories,
        sticky     = False, # TODO: implement sticky
        comments   = comments,
        emoticons  = emoticons,
        avatar     = avatar,
        privacy    = privacy or "public",
        author     = author,
        subject    = subject,
        format     = format,
        body       = body,
    )

    # Write the post.
    JsonDB.commit("blog/entries/{}".format(post_id), db)

    # Update the index cache.
    update_index(post_id, db, index)

    return post_id, fid


def delete_entry(post_id):
    """Remove a blog entry."""
    # Fetch the blog information.
    index = get_index()
    post  = get_entry(post_id)
    if post is None:
        logger.warning("Can't delete post {}, it doesn't exist!".format(post_id))

    # Delete the post.
    JsonDB.delete("blog/entries/{}".format(post_id))

    # Update the index cache.
    del index[str(post_id)] # Python JSON dict keys must be strings, never ints
    JsonDB.commit("blog/index", index)


def resolve_id(fid):
    """Resolve a friendly ID to the blog ID number."""
    index = get_index()

    # If the ID is all numeric, it's the blog post ID directly.
    if re.match(r'^\d+$', fid):
        if fid in index:
            return int(fid)
        else:
            logger.error("Tried resolving blog post ID {} as an EntryID, but it wasn't there!".format(fid))
            return None

    # It's a friendly ID. Scan for it.
    for post_id, data in index.items():
        if data["fid"] == fid:
            return int(post_id)

    logger.error("Friendly post ID {} wasn't found!".format(fid))
    return None


def list_avatars():
    """Get a list of all the available blog avatars."""
    avatars = set()
    paths = [
        # Load avatars from both locations. We check the built-in set first,
        # so if you have matching names in your local site those will override.
        "rophako/www/static/avatars/*.*",
        os.path.join(Config.site.site_root, "static", "avatars", "*.*"),
    ]
    for path in paths:
        for filename in glob.glob(path):
            filename = filename.split("/")[-1]
            avatars.add(filename)

    return sorted(avatars, key=lambda x: x.lower())


def get_next_id(index):
    """Get the next free ID for a blog post."""
    logger.debug("Getting next available blog ID number")
    sort = sorted(index.keys(), key=lambda x: int(x))
    next_id = 1
    if len(sort) > 0:
        next_id = int(sort[-1]) + 1
    logger.debug("Highest post ID is: {}".format(next_id))

    # Sanity check!
    if next_id in index:
        raise Exception("Failed to get_next_id for the blog. Chosen ID is still in the index!")
    return next_id
