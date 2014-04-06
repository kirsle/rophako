# -*- coding: utf-8 -*-

"""JSON flat file database system."""

import codecs
import os
import os.path
import glob
import re
from fcntl import flock, LOCK_EX, LOCK_SH, LOCK_UN
import redis
import json
import time

import config
from rophako.log import logger

redis_client = None
cache_lifetime = 60*60 # 1 hour


def get(document):
    """Get a specific document from the DB."""
    logger.debug("JsonDB: GET {}".format(document))

    # Exists?
    if not exists(document):
        logger.debug("Requested document doesn't exist")
        return None

    path = mkpath(document)
    stat = os.stat(path)

    # Do we have it cached?
    data = get_cache(document)
    if data:
        # Check if the cache is fresh.
        if stat.st_mtime > get_cache(document+"_mtime"):
            del_cache(document)
            del_cache(document+"_mtime")
        else:
            return data

    # Get the JSON data.
    data = read_json(path)

    # Cache and return it.
    set_cache(document, data, expires=cache_lifetime)
    set_cache(document+"_mtime", stat.st_mtime, expires=cache_lifetime)
    return data


def commit(document, data):
    """Insert/update a document in the DB."""

    # Need to create the file?
    path = mkpath(document)
    if not os.path.isfile(path):
        parts = path.split("/")
        parts.pop() # Remove the file part
        directory = list()

        # Create all the folders.
        for part in parts:
            directory.append(part)
            segment = "/".join(directory)
            if len(segment) > 0 and not os.path.isdir(segment):
                logger.debug("JsonDB: mkdir {}".format(segment))
                os.mkdir(segment, 0755)

    # Update the cached document.
    set_cache(document, data, expires=cache_lifetime)
    set_cache(document+"_mtime", time.time(), expires=cache_lifetime)

    # Write the JSON.
    write_json(path, data)


def delete(document):
    """Delete a document from the DB."""
    path = mkpath(document)
    if os.path.isfile(path):
        logger.info("Delete DB document: {}".format(path))
        os.unlink(path)


def exists(document):
    """Query whether a document exists."""
    path = mkpath(document)
    return os.path.isfile(path)


def list_docs(path):
    """List all the documents at the path."""
    path = mkpath("{}/*".format(path))
    docs = list()

    for item in glob.glob(path):
        name = re.sub(r'\.json$', '', item)
        name = name.split("/")[-1]
        docs.append(name)

    return docs


def mkpath(document):
    """Turn a DB path into a JSON file path."""
    if document.endswith(".json"):
        # Let's not do that.
        raise Exception("mkpath: document path already includes .json extension!")
    return "{}/{}.json".format(config.DB_ROOT, str(document))


def read_json(path):
    """Slurp, decode and return the data from a JSON document."""
    path = str(path)
    if not os.path.isfile(path):
        raise Exception("Can't read JSON file {}: file not found!".format(path))

    # Don't allow any fishy looking paths.
    if ".." in path:
        logger.error("ERROR: JsonDB tried to read a path with two dots: {}".format(path))
        raise Exception()

    # Open and lock the file.
    fh = codecs.open(path, 'r', 'utf-8')
    flock(fh, LOCK_SH)
    text = fh.read()
    flock(fh, LOCK_UN)
    fh.close()

    # Decode.
    try:
        data = json.loads(text)
    except:
        logger.error("Couldn't decode JSON data from {}".format(path))
        data = None

    return data


def write_json(path, data):
    """Write a JSON document."""
    path = str(path)

    # Don't allow any fishy looking paths.
    if ".." in path:
        logger.error("ERROR: JsonDB tried to write a path with two dots: {}".format(path))
        raise Exception()

    logger.debug("JsonDB: WRITE > {}".format(path))

    # Open and lock the file.
    fh = None
    if os.path.isfile(path):
        fh = codecs.open(path, 'r+', 'utf-8')
    else:
        fh = codecs.open(path, 'w', 'utf-8')
    flock(fh, LOCK_EX)

    # Write it.
    fh.truncate(0)
    fh.write(json.dumps(data, sort_keys=True, indent=4, separators=(',', ': ')))

    # Unlock and close.
    flock(fh, LOCK_UN)
    fh.close()


############################################################################
# Redis Caching Functions                                                  #
############################################################################

def get_redis():
    """Connect to Redis or return the existing connection."""
    global redis_client
    if not redis_client:
        redis_client = redis.StrictRedis(
            host = config.REDIS_HOST,
            port = config.REDIS_PORT,
            db   = config.REDIS_DB,
        )
    return redis_client


def set_cache(key, value, expires=None):
    """Set a key in the Redis cache."""
    key = config.REDIS_PREFIX + key
    try:
        client = get_redis()
        client.set(key, json.dumps(value))

        # Expiration date?
        if expires:
            client.expire(key, expires)
    except:
        logger.error("Redis exception: couldn't set_cache {}".format(key))


def get_cache(key):
    """Get a cached item."""
    key = config.REDIS_PREFIX + key
    value = None
    try:
        client = get_redis()
        value  = client.get(key)
        if value:
            value = json.loads(value)
    except:
        logger.warning("Redis exception: couldn't get_cache {}".format(key))
        value = None
    return value


def del_cache(key):
    """Delete a cached item."""
    key = config.REDIS_PREFIX + key
    client = get_redis()
    client.delete(key)