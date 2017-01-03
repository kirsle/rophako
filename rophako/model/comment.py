# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

"""Commenting models."""

from flask import url_for, session
from itsdangerous import URLSafeSerializer
import time
import hashlib
import urllib
import random
import sys
import uuid

from rophako.settings import Config
import rophako.jsondb as JsonDB
import rophako.model.user as User
import rophako.model.emoticons as Emoticons
from rophako.utils import send_email, render_markdown
from rophako.log import logger

def deletion_token():
    """Retrieves the comment deletion token for the current user's session.

    Deletion tokens are random strings saved with a comment's data that allows
    its original commenter to delete or modify their comment on their own,
    within a window of time configurable by the site owner
    (in ``comment.edit_period``).

    If the current session doesn't have a deletion token yet, this function
    will generate and set one. Otherwise it returns the one set last time.
    All comments posted by the same session would share the same deletion
    token.
    """
    if not "comment_token" in session:
        session["comment_token"] = str(uuid.uuid4())
    return session.get("comment_token")


def add_comment(thread, uid, name, subject, message, url, time, ip,
    token=None, image=None):
    """Add a comment to a comment thread.

    Parameters:
        thread (str): the unique comment thread name.
        uid (int): 0 for guest posts, otherwise the UID of the logged-in user.
        name (str): the commenter's name (if a guest)
        subject (str)
        message (str)
        url (str): the URL where the comment can be read (i.e. the blog post)
        time (int): epoch time of the comment.
        ip (str): the user's IP address.
        token (str): the user's session's comment deletion token.
        image (str): the URL to a Gravatar image, if any.
    """

    # Get the comments for this thread.
    comments = get_comments(thread)

    # Make up a unique ID for the comment.
    cid = random_hash()
    while cid in comments:
        cid = random_hash()

    # Add the comment.
    comments[cid] = dict(
        uid=uid,
        name=name or "Anonymous",
        image=image or "",
        message=message,
        time=time or int(time.time()),
        ip=ip,
        token=token,
    )
    write_comments(thread, comments)

    # Get info about the commenter.
    if uid > 0:
        user = User.get_user(uid=uid)
        if user:
            name = user["name"]

    # Send the e-mail to the site admins.
    send_email(
        to=Config.site.notify_address,
        subject="Comment Added: {}".format(subject),
        message="""{name} has left a comment on: {subject}

{message}

-----

To view this comment, please go to <{url}>

Was this comment spam? [Delete it]({deletion_link}).""".format(
            name=name,
            subject=subject,
            message=message,
            url=url,
            deletion_link=url_for("comment.quick_delete",
                token=make_quick_delete_token(thread, cid),
                url=url,
                _external=True,
            )
        ),
    )

    # Notify any subscribers.
    subs = get_subscribers(thread)
    for sub in subs.keys():
        # Make the unsubscribe link.
        unsub = url_for("comment.unsubscribe", thread=thread, who=sub, _external=True)

        send_email(
            to=sub,
            subject="New Comment: {}".format(subject),
            message="""Hello,

{name} has left a comment on: {subject}

{message}

-----

To view this comment, please go to <{url}>""".format(
                thread=thread,
                name=name,
                subject=subject,
                message=message,
                url=url,
                unsub=unsub,
            ),
            footer="You received this e-mail because you subscribed to the "
                "comment thread that this comment was added to. You may "
                "[**unsubscribe**]({unsub}) if you like.".format(
                unsub=unsub,
            ),
        )


def get_comment(thread, cid):
    """Look up a specific comment."""
    comments = get_comments(thread)
    return comments.get(cid, None)


def update_comment(thread, cid, data):
    """Update the data for a comment."""
    comments = get_comments(thread)
    if cid in comments:
        comments[cid].update(data)
        write_comments(thread, comments)


def delete_comment(thread, cid):
    """Delete a comment from a thread."""
    comments = get_comments(thread)
    del comments[cid]
    write_comments(thread, comments)


def make_quick_delete_token(thread, cid):
    """Generate a unique tamper-proof token for quickly deleting comments.

    This allows for an instant 'delete' link to be included in the notification
    e-mail sent to the site admins, to delete obviously spammy comments
    quickly.

    It uses ``itsdangerous`` to create a unique token signed by the site's
    secret key so that users can't forge their own tokens.

    Parameters:
        thread (str): comment thread name.
        cid (str): unique comment ID.

    Returns:
        str
    """
    s = URLSafeSerializer(Config.security.secret_key)
    return s.dumps(dict(
        t=thread,
        c=cid,
    ))


def validate_quick_delete_token(token):
    """Validate and decode a quick delete token.

    If the token is valid, returns a dict of the thread name and comment ID,
    as keys ``t`` and ``c`` respectively.

    If not valid, returns ``None``.
    """
    s = URLSafeSerializer(Config.security.secret_key)
    try:
        return s.loads(token)
    except:
        logger.exception("Failed to validate quick-delete token {}".format(token))
        return None


def is_editable(thread, cid, comment=None):
    """Determine if the comment is editable by the end user.

    A comment is editable to its own author (even guests) for a window defined
    by the site owner. In this event, the user's session has their
    'comment deletion token' that matches the comment's saved token, and the
    comment was posted recently.

    Site admins (any logged-in user) can always edit all comments.

    Parameters:
        thread (str): the unique comment thread name.
        cid (str): the comment ID.
        comment (dict): if you already have the comment object, you can provide
            it here and save an extra DB lookup.

    Returns:
        bool: True if the user is logged in *OR* has a valid deletion token and
            the comment is relatively new. Otherwise returns False.
    """
    # Logged in users can always do it.
    if session["login"]:
        return True

    # Get the comment, or bail if not found.
    if comment is None:
        comment = get_comment(thread, cid)
        if not comment:
            return False

    # Make sure the comment's token matches the user's, or bail.
    if comment.get("token", "x") != deletion_token():
        return False

    # And finally, make sure the comment is new enough.
    return time.time() - comment["time"] < 60*60*Config.comment.edit_period


def count_comments(thread):
    """Count the comments on a thread."""
    comments = get_comments(thread)
    return len(comments.keys())


def add_subscriber(thread, email):
    """Add a subscriber to a thread."""
    if not "@" in email:
        return

    # Sanity check: only subscribe to threads that exist.
    if not JsonDB.exists("comments/threads/{}".format(thread)):
        return

    logger.info("Subscribe e-mail {} to thread {}".format(email, thread))
    subs = get_subscribers(thread)
    subs[email] = int(time.time())
    write_subscribers(thread, subs)


def unsubscribe(thread, email):
    """Unsubscribe an e-mail address from a thread.

    If `thread` is `*`, the e-mail is unsubscribed from all threads."""

    # Which threads to unsubscribe from?
    threads = []
    if thread == "*":
        threads = JsonDB.list_docs("comments/subscribers")
    else:
        threads = [thread]

    # Remove them as a subscriber.
    for thread in threads:
        if JsonDB.exists("comments/subscribers/{}".format(thread)):
            logger.info("Unsubscribe e-mail address {} from comment thread {}".format(email, thread))
            db = get_subscribers(thread)
            del db[email]
            write_subscribers(thread, db)


def format_message(message):
    """HTML sanitize the message and format it for display."""

    # Comments use Markdown formatting, and HTML tags are escaped by default.
    message = render_markdown(message)

    # Process emoticons.
    message = Emoticons.render(message)
    return message


def get_comments(thread):
    """Get the comment thread."""
    doc = "comments/threads/{}".format(thread)
    if JsonDB.exists(doc):
        return JsonDB.get(doc)
    return {}


def write_comments(thread, comments):
    """Save the comments DB."""
    if len(comments.keys()) == 0:
        return JsonDB.delete("comments/threads/{}".format(thread))
    return JsonDB.commit("comments/threads/{}".format(thread), comments)


def get_subscribers(thread):
    """Get the subscribers to a comment thread."""
    doc = "comments/subscribers/{}".format(thread)
    if JsonDB.exists(doc):
        return JsonDB.get(doc)
    return {}


def write_subscribers(thread, subs):
    """Save the subscribers to the DB."""
    if len(subs.keys()) == 0:
        return JsonDB.delete("comments/subscribers/{}".format(thread))
    return JsonDB.commit("comments/subscribers/{}".format(thread), subs)


def random_hash():
    """Get a short random hash to use as the ID for a comment."""
    md5 = hashlib.md5()
    md5.update(str(random.randint(0, 1000000)).encode("utf-8"))
    return md5.hexdigest()


def gravatar(email):
    """Generate a Gravatar link for an email address."""
    if "@" in email:
        # Default avatar?
        default = Config.comment.default_avatar

        # Construct the URL.
        params = {
            "s": "96", # size
        }
        if default:
            params["d"] = default
        url = "//www.gravatar.com/avatar/" + hashlib.md5(email.lower().encode("utf-8")).hexdigest() + "?"

        # URL encode the params, the Python 2 & Python 3 way.
        if sys.version_info[0] < 3:
            url += urllib.urlencode(params)
        else:
            url += urllib.parse.urlencode(params)

        return url
    return ""
