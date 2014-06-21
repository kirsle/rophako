# -*- coding: utf-8 -*-

"""Endpoints for the photo albums."""

from flask import Blueprint, g, request, redirect, url_for, session, flash

import rophako.model.user as User
import rophako.model.photo as Photo
from rophako.utils import template, pretty_time, login_required, ajax_response
from rophako.log import logger
from config import *

mod = Blueprint("photo", __name__, url_prefix="/photos")

@mod.route("/")
def index():
    return redirect(url_for(".albums"))


@mod.route("/albums")
def albums():
    """View the index of the photo albums."""
    albums = Photo.list_albums()

    # If there's only one album, jump directly to that one.
    if len(albums) == 1:
        return redirect(url_for(".album_index", name=albums[0]["name"]))

    g.info["albums"] = albums
    return template("photos/albums.html")


@mod.route("/album/<name>")
def album_index(name):
    """View the photos inside an album."""
    photos = Photo.list_photos(name)
    if photos is None:
        flash("That album doesn't exist.")
        return redirect(url_for(".albums"))

    g.info["album"]  = name
    g.info["photos"] = photos
    return template("photos/album.html")


@mod.route("/view/<key>")
def view_photo(key):
    """View a specific photo."""
    photo = Photo.get_photo(key)
    if photo is None:
        flash("That photo wasn't found!")
        return redirect(url_for(".albums"))

    # Get the author info.
    author = User.get_user(uid=photo["author"])
    if author:
        g.info["author"] = author

    g.info["photo"] = photo
    g.info["photo"]["key"] = key
    g.info["photo"]["pretty_time"] = pretty_time(PHOTO_TIME_FORMAT, photo["uploaded"])
    return template("photos/view.html")


@mod.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """Upload a photo."""

    if request.method == "POST":
        # We're posting the upload.

        # Is this an ajax post or a direct post?
        is_ajax = request.form.get("__ajax", "false") == "true"

        # Album name.
        album = request.form.get("album") or request.form.get("new-album")

        # What source is the pic from?
        result = None
        location = request.form.get("location")
        if location == "pc":
            # An upload from the PC.
            result = Photo.upload_from_pc(request)
        elif location == "www":
            # An upload from the Internet.
            result = Photo.upload_from_www(request.form)
        else:
            flash("Stop messing around.")
            return redirect(url_for(".upload"))

        # How'd it go?
        if result["success"] is not True:
            if is_ajax:
                return ajax_response(False, result["error"])
            else:
                flash("The upload has failed: {}".format(result["error"]))
                return redirect(url_for(".upload"))

        # Good!
        if is_ajax:
            # Was it a multiple upload?
            if result.get("multi"):
                return ajax_response(True, url_for(".album_index", name=album))
            else:
                return ajax_response(True, url_for(".crop", photo=result["photo"]))
        else:
            if result["multi"]:
                return redirect(url_for(".album_index", name=album))
            else:
                return redirect(url_for(".crop", photo=result["photo"]))

    # Get the list of available albums.
    g.info["album_list"] = [
        "My Photos", # the default
    ]
    g.info["selected"] = PHOTO_DEFAULT_ALBUM
    albums = Photo.list_albums()
    if len(albums):
        g.info["album_list"] = [ album["name"] for album in albums ]
        g.info["selected"] = albums[0]

    return template("photos/upload.html")


@mod.route("/crop/<photo>", methods=["GET", "POST"])
@login_required
def crop(photo):
    pic = Photo.get_photo(photo)
    if not pic:
        flash("The photo you want to crop wasn't found!")
        return redirect(url_for(".albums"))

    # Saving?
    if request.method == "POST":
        try:
            x      = int(request.form.get("x", 0))
            y      = int(request.form.get("y", 0))
            length = int(request.form.get("length", 0))
        except:
            flash("Error with form inputs.")
            return redirect(url_for(".crop", photo=photo))

        # Re-crop the photo!
        Photo.crop_photo(photo, x, y, length)
        flash("The photo has been cropped!")
        return redirect(url_for(".albums")) # TODO go to photo

    # Get the photo's true size.
    true_width, true_height = Photo.get_image_dimensions(pic)
    g.info["true_width"] = true_width
    g.info["true_height"] = true_height
    g.info["photo"] = photo
    g.info["preview"] = pic["large"]
    return template("photos/crop.html")


@mod.route("/set_cover/<album>/<key>")
@login_required
def set_cover(album, key):
    """Set the pic as the album cover."""
    pic = Photo.get_photo(key)
    if not pic:
        flash("The photo you want to crop wasn't found!")
        return redirect(url_for(".albums"))

    Photo.set_album_cover(album, key)
    flash("Album cover has been set.")
    return redirect(url_for(".albums"))


@mod.route("/set_profile/<key>")
@login_required
def set_profile(key):
    """Set the pic as your profile picture."""
    pic = Photo.get_photo(key)
    if not pic:
        flash("The photo wasn't found!")
        return redirect(url_for(".albums"))

    uid = g.info["session"]["uid"]
    User.update_user(uid, dict(picture=key))
    flash("Your profile picture has been updated.")
    return redirect(url_for(".view_photo", key=key))


@mod.route("/edit/<key>", methods=["GET", "POST"])
@login_required
def edit(key):
    """Edit a photo."""
    pic = Photo.get_photo(key)
    if not pic:
        flash("The photo wasn't found!")
        return redirect(url_for(".albums"))

    if request.method == "POST":
        caption = request.form.get("caption", "")
        rotate  = request.form.get("rotate", "")
        Photo.edit_photo(key, dict(caption=caption))

        # Rotating the photo?
        if rotate in ["left", "right", "180"]:
            Photo.rotate_photo(key, rotate)

        flash("The photo has been updated.")
        return redirect(url_for(".view_photo", key=key))

    g.info["key"] = key
    g.info["photo"] = pic

    return template("photos/edit.html")


@mod.route("/delete/<key>", methods=["GET", "POST"])
@login_required
def delete(key):
    """Delete a photo."""
    pic = Photo.get_photo(key)
    if not pic:
        flash("The photo wasn't found!")
        return redirect(url_for(".albums"))

    if request.method == "POST":
        # Do it.
        Photo.delete_photo(key)
        flash("The photo has been deleted.")
        return redirect(url_for(".albums"))

    g.info["key"] = key
    g.info["photo"] = pic

    return template("photos/delete.html")


@mod.route("/arrange_albums", methods=["GET", "POST"])
@login_required
def arrange_albums():
    """Rearrange the photo album order."""
    albums = Photo.list_albums()
    if len(albums) == 0:
        flash("There are no albums yet.")
        return redirect(url_for(".albums"))

    if request.method == "POST":
        order = request.form.get("order", "").split(";")
        Photo.order_albums(order)
        flash("The albums have been rearranged!")
        return redirect(url_for(".albums"))

    g.info["albums"] = albums
    return template("photos/arrange_albums.html")


@mod.route("/delete_album/<album>", methods=["GET", "POST"])
@login_required
def delete_album(album):
    """Delete an entire album."""
    photos = Photo.list_photos(album)
    if photos is None:
        flash("That album doesn't exist.")
        return redirect(url_for(".albums"))

    if request.method == "POST":
        # Do it.
        for photo in photos:
            Photo.delete_photo(photo["key"])
        flash("The album has been deleted.")
        return redirect(url_for(".albums"))

    g.info["album"] = album

    return template("photos/delete_album.html")


@mod.route("/arrange_photos/<album>", methods=["GET", "POST"])
@login_required
def arrange_photos(album):
    """Rearrange the photos in an album."""
    photos = Photo.list_photos(album)
    if photos is None:
        flash("That album doesn't exist.")
        return redirect(url_for(".albums"))

    if request.method == "POST":
        order = request.form.get("order", "").split(";")
        Photo.order_photos(album, order)
        flash("The albums have been rearranged!")
        return redirect(url_for(".album_index", name=album))

    g.info["album"]  = album
    g.info["photos"] = photos
    return template("photos/arrange_photos.html")
