# -*- coding: utf-8 -*-
from __future__ import unicode_literals

"""Visitor tracking models."""

import time
import requests

import rophako.jsondb as JsonDB
from rophako.utils import (remote_addr, pretty_time, server_name,
    handle_exception)

def track_visit(request, session):
    """Main logic to track and log visitor details."""

    # Get their tracking cookie value. The value will either be their HTTP
    # referrer (if exists and valid) or else a "1".
    cookie = session.get("tracking")
    addr   = remote_addr()
    values = dict() # Returnable traffic values

    # Log hit counts. We need four kinds:
    # - Unique today   - Unique total
    # - Hits today     - Hits total
    today = pretty_time("%Y-%m-%d", time.time())
    files = {
        "unique/{}".format(today) : "unique_today",
        "unique/total"            : "unique_total",
        "hits/{}".format(today)   : "hits_today",
        "hits/total"              : "hits_total",
    }

    # Go through the hit count files. Update them only if their tracking
    # cookie was not present.
    for file, key in files.items():
        dbfile = "traffic/{}".format(file)
        if file.startswith("hits"):
            # Hit file is just a simple counter.
            db = dict(hits=0)
            if JsonDB.exists(dbfile):
                db = JsonDB.get(dbfile)
                if db is None:
                    db = dict(hits=0)

            # Update it?
            if not cookie:
                db["hits"] += 1
                JsonDB.commit(dbfile, db)

            # Store the copy.
            values[key] = db["hits"]
        else:
            # Unique file is a collection of IP addresses.
            db = dict()
            if JsonDB.exists(dbfile):
                db = JsonDB.get(dbfile)
                if db is None:
                    db = dict()

            # Update with their IP?
            if not cookie and not addr in db:
                db[addr] = time.time()
                JsonDB.commit(dbfile, db)

            # Store the copy.
            values[key] = len(db.keys())

    # Log their HTTP referrer.
    referrer = "1"
    if request.referrer:
        # Branch and check this.
        referrer = log_referrer(request, request.referrer)
        if not referrer:
            # Wasn't a valid referrer.
            referrer = "1"

    # Set their tracking cookie.
    if not cookie:
        cookie = referrer
        session["tracking"] = cookie

    return values


def log_referrer(request, link):
    """Double check the referring URL."""

    # Ignore if same domain.
    hostname = server_name()
    if link.startswith("http://{}".format(hostname)) or \
       link.startswith("https://{}".format(hostname)):
        return None

    # See if the URL really links back to us.
    hostname = server_name()
    try:
        r = requests.get(link,
            timeout=5,
            verify=False, # Don't do SSL verification
        )

        # Make sure the request didn't just redirect back to our main site
        # (e.g. http://whatever.example.com wildcard may redirect back to
        # http://example.com, and if that's us, don't log that!
        if r.url.startswith("http://{}".format(hostname)) or \
           r.url.startswith("https://{}".format(hostname)):
            return None

        # Look for our hostname in their page.
        if hostname in r.text:
            # Log it.
            db = list()
            if JsonDB.exists("traffic/referrers"):
                # Don't cache the result -- the list can get huge!
                db = JsonDB.get("traffic/referrers", cache=False)
            db.append(link)
            JsonDB.commit("traffic/referrers", db, cache=False)
            return link
    except:
        pass

    return None


def rebuild_visitor_stats():
    """Recalculate the total unique/hits based on daily info."""
    total_unique = {}
    total_hits   = 0

    # Tally them all up!
    for date in JsonDB.list_docs("traffic/unique"):
        if date == "total":
            continue
        db = JsonDB.get("traffic/unique/{}".format(date), cache=False)
        total_unique.update(db)
    for date in JsonDB.list_docs("traffic/hits"):
        if date == "total":
            continue
        db = JsonDB.get("traffic/hits/{}".format(date), cache=False)
        total_hits += db.get("hits", 0)

    # Write the outputs.
    JsonDB.commit("traffic/unique/total", total_unique)
    JsonDB.commit("traffic/hits/total", dict(hits=total_hits))


def get_visitor_details():
    """Retrieve detailed visitor information for the frontend."""
    result = {
        "traffic": [],                      # Historical traffic data
        "most_unique": [ "0000-00-00", 0 ], # Day with the most unique
        "most_hits":   [ "0000-00-00", 0 ], # Day with the most hits
        "oldest": None,                     # Oldest day on record.
    }

    # List all the documents.
    hits = JsonDB.list_docs("traffic/hits")
    for date in sorted(hits):
        if date == "total": continue
        if not result["oldest"]:
            result["oldest"] = date

        # Get the DBs.
        hits_db = JsonDB.get("traffic/hits/{}".format(date), cache=False)
        uniq_db = JsonDB.get("traffic/unique/{}".format(date), cache=False)

        # Most we've seen?
        if hits_db["hits"] > result["most_hits"][1]:
            result["most_hits"] = [ date, hits_db["hits"] ]
        if len(uniq_db.keys()) > result["most_unique"][1]:
            result["most_unique"] = [ date, len(uniq_db.keys()) ]

        result["traffic"].append(dict(
            date=date,
            hits=hits_db["hits"],
            unique=len(uniq_db.keys()),
        ))

    return result


def get_referrers(recent=25):
    """Retrieve the referrer details. Returns results in this format:

    ```
    {
        referrers: [
            ["http://...", 20], # Pre-sorted by number of hits
        ],
        recent: [ recent list ]
    }
    ```
    """
    db = []
    if JsonDB.exists("traffic/referrers"):
        db = JsonDB.get("traffic/referrers", cache=False)

    # Count the links.
    unique = dict()
    for link in db:
        if not link in unique:
            unique[link] = 1
        else:
            unique[link] += 1

    # Sort them by popularity.
    result = dict(
        referrers=[],
        recent=[],
    )

    sorted_links = sorted(unique.keys(), key=lambda x: unique[x], reverse=True)
    for link in sorted_links:
        result["referrers"].append([ link, unique[link] ])

    recent = 0 - recent
    result["recent"] = db[recent:]
    result["recent"].reverse()

    return result
