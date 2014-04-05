# -*- coding: utf-8 -*-

"""User account models."""

import bcrypt
import time

import config
import rophako.jsondb as JsonDB
import rophako.model.photo as Photo
from rophako.log import logger

def create(username, password, name=None, uid=None, role="user"):
    """Create a new user account.

    Returns the user ID number assigned to this user."""
    # Name defaults to username.
    if name is None:
        name = username

    username = username.lower()

    # Provided with a user ID?
    if uid is not None:
        # See if it's available.
        if exists(uid=uid):
            logger.warning("Wanted to use UID {} for user {} but it wasn't available.".format(uid, username))
            uid = None

    # Need to generate a UID?
    if uid is None:
        uid = get_next_uid()

    uid = int(uid)

    # Username musn't exist.
    if exists(username):
        # The front-end shouldn't let this happen.
        raise Exception("Can't create username {}: already exists!".format(username))

    # Crypt their password.
    hashedpass = hash_password(password)

    logger.info("Create user {} with username {}".format(uid, username))

    # Create the user file.
    JsonDB.commit("users/by-id/{}".format(uid), dict(
        uid=uid,
        username=username,
        name=name,
        picture="",
        role=role,
        password=hashedpass,
        created=time.time(),
    ))

    # And their username to ID map.
    JsonDB.commit("users/by-name/{}".format(username), dict(
        uid=uid,
    ))

    return uid


def update_user(uid, data):
    """Update the user's data."""
    if not exists(uid=uid):
        raise Exception("Can't update user {}: doesn't exist!".format(uid))

    db = get_user(uid=uid)

    # Change of username?
    if "username" in data and len(data["username"]) and data["username"] != db["username"]:
        JsonDB.delete("users/by-name/{}".format(db["username"]))
        JsonDB.commit("users/by-name/{}".format(data["username"]), dict(
            uid=int(uid),
        ))

    db.update(data)
    JsonDB.commit("users/by-id/{}".format(uid), db)


def delete_user(uid):
    """Delete a user account."""
    if not exists(uid=uid):
        return

    db = get_user(uid=uid)
    username = db["username"]

    # Mark the account deleted.
    update_user(uid, dict(
        username="",
        name="",
        role="deleted",
        password="!",
    ))

    # Delete their username.
    JsonDB.delete("users/by-name/{}".format(username))


def list_users():
    """Get a sorted list of all users."""
    uids  = JsonDB.list_docs("users/by-id")
    users = list()
    for uid in sorted(map(lambda x: int(x), uids)):
        db = get_user(uid=uid)
        if db["role"] == "deleted": continue
        users.append(db)
    return users


def get_uid(username):
    """Turn a username into a user ID."""
    db = JsonDB.get("users/by-name/{}".format(username))
    if db:
        return int(db["uid"])
    return None


def get_user(uid=None, username=None):
    """Get a user's DB file, or None if not found."""
    if username:
        uid = get_uid(username)
        logger.debug("get_user: resolved username {} to UID {}".format(username, uid))
    return JsonDB.get("users/by-id/{}".format(uid))


def get_picture(uid):
    """Get the chosen profile photo for the user."""
    data = get_user(uid=uid)
    pic = data["picture"]
    if len(pic):
        photo = Photo.get_photo(pic)
        if photo:
            return photo["avatar"]
    return None


def exists(uid=None, username=None):
    """Query whether a user ID or name exists."""
    if uid:
        return JsonDB.exists("users/by-id/{}".format(uid))
    elif username:
        return JsonDB.exists("users/by-name/{}".format(username.lower()))


def hash_password(password):
    return bcrypt.hashpw(str(password), bcrypt.gensalt(config.BCRYPT_ITERATIONS))


def check_auth(username, password):
    """Check the authentication credentials for the username and password.

    Returns a boolean true or false. On error, an error is logged."""
    # Check if the username exists.
    if not exists(username=username):
        logger.error("User authentication failed: username {} not found!".format(username))
        return False

    # Get the user's file.
    db = get_user(username=username)
    print db

    # Check the password.
    return bcrypt.hashpw(str(password), str(db["password"])) == db["password"]


def get_next_uid():
    """Get the next available user ID."""
    uid = 1
    while exists(uid=uid):
        uid += 1
    return uid