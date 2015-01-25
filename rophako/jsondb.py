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

from rophako.settings import Config
from rophako.utils import handle_exception
from rophako.log import logger

redis_client = None
cache_lifetime = 60*60 # 1 hour


def get(document, cache=True):
    """Get a specific document from the DB."""
    logger.debug("JsonDB: GET {}".format(document))

    # Exists?
    if not exists(document):
        logger.debug("Requested document doesn't exist")
        return None

    path = mkpath(document)
    stat = os.stat(path)

    # Do we have it cached?
    data = get_cache(document) if cache else None
    if data:
        # Check if the cache is fresh.
        if stat.st_mtime > get_cache(document+"_mtime"):
            del_cache(document)
            del_cache(document+"_mtime")
        else:
            return data

    # Get a lock for reading.
    lock = lock_cache(document)

    # Get the JSON data.
    data = read_json(path)

    # Unlock!
    unlock_cache(lock)

    # Cache and return it.
    if cache:
        set_cache(document, data, expires=cache_lifetime)
        set_cache(document+"_mtime", stat.st_mtime, expires=cache_lifetime)

    return data


def commit(document, data, cache=True):
    """Insert/update a document in the DB."""

    # Only allow one commit at a time.
    lock = lock_cache(document)

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
                os.mkdir(segment, 0o755)

    # Write the JSON.
    write_json(path, data)

    # Update the cached document.
    if cache:
        set_cache(document, data, expires=cache_lifetime)
        set_cache(document+"_mtime", time.time(), expires=cache_lifetime)

    # Release the lock.
    unlock_cache(lock)


def delete(document):
    """Delete a document from the DB."""
    path = mkpath(document)
    if os.path.isfile(path):
        logger.info("Delete DB document: {}".format(path))
        os.unlink(path)
        del_cache(document)


def exists(document):
    """Query whether a document exists."""
    path = mkpath(document)
    return os.path.isfile(path)


def list_docs(path, recursive=False):
    """List all the documents at the path."""
    root = os.path.join(Config.db.db_root, path)
    docs = list()

    for item in sorted(os.listdir(root)):
        target = os.path.join(root, item)
        db_path = os.path.join(path, item)

        # Descend into subdirectories?
        if os.path.isdir(target):
            if recursive:
                docs += [
                    os.path.join(item, name) for name in list_docs(db_path)
                ]
            else:
                continue

        if target.endswith(".json"):
            name = re.sub(r'\.json$', '', item)
            docs.append(name)

    return docs


def mkpath(document):
    """Turn a DB path into a JSON file path."""
    if document.endswith(".json"):
        # Let's not do that.
        raise Exception("mkpath: document path already includes .json extension!")
    return "{}/{}.json".format(Config.db.db_root, str(document))


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
        handle_exception(Exception("Couldn't decode JSON from {}\n{}".format(
            path,
            text,
        )))
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
    fh = codecs.open(path, 'w', 'utf-8')
    flock(fh, LOCK_EX)

    # Write it.
    fh.write(json.dumps(data, sort_keys=True, indent=4, separators=(',', ': ')))

    # Unlock and close.
    flock(fh, LOCK_UN)
    fh.close()


############################################################################
# Redis Caching Functions                                                  #
############################################################################

disable_redis = False
def get_redis():
    """Connect to Redis or return the existing connection."""
    global redis_client
    global disable_redis

    if not redis_client and not disable_redis:
        try:
            redis_client = redis.StrictRedis(
                host = Config.db.redis_host,
                port = Config.db.redis_port,
                db   = Config.db.redis_db,
            )
            redis_client.ping()
        except Exception as e:
            logger.error("Couldn't connect to Redis; memory caching will be disabled! {}".format(e.message))
            redis_client  = None
            disable_redis = True
    return redis_client


def set_cache(key, value, expires=None):
    """Set a key in the Redis cache."""
    key = Config.db.redis_prefix + key
    client = get_redis()
    if not client:
        return

    try:
        client.set(key, json.dumps(value))

        # Expiration date?
        if expires:
            client.expire(key, expires)
    except:
        logger.error("Redis exception: couldn't set_cache {}".format(key))


def get_cache(key):
    """Get a cached item."""
    key = Config.db.redis_prefix + key
    value = None
    client = get_redis()
    if not client:
        return

    try:
        value  = client.get(key)
        if value:
            value = json.loads(value)
    except:
        logger.warning("Redis exception: couldn't get_cache {}".format(key))
        value = None
    return value


def del_cache(key):
    """Delete a cached item."""
    key = Config.db.redis_prefix + key
    client = get_redis()
    if not client:
        return
    client.delete(key)


def lock_cache(key, timeout=5, expire=20):
    """Cache level 'file locking' implementation.

    The `key` will be automatically suffixed with `_lock`.
    The `timeout` is the max amount of time to wait for a lock.
    The `expire` is how long a lock may exist before it's considered stale.

    Returns True on success, None on failure to acquire lock."""
    client = get_redis()
    if not client:
        return

    # Take the lock.
    lock = client.lock(key, timeout=expire)
    lock.acquire()
    logger.debug("Cache lock acquired: {}, expires in {}s".format(key, expire))
    return lock


def unlock_cache(lock):
    """Release the lock on a cache key."""
    if lock:
        lock.release()
        logger.debug("Cache lock released")
