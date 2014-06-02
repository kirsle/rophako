# -*- coding: utf-8 -*-

"""Photo album models."""

import os
from flask import g, request
import time
import requests
from PIL import Image
import hashlib
import random

import config
import rophako.jsondb as JsonDB
from rophako.utils import sanitize_name
from rophako.log import logger

# Maps the friendly names of photo sizes with their pixel values from config.
PHOTO_SCALES = dict(
    large=config.PHOTO_WIDTH_LARGE,
    thumb=config.PHOTO_WIDTH_THUMB,
    avatar=config.PHOTO_WIDTH_AVATAR,
)


def list_albums():
    """Retrieve a sorted list of the photo albums."""
    index = get_index()
    result = []

    for album in index["album-order"]:
        cover = index["covers"][album]
        pic = index["albums"][album][cover]["thumb"]
        result.append(dict(
            name=album,
            cover=pic,
            data=index["albums"][album],
        ))

    return result


def list_photos(album):
    """List the photos in an album."""
    album = sanitize_name(album)
    index = get_index()

    if not album in index["albums"]:
        return None

    result = []
    for key in index["photo-order"][album]:
        data = index["albums"][album][key]
        result.append(dict(
            key=key,
            data=data,
        ))

    return result


def photo_exists(key):
    """Query whether a photo exists in the album."""
    index = get_index()
    return key in index["map"]


def get_photo(key):
    """Look up a photo by key. Returns None if not found."""
    index = get_index()
    photo = None
    if key in index["map"]:
        album = index["map"][key]
        if album in index["albums"] and key in index["albums"][album]:
            photo = index["albums"][album][key]
        else:
            # The map is wrong!
            logger.error("Photo album map is wrong; key {} not found in album {}!".format(key, album))
            del index["map"][key]
            write_index(index)

    if not photo:
        return None

    # Inject additional information about the photo:
    # What position it's at in the album, how many photos total, and the photo
    # IDs of its siblings.
    siblings = index["photo-order"][album]
    i = 0
    for pid in siblings:
        if pid == key:
            # We found us! Find the siblings.
            sprev, snext = None, None
            if i == 0:
                # We're the first photo. So previous is the last!
                sprev = siblings[-1]
                if len(siblings) > i+1:
                    snext = siblings[i+1]
                else:
                    snext = key
            elif i == len(siblings)-1:
                # We're the last. So next is first!
                sprev = siblings[i-1]
                snext = siblings[0]
            else:
                # Right in the middle.
                sprev = siblings[i-1]
                snext = siblings[i+1]

            # Inject.
            photo["album"] = album
            photo["position"] = i+1
            photo["siblings"] = len(siblings)
            photo["previous"] = sprev
            photo["next"] = snext
        i += 1

    return photo


def get_image_dimensions(pic):
    """Use PIL to get the image's true dimensions."""
    filename = os.path.join(config.PHOTO_ROOT_PRIVATE, pic["large"])
    img = Image.open(filename)
    return img.size


def update_photo(album, key, data):
    """Update photo meta-data in the album."""
    index = get_index()

    if not album in index["albums"]:
        index["albums"][album] = {}
    if not key in index["albums"][album]:
        index["albums"][album][key] = {}

    # Update!
    index["albums"][album][key].update(data)
    write_index(index)


def crop_photo(key, x, y, length):
    """Change the crop coordinates of a photo and re-crop it."""
    index = get_index()
    if not key in index["map"]:
        raise Exception("Can't crop photo: doesn't exist!")

    album = index["map"][key]

    # Sanity check.
    if not album in index["albums"]:
        raise Exception("Can't find photo in album!")

    logger.debug("Recropping photo {}".format(key))

    # Delete all the images except the large one.
    for size in ["thumb", "avatar"]:
        pic = index["albums"][album][key][size]
        logger.debug("Delete {} size: {}".format(size, pic))
        os.unlink(os.path.join(config.PHOTO_ROOT_PRIVATE, pic))

    # Regenerate all the thumbnails.
    large = index["albums"][album][key]["large"]
    source = os.path.join(config.PHOTO_ROOT_PRIVATE, large)
    for size in ["thumb", "avatar"]:
        pic = resize_photo(source, size, crop=dict(
            x=x,
            y=y,
            length=length,
        ))
        index["albums"][album][key][size] = pic

    # Save changes.
    write_index(index)


def set_album_cover(album, key):
    """Change the album's cover photo."""
    album = sanitize_name(album)
    index = get_index()
    logger.info("Changing album cover for {} to {}".format(album, key))
    if album in index["albums"] and key in index["albums"][album]:
        index["covers"][album] = key
        write_index(index)
        return
    logger.error("Failed to change album index! Album or photo not found.")


def edit_photo(key, data):
    """Update a photo's data."""
    index = get_index()
    if not key in index["map"]:
        logger.warning("Tried to delete photo {} but it wasn't found?".format(key))
        return

    album = index["map"][key]

    logger.info("Completely deleting the photo {} from album {}".format(key, album))
    index["albums"][album][key].update(data)

    write_index(index)


def delete_photo(key):
    """Delete a photo."""
    index = get_index()
    if not key in index["map"]:
        logger.warning("Tried to delete photo {} but it wasn't found?".format(key))
        return

    album = index["map"][key]

    logger.info("Completely deleting the photo {} from album {}".format(key, album))
    photo = index["albums"][album][key]

    # Delete all the images.
    for size in ["large", "thumb", "avatar"]:
        logger.info("Delete: {}".format(photo[size]))
        os.unlink(os.path.join(config.PHOTO_ROOT_PRIVATE, photo[size]))

    # Delete it from the sort list.
    index["photo-order"][album].remove(key)
    del index["map"][key]
    del index["albums"][album][key]

    # Was this the album cover?
    if index["covers"][album] == key:
        # Try to pick a new one.
        if len(index["photo-order"][album]) > 0:
            index["covers"][album] = index["photo-order"][album][0]
        else:
            index["covers"][album] = ""

    # If the album is empty now too, delete it as well.
    if len(index["albums"][album].keys()) == 0:
        del index["albums"][album]
        del index["photo-order"][album]
        del index["covers"][album]
        index["album-order"].remove(album)

    write_index(index)


def order_albums(order):
    """Reorder the albums according to the new order list."""
    index = get_index()

    # Sanity check, make sure all albums are included.
    if len(order) != len(index["album-order"]):
        logger.warning("Can't reorganize albums because the order lists don't match!")
        return None

    for album in index["album-order"]:
        if album not in order:
            logger.warning("Tried reorganizing albums, but {} was missing!".format(album))
            return None

    index["album-order"] = order
    write_index(index)


def order_photos(album, order):
    """Reorder the photos according to the new order list."""
    index = get_index()

    if not album in index["albums"]:
        logger.warning("Album not found: {}".format(album))
        return None

    # Sanity check, make sure all albums are included.
    if len(order) != len(index["photo-order"][album]):
        logger.warning("Can't reorganize photos because the order lists don't match!")
        return None

    for key in index["photo-order"][album]:
        if key not in order:
            logger.warning("Tried reorganizing photos, but {} was missing!".format(key))
            return None

    index["photo-order"][album] = order
    write_index(index)


def upload_from_pc(request):
    """Upload a photo from the user's filesystem.

    This requires the Flask `request` object. Returns a dict with the following
    keys:

    * success: True || False
    * error: if unsuccessful
    * photo: if successful
    """

    form   = request.form
    upload = request.files["file"]

    # Make a temp filename for it.
    filetype = upload.filename.rsplit(".", 1)[1]
    tempfile = "{}/rophako-photo-{}.{}".format(config.TEMPDIR, int(time.time()), filetype)
    logger.debug("Save incoming photo to: {}".format(tempfile))
    upload.save(tempfile)

    # All good so far. Process the photo.
    return process_photo(form, tempfile)


def upload_from_www(form):
    """Upload a photo from the Internet.

    This requires the `form` object, but not necessarily Flask's. It just has to
    be a dict with the form keys for the upload.

    Returns the same structure as `upload_from_pc()`.
    """

    url = form.get("url")
    if not url or not allowed_filetype(url):
        return dict(success=False, error="Invalid file extension.")

    # Make a temp filename for it.
    filetype = url.rsplit(".", 1)[1]
    tempfile = "{}/rophako-photo-{}.{}".format(config.TEMPDIR, int(time.time()), filetype)
    logger.debug("Save incoming photo to: {}".format(tempfile))

    # Grab the file.
    try:
        data = requests.get(url).content
    except:
        return dict(success=False, error="Failed to get that URL.")

    fh = open(tempfile, "wb")
    fh.write(data)
    fh.close()

    # All good so far. Process the photo.
    return process_photo(form, tempfile)


def process_photo(form, filename):
    """Formats an incoming photo."""

    # Resize the photo to each of the various sizes and collect their names.
    sizes = dict()
    for size in PHOTO_SCALES.keys():
        sizes[size] = resize_photo(filename, size)

    # Remove the temp file.
    os.unlink(filename)

    # What album are the photos going to?
    album     = form.get("album", "")
    new_album = form.get("new-album", None)
    if album == "" and new_album:
        album = new_album

    # Sanitize the name.
    album = sanitize_name(album)
    if album == "":
        logger.warning("Album name didn't pass sanitization! Fall back to default album name.")
        album = config.PHOTO_DEFAULT_ALBUM

    # Make up a unique public key for this set of photos.
    key = random_hash()
    while photo_exists(key):
        key = random_hash()
    logger.debug("Photo set public key: {}".format(key))

    # Get the album index to manipulate ordering.
    index = get_index()

    # Update the photo data.
    if not album in index["albums"]:
        index["albums"][album] = {}

    index["albums"][album][key] = dict(
        ip=request.remote_addr,
        author=g.info["session"]["uid"],
        uploaded=int(time.time()),
        caption=form.get("caption", ""),
        **sizes
    )

    # Maintain a photo map to album.
    index["map"][key] = album

    # Add this pic to the front of the album.
    if not album in index["photo-order"]:
        index["photo-order"][album] = []
    index["photo-order"][album].insert(0, key)

    # If this is a new album, add it to the front of the album ordering.
    if not album in index["album-order"]:
        index["album-order"].insert(0, album)

    # Set the album cover for a new album.
    if not album in index["covers"] or len(index["covers"][album]) == 0:
        index["covers"][album] = key

    # Save changes to the index.
    write_index(index)

    return dict(success=True, photo=key)


def allowed_filetype(filename):
    """Query whether the file extension is allowed."""
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in ['jpeg', 'jpe', 'jpg', 'gif', 'png']


def resize_photo(filename, size, crop=None):
    """Resize a photo from the target filename into the requested size.

    Optionally the photo can be cropped with custom parameters.
    """

    # Find the file type.
    filetype = filename.rsplit(".", 1)[1]
    if filetype == "jpeg": filetype = "jpg"

    # Open the image.
    img = Image.open(filename)

    # Make up a unique filename.
    outfile = random_name(filetype)
    target  = os.path.join(config.PHOTO_ROOT_PRIVATE, outfile)
    logger.debug("Output file for {} scale: {}".format(size, target))

    # Get the image's dimensions.
    orig_width, orig_height = img.size
    new_width = PHOTO_SCALES[size]
    logger.debug("Original photo dimensions: {}x{}".format(orig_width, orig_height))

    # For the large version, only scale it, don't crop it.
    if size == "large":
        # Do we NEED to scale it?
        if orig_width <= new_width:
            logger.debug("Don't need to scale down the large image!")
            img.save(target)
            return outfile

        # Scale it down.
        ratio      = float(new_width) / float(orig_width)
        new_height = int(float(orig_height) * float(ratio))
        logger.debug("New image dimensions: {}x{}".format(new_width, new_height))
        img = img.resize((new_width, new_height), Image.ANTIALIAS)
        img.save(target)
        return outfile

    # For all other versions, crop them into a square.
    x, y, length = 0, 0, 0

    # Use 0,0 and find the shortest dimension for the length.
    if orig_width > orig_height:
        length = orig_height
    else:
        length = orig_width

    # Did they give us crop coordinates?
    if crop is not None:
        x = crop["x"]
        y = crop["y"]
        if crop["length"] > 0:
            length = crop["length"]

    # Adjust the coords if they're impossible.
    if x < 0:
        logger.warning("X-Coord is less than 0; fixing!")
        x = 0
    if y < 0:
        logger.warning("Y-Coord is less than 0; fixing!")
        y = 0
    if x > orig_width:
        logger.warning("X-Coord is greater than image width; fixing!")
        x = orig_width - length
        if x < 0: x = 0
    if y > orig_height:
        logger.warning("Y-Coord is greater than image height; fixing!")
        y = orig_height - length
        if y < 0: y = 0

    # Make sure the crop box fits.
    if x + length > orig_width:
        diff = x + length - orig_width
        logger.warning("Crop box is outside the right edge of the image by {}px; fixing!".format(diff))
        length -= diff
    if y + length > orig_height:
        diff = y + length - orig_height
        logger.warning("Crop box is outside the bottom edge of the image by {}px; fixing!".format(diff))
        length -= diff

    # Do we need to scale?
    if new_width == length:
        logger.debug("Image doesn't need to be cropped or scaled!")
        img.save(target)
        return outfile

    # Crop to the requested box.
    logger.debug("Cropping the photo")
    img = img.crop((x, y, x+length, y+length))

    # Scale it to the proper dimensions.
    img = img.resize((new_width, new_width), Image.ANTIALIAS)
    img.save(target)
    return outfile


def get_index():
    """Get the photo album index, or a new empty DB if it doesn't exist."""
    if JsonDB.exists("photos/index"):
        return JsonDB.get("photos/index")

    return {
        "albums": {},      # Album data
        "map": {},         # Map photo keys to albums
        "covers": {},      # Album cover photos
        "photo-order": {}, # Ordering of photos in albums
        "album-order": [], # Ordering of albums themselves
    }


def write_index(index):
    """Save the index back to the DB."""
    return JsonDB.commit("photos/index", index)


def random_name(filetype):
    """Get a random available file name to save a new photo."""
    outfile = random_hash() + "." + filetype
    while os.path.isfile(os.path.join(config.PHOTO_ROOT_PRIVATE, outfile)):
        outfile = random_hash() + "." + filetype
    return outfile


def random_hash():
    """Get a short random hash to use as the base name for a photo."""
    md5 = hashlib.md5()
    md5.update(str(random.randint(0, 1000000)).encode("utf-8"))
    return md5.hexdigest()[:8]