#!/usr/bin/env python

"""Migrate blog database files from a PerlSiikir site to Rophako.

Usage: scripts/siikir-blog-migrate.py <path/to/siikir/db/root>

Rophako supports one global blog, so the blog of UserID 1 in Siikir is used."""

import sys
import os
import codecs
import json
import glob

sys.path.append(".")
import rophako.jsondb as JsonDB

# Path to Siikir DB root.
siikir = None

def main():
    if len(sys.argv) == 1:
        print "Usage: {} <path/to/siikir/db/root>".format(__file__)
        sys.exit(1)

    global siikir
    siikir = sys.argv[1]
    print "Siikir DB:", siikir
    if raw_input("Confirm? [yN] ") != "y":
        sys.exit(1)

    convert_index()
    convert_posts()
    convert_comments()
    convert_subscriptions()


def convert_index():
    print "Converting blog index"
    index = json_get("blog/index/1.json")
    new = {}
    for post_id, data in index.iteritems():
        del data["id"]

        # Enforce data types.
        data["author"] = int(data["author"])
        data["time"]   = int(data["time"])
        data["sticky"] = bool(data["sticky"])

        new[post_id] = data

    JsonDB.commit("blog/index", new)


def convert_posts():
    print "Converting blog entries..."

    for name in glob.glob(os.path.join(siikir, "blog/entries/1/*.json")):
        name = name.split("/")[-1]
        post = json_get("blog/entries/1/{}".format(name))
        post_id = post["id"]
        del post["id"]

        # Enforce data types.
        post["time"] = int(post["time"])
        post["author"] = int(post["author"])
        post["comments"] = bool(post["comments"])
        post["sticky"] = bool(post["sticky"])
        post["emoticons"] = bool(post["emoticons"])

        print "*", post["subject"]
        JsonDB.commit("blog/entries/{}".format(post_id), post)


def convert_comments():
    print "Converting comments..."

    for name in glob.glob(os.path.join(siikir, "comments/1/*.json")):
        name = name.split("/")[-1]
        if name.startswith("photos-"): continue
        data = json_get("comments/1/{}".format(name))

        thread = name[:len(name)-5]

        # Enforce data types.
        for cid in data:
            data[cid]["time"] = int(data[cid]["time"])
            data[cid]["uid"] = int(data[cid]["uid"])

        print "*", thread
        JsonDB.commit("comments/threads/{}".format(thread), data)


def convert_subscriptions():
    print "Converting subscriptions..."

    for name in glob.glob(os.path.join(siikir, "subscribers/1/*.json")):
        name = name.split("/")[-1]
        if name.startswith("photos-"): continue
        data = json_get("subscribers/1/{}".format(name))

        thread = name[:len(name)-5]

        # Enforce data types.
        for email in data:
            data[email] = int(data[email])

        print "*", thread
        JsonDB.commit("comments/subscribers/{}".format(thread), data)


def json_get(document):
    fh = codecs.open(os.path.join(siikir, document), 'r', 'utf-8')
    text = fh.read()
    fh.close()
    return json.loads(text)


if __name__ == "__main__":
    main()