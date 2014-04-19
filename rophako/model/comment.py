# -*- coding: utf-8 -*-

"""Commenting models."""

from flask import g, url_for
import time
import hashlib
import urllib
import random
import re

import config
import rophako.jsondb as JsonDB
import rophako.model.user as User
import rophako.model.emoticons as Emoticons
from rophako.utils import send_email, render_markdown
from rophako.log import logger


def add_comment(thread, uid, name, subject, message, url, time, ip, image=None):
    """Add a comment to a comment thread.

    * uid is 0 if it's a guest post, otherwise the UID of the user.
    * name is the commenter's name (if a guest)
    * subject is for the e-mails that are sent out
    * message is self explanatory.
    * url is the URL where the comment can be read.
    * time, epoch time of comment.
    * ip is the IP address of the commenter.
    * image is a Gravatar image URL etc.
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
    )
    write_comments(thread, comments)

    # Get info about the commenter.
    if uid > 0:
        user = User.get_user(uid=uid)
        if user:
            name = user["name"]

    # Send the e-mail to the site admins.
    send_email(
        to=config.NOTIFY_ADDRESS,
        subject="New comment: {}".format(subject),
        message="""{name} has left a comment on: {subject}

{message}

To view this comment, please go to {url}

=====================

This e-mail was automatically generated. Do not reply to it.""".format(
            name=name,
            subject=subject,
            message=message,
            url=url,
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

You are currently subscribed to the comment thread '{thread}', and somebody has
just added a new comment!

{name} has left a comment on: {subject}

{message}

To view this comment, please go to {url}

=====================

This e-mail was automatically generated. Do not reply to it.

If you wish to unsubscribe from this comment thread, please visit the following
URL: {unsub}""".format(
                thread=thread,
                name=name,
                subject=subject,
                message=message,
                url=url,
                unsub=unsub,
            )
        )


def delete_comment(thread, cid):
    """Delete a comment from a thread."""
    comments = get_comments(thread)
    del comments[cid]
    write_comments(thread, comments)


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

    # Don't allow commenters to use images.
    message = re.sub(r'<img.+?/>', '', message)

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
    md5.update(str(random.randint(0, 1000000)))
    return md5.hexdigest()


def gravatar(email):
    """Generate a Gravatar link for an email address."""
    if "@" in email:
        # Default avatar?
        default = config.COMMENT_DEFAULT_AVATAR

        # Construct the URL.
        params = {
            "s": "96", # size
        }
        if default:
            params["d"] = default
        url = "//www.gravatar.com/avatar/" + hashlib.md5(email.lower()).hexdigest() + "?"
        url += urllib.urlencode(params)
        return url
    return ""
