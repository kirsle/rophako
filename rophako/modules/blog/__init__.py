# -*- coding: utf-8 -*-
from __future__ import unicode_literals, absolute_import

"""Endpoints for the web blog."""

from flask import Blueprint, g, request, redirect, url_for, flash, make_response
import datetime
import time
import re
from xml.dom.minidom import Document

import rophako.model.user as User
import rophako.model.blog as Blog
import rophako.model.comment as Comment
import rophako.model.emoticons as Emoticons
from rophako.utils import (template, render_markdown, pretty_time,
    login_required, remote_addr)
from rophako.plugin import load_plugin
from rophako.settings import Config
from rophako.log import logger

import sys
if sys.version_info[0] > 2:
    def unicode(s):
        return str(s)

mod = Blueprint("blog", __name__, url_prefix="/blog")
load_plugin("rophako.modules.comment")

@mod.route("/")
def index():
    return template("blog/index.html")


@mod.route("/archive")
def archive():
    """List all blog posts over time on one page."""
    index = Blog.get_index()

    # Group by calendar month, and keep track of friendly versions of months.
    groups = dict()
    friendly_months = dict()
    for post_id, data in index.items():
        ts = datetime.datetime.fromtimestamp(data["time"])
        date = ts.strftime("%Y-%m")
        if not date in groups:
            groups[date] = dict()
            friendly = ts.strftime("%B %Y")
            friendly_months[date] = friendly

        # Get author's profile && Pretty-print the time.
        data["profile"] = User.get_user(uid=data["author"])
        data["pretty_time"] = pretty_time(Config.blog.time_format, data["time"])
        groups[date][post_id] = data

    # Sort by calendar month.
    sort_months = sorted(groups.keys(), reverse=True)

    # Prepare the results.
    result = list()
    for month in sort_months:
        data = dict(
            month=month,
            month_friendly=friendly_months[month],
            posts=list()
        )

        # Sort the posts by time created, descending.
        for post_id in sorted(groups[month].keys(), key=lambda x: groups[month][x]["time"], reverse=True):
            data["posts"].append(groups[month][post_id])

        result.append(data)

    g.info["archive"] = result
    return template("blog/archive.html")


@mod.route("/category/<category>")
def category(category):
    g.info["url_category"] = category
    return template("blog/index.html")

@mod.route("/drafts")
@login_required
def drafts():
    """View all of the draft blog posts."""
    return template("blog/drafts.html")

@mod.route("/private")
@login_required
def private():
    """View all of the blog posts marked as private."""
    return template("blog/private.html")

@mod.route("/entry/<fid>")
def entry(fid):
    """Endpoint to view a specific blog entry."""

    # Resolve the friendly ID to a real ID.
    post_id = Blog.resolve_id(fid, drafts=True)
    if not post_id:
        flash("That blog post wasn't found.")
        return redirect(url_for(".index"))

    # Look up the post.
    post = Blog.get_entry(post_id)
    post["post_id"] = post_id

    # Body has a snipped section?
    if "<snip>" in post["body"]:
        post["body"] = re.sub(r'\s*<snip>\s*', '\n\n', post["body"])

    # Render the body.
    if post["format"] == "markdown":
        post["rendered_body"] = render_markdown(post["body"])
    else:
        post["rendered_body"] = post["body"]

    # Render emoticons.
    if post["emoticons"]:
        post["rendered_body"] = Emoticons.render(post["rendered_body"])

    # Get the author's information.
    post["profile"] = User.get_user(uid=post["author"])
    post["photo"]   = User.get_picture(uid=post["author"])
    post["photo_url"] = Config.photo.root_public

    # Pretty-print the time.
    post["pretty_time"] = pretty_time(Config.blog.time_format, post["time"])

    # Count the comments for this post
    post["comment_count"] = Comment.count_comments("blog-{}".format(post_id))

    # Inject information about this post's siblings.
    index = Blog.get_index()
    siblings = [None, None] # previous, next
    sorted_ids = list(map(lambda y: int(y), sorted(index.keys(), key=lambda x: index[x]["time"], reverse=True)))
    for i in range(0, len(sorted_ids)):
        if sorted_ids[i] == post_id:
            # Found us!
            if i > 0:
                # We have an older post.
                siblings[0] = index[ str(sorted_ids[i-1]) ]
            if i < len(sorted_ids) - 1:
                # We have a newer post.
                siblings[1] = index[ str(sorted_ids[i+1]) ]
    post["siblings"] = siblings

    g.info["post"] = post
    return template("blog/entry.html")


@mod.route("/entry")
@mod.route("/index")
def dummy():
    return redirect(url_for(".index"))


@mod.route("/update", methods=["GET", "POST"])
@login_required
def update():
    """Post/edit a blog entry."""

    # Get our available avatars.
    g.info["avatars"] = Blog.list_avatars()
    g.info["userpic"] = User.get_picture(uid=g.info["session"]["uid"])

    # Default vars.
    g.info.update(dict(
        post_id="",
        fid="",
        author=g.info["session"]["uid"],
        subject="",
        body="",
        format="markdown",
        avatar="",
        categories="",
        privacy=Config.blog.default_privacy,
        sticky=False,
        emoticons=True,
        comments=Config.blog.allow_comments,
        preview=False,
    ))

    # Editing an existing post?
    post_id = request.args.get("id", None)
    if post_id:
        post_id = Blog.resolve_id(post_id, drafts=True)
        if post_id:
            logger.info("Editing existing blog post {}".format(post_id))
            post = Blog.get_entry(post_id)
            g.info["post_id"] = post_id
            g.info["post"] = post

            # Copy fields.
            for field in ["author", "fid", "subject", "time", "format",
                          "body", "avatar", "categories", "privacy",
                          "sticky", "emoticons", "comments"]:
                g.info[field] = post[field]

    # Are we SUBMITTING the form?
    if request.method == "POST":
        action = request.form.get("action")

        # Get all the fields from the posted params.
        g.info["post_id"] = request.form.get("id")
        for field in ["fid", "subject", "format", "body", "avatar", "categories", "privacy"]:
            g.info[field] = request.form.get(field)
        for boolean in ["sticky", "emoticons", "comments"]:
            g.info[boolean] = True if request.form.get(boolean, None) == "true" else False
        g.info["author"] = int(g.info["author"])

        # What action are they doing?
        if action == "preview":
            g.info["preview"] = True

            # Render markdown?
            if g.info["format"] == "markdown":
                g.info["rendered_body"] = render_markdown(g.info["body"])
            else:
                g.info["rendered_body"] = g.info["body"]

            # Render emoticons.
            if g.info["emoticons"]:
                g.info["rendered_body"] = Emoticons.render(g.info["rendered_body"])

        elif action == "publish":
            # Publishing! Validate inputs first.
            invalid = False
            if len(g.info["body"]) == 0:
                invalid = True
                flash("You must enter a body for your blog post.")
            if len(g.info["subject"]) == 0:
                invalid = True
                flash("You must enter a subject for your blog post.")

            # Resetting the post's time stamp?
            if not request.form.get("id") or request.form.get("reset-time"):
                g.info["time"] = float(time.time())
            else:
                g.info["time"] = float(request.form.get("time", time.time()))

            # Format the categories.
            tags = []
            for tag in g.info["categories"].split(","):
                tags.append(tag.strip())

            # Okay to update?
            if invalid is False:
                new_id, new_fid = Blog.post_entry(
                    post_id    = g.info["post_id"],
                    epoch      = g.info["time"],
                    author     = g.info["author"],
                    subject    = g.info["subject"],
                    fid        = g.info["fid"],
                    avatar     = g.info["avatar"],
                    categories = tags,
                    privacy    = g.info["privacy"],
                    ip         = remote_addr(),
                    emoticons  = g.info["emoticons"],
                    sticky     = g.info["sticky"],
                    comments   = g.info["comments"],
                    format     = g.info["format"],
                    body       = g.info["body"],
                )

                return redirect(url_for(".entry", fid=new_fid))


    if type(g.info["categories"]) is list:
        g.info["categories"] = ", ".join(g.info["categories"])

    return template("blog/update.html")


@mod.route("/delete", methods=["GET", "POST"])
@login_required
def delete():
    """Delete a blog post."""
    post_id = request.args.get("id")

    # Resolve the post ID.
    post_id = Blog.resolve_id(post_id, drafts=True)
    if not post_id:
        flash("That blog post wasn't found.")
        return redirect(url_for(".index"))

    if request.method == "POST":
        confirm = request.form.get("confirm")
        if confirm == "true":
            Blog.delete_entry(post_id)
            flash("The blog entry has been deleted.")
            return redirect(url_for(".index"))

    # Get the entry's subject.
    post = Blog.get_entry(post_id)
    g.info["subject"] = post["subject"]
    g.info["post_id"] = post_id

    return template("blog/delete.html")


@mod.route("/rss")
def rss():
    """RSS feed for the blog."""
    doc = Document()

    rss = doc.createElement("rss")
    rss.setAttribute("version", "2.0")
    rss.setAttribute("xmlns:blogChannel", "http://backend.userland.com/blogChannelModule")
    doc.appendChild(rss)

    channel = doc.createElement("channel")
    rss.appendChild(channel)

    rss_time = "%a, %d %b %Y %H:%M:%S GMT"

    ######
    ## Channel Information
    ######

    today = time.strftime(rss_time, time.gmtime())

    xml_add_text_tags(doc, channel, [
        ["title", Config.blog.title],
        ["link", Config.blog.link],
        ["description", Config.blog.description],
        ["language", Config.blog.language],
        ["copyright", Config.blog.copyright],
        ["pubDate", today],
        ["lastBuildDate", today],
        ["webmaster", Config.blog.webmaster],
    ])

    ######
    ## Image Information
    ######

    image = doc.createElement("image")
    channel.appendChild(image)
    xml_add_text_tags(doc, image, [
        ["title", Config.blog.image_title],
        ["url", Config.blog.image_url],
        ["link", Config.blog.link],
        ["width", Config.blog.image_width],
        ["height", Config.blog.image_height],
        ["description", Config.blog.image_description],
    ])

    ######
    ## Add the blog posts
    ######

    index = Blog.get_index()
    posts = get_index_posts(index)
    for post_id in posts[:int(Config.blog.entries_per_feed)]:
        post = Blog.get_entry(post_id)
        item = doc.createElement("item")
        channel.appendChild(item)

        # Render the body.
        if post["format"] == "markdown":
            post["rendered_body"] = render_markdown(post["body"])
        else:
            post["rendered_body"] = post["body"]

        # Render emoticons.
        if post["emoticons"]:
            post["rendered_body"] = Emoticons.render(post["rendered_body"])

        xml_add_text_tags(doc, item, [
            ["title", post["subject"]],
            ["link", url_for("blog.entry", fid=post["fid"], _external=True)],
            ["description", post["rendered_body"]],
            ["pubDate", time.strftime(rss_time, time.gmtime(post["time"]))],
        ])

    resp = make_response(doc.toprettyxml(encoding="utf-8"))
    resp.headers["Content-Type"] = "application/rss+xml; charset=utf-8"
    return resp


def xml_add_text_tags(doc, root_node, tags):
    """RSS feed helper function.

    Add a collection of simple tag/text pairs to a root XML element."""
    for pair in tags:
        name, value = pair
        channelTag = doc.createElement(name)
        channelTag.appendChild(doc.createTextNode(unicode(value)))
        root_node.appendChild(channelTag)


def partial_index(template_name="blog/index.inc.html", mode="normal"):
    """Partial template for including the index view of the blog.

    Args:
        template_name (str): The name of the template to be rendered.
        mode (str): The view mode of the posts, one of:
            - normal: Only list public entries, or private posts for users
                who are logged in.
            - drafts: Only list draft entries for logged-in users.
    """

    # Get the blog index.
    if mode == "normal":
        index = Blog.get_index()
    elif mode == "drafts":
        index = Blog.get_drafts()
    elif mode == "private":
        index = Blog.get_private()
    else:
        return "Invalid partial_index mode."

    # Let the pages know what mode they're in.
    g.info["mode"] = mode

    pool  = {} # The set of blog posts to show.

    category = g.info.get("url_category", None)
    if category == Config.blog.default_category:
        category = ""

    # Are we narrowing by category?
    if category is not None:
        # Narrow down the index to just those that match the category.
        for post_id, data in index.items():
            if not category in data["categories"]:
                continue
            pool[post_id] = data

        # No such category?
        if len(pool) == 0:
            flash("There are no posts with that category.")
            return redirect(url_for(".index"))
    else:
        pool = index

    # Get the posts we want.
    posts = get_index_posts(pool)

    # Handle pagination.
    offset = request.args.get("skip", 0)
    try:    offset = int(offset)
    except: offset = 0

    # Handle the offsets, and get those for the "older" and "earlier" posts.
    # "earlier" posts count down (towards index 0), "older" counts up.
    g.info["offset"]  = offset
    g.info["earlier"] = offset - int(Config.blog.entries_per_page) if offset > 0 else 0
    g.info["older"]   = offset + int(Config.blog.entries_per_page)
    if g.info["earlier"] < 0:
        g.info["earlier"] = 0
    if g.info["older"] < 0 or g.info["older"] > len(posts) - 1:
        g.info["older"] = 0
    g.info["count"] = 0

    # Can we go to other pages?
    g.info["can_earlier"] = True if offset > 0 else False
    g.info["can_older"]   = False if g.info["older"] == 0 else True

    # Load the selected posts.
    selected = []
    stop = offset + int(Config.blog.entries_per_page)
    if stop > len(posts): stop = len(posts)
    index = 1 # Let each post know its position on-page.
    for i in range(offset, stop):
        post_id = posts[i]
        post    = Blog.get_entry(post_id)

        post["post_id"] = post_id

        # Body has a snipped section?
        if "<snip>" in post["body"]:
            post["body"] = post["body"].split("<snip>")[0]
            post["snipped"] = True

        # Render the body.
        if post["format"] == "markdown":
            post["rendered_body"] = render_markdown(post["body"])
        else:
            post["rendered_body"] = post["body"]

        # Render emoticons.
        if post["emoticons"]:
            post["rendered_body"] = Emoticons.render(post["rendered_body"])

        # Get the author's information.
        post["profile"] = User.get_user(uid=post["author"])
        post["photo"]   = User.get_picture(uid=post["author"])
        post["photo_url"] = Config.photo.root_public

        post["pretty_time"] = pretty_time(Config.blog.time_format, post["time"])

        # Count the comments for this post
        post["comment_count"] = Comment.count_comments("blog-{}".format(post_id))
        post["position_index"] = index
        index += 1

        selected.append(post)
        g.info["count"] += 1

    g.info["category"] = category
    g.info["posts"] = selected

    return template(template_name)


def get_index_posts(index):
    """Helper function to get data for the blog index page."""
    # Separate the sticky posts from the normal ones.
    sticky, normal = set(), set()
    for post_id, data in index.items():
        if data["sticky"]:
            sticky.add(post_id)
        else:
            normal.add(post_id)

    # Sort the blog IDs by published time.
    posts = []
    posts.extend(sorted(sticky, key=lambda x: index[x]["time"], reverse=True))
    posts.extend(sorted(normal, key=lambda x: index[x]["time"], reverse=True))
    return posts

def partial_tags():
    """Get a listing of tags and their quantities for the nav bar."""
    tags = Blog.get_categories()

    # Sort the tags by popularity.
    sort_tags = [ tag for tag in sorted(tags.keys(), key=lambda y: tags[y], reverse=True) ]
    result = []
    has_small = False
    for tag in sort_tags:
        result.append(dict(
            category=tag if len(tag) else Config.blog.default_category,
            count=tags[tag],
            small=tags[tag] < 3, # TODO: make this configurable
        ))
        if tags[tag] < 3:
            has_small = True

    g.info["tags"] = result
    g.info["has_small"] = has_small
    return template("blog/categories.inc.html")
