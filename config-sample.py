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

# Rophako uses a flat file JSON database system, and the Redis caching server
# sits between Ropahko and the filesystem.
DB_ROOT      = "db"
REDIS_HOST   = "localhost"
REDIS_PORT   = 6379
REDIS_DB     = 0
REDIS_PREFIX = "rophako:"