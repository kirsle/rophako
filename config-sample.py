# Sample config file for Rophako.
#
# Edit this file and save the copy as "config.py".

import os
_basedir = os.path.abspath(os.path.dirname(__file__))

DEBUG = True

# Unique name of your site, e.g. "kirsle.net"
SITE_NAME = "example.com"

# Secret key used for session cookie signing. Make this long and hard to guess.
#
# Tips for creating a strong secret key:
# $ python
# >>> import os
# >>> os.urandom(24)
# '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8'
#
# Then take that whole quoted string and paste it right in as the secret key!
# Do NOT use that one. It was just an example! Make your own.
SECRET_KEY = 'for the love of Arceus, change this key!'

# Password strength: number of iterations for bcrypt to hash passwords.
BCRYPT_ITERATIONS = 12

# Where to save temp files for photo uploads, etc.
TEMPDIR = "/tmp"

# Rophako uses a flat file JSON database system, and the Redis caching server
# sits between Ropahko and the filesystem.
DB_ROOT      = "db"
REDIS_HOST   = "localhost"
REDIS_PORT   = 6379
REDIS_DB     = 0
REDIS_PREFIX = "rophako:"

################################################################################
## Blog Settings                                                              ##
################################################################################

BLOG_ENTRIES_PER_PAGE = 5  # Number of entries to show per page
BLOG_ENTRIES_PER_RSS  = 5  # The same, but for the RSS feed
BLOG_DEFAULT_CATEGORY = "Uncategorized"
BLOG_DEFAULT_PRIVACY  = "public"
BLOG_TIME_FORMAT      = "%A, %B %d %Y @ %I:%M:%S %p" # "Weekday, Month dd yyyy @ hh:mm:ss AM"
BLOG_ALLOW_COMMENTS   = True

################################################################################
## Photo Settings                                                             ##
################################################################################

# The path to where uploaded photos will be stored.
# The PRIVATE path is from the perspective of the server file system.
# The PUBLIC path is from the perspective of the web browser via HTTP.
PHOTO_ROOT_PRIVATE = os.path.join(_basedir, "site", "www", "static", "photos")
PHOTO_ROOT_PUBLIC  = "/static/photos"

PHOTO_DEFAULT_ALBUM = "My Photos" # Default/fallback album name.
PHOTO_TIME_FORMAT   = BLOG_TIME_FORMAT

# Photo sizes.
PHOTO_WIDTH_LARGE  = 800  # Max width of full size photos.
PHOTO_WIDTH_THUMB  = 256  # Max square width of photo thumbnails.
PHOTO_WIDTH_AVATAR = 96   # Square width of photo avatars.