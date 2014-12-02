# -*- coding: utf-8 -*-

"""Visitor tracking models."""

import time
import requests

import rophako.jsondb as JsonDB
from rophako.utils import remote_addr, pretty_time, server_name

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
    if link.startswith(request.url_root):
        print "Referrer is same host!"
        return None

    # See if the URL really links back to us.
    hostname = server_name()
    r = requests.get(link)
    if hostname in r.text:
        # Log it.
        db = list()
        if JsonDB.exists("traffic/referrers"):
            # Don't cache the result -- the list can get huge!
            db = JsonDB.get("traffic/referrers", cache=False)
        db.append(link)
        JsonDB.commit("traffic/referrers", db, cache=False)
        return link

    return None


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

    return result
