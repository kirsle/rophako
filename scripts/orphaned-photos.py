#!/usr/bin/env python

"""Locate any orphaned photos.

Usage: scripts/orphaned-photos.py <path/to/db> <path/to/static/photos>"""

import sys
import os
import codecs
import json
import glob

sys.path.append(".")
import rophako.jsondb as JsonDB

def main():
    if len(sys.argv) == 1:
        print "Usage: {} <path/to/static/photos>".format(__file__)
        sys.exit(1)

    photo_root = sys.argv[1]

    db = JsonDB.get("photos/index")
    photos = set()
    for album in db["albums"]:
        for key, data in db["albums"][album].iteritems():
            for img in ["large", "thumb", "avatar"]:
                photos.add(data[img])

    # Get all the images and compare.
    for img in glob.glob("{}/*.*".format(photo_root)):
        fname = img.split("/")[-1]
        if not fname in photos:
            print "Orphan:", fname

if __name__ == "__main__":
    main()