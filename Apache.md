# Apache Configuration

Here's some tips on getting Rophako set up on Apache.

# mod\_fcgid and mod\_rewrite

For kirsle.net I needed to set it up using `mod_fcgid` because my site has a lot
of legacy URLs to old static files, so Rophako needs to serve the main website
pages and Apache needs to serve everything else.

## Apache configuration:

```apache
# Rophako www.kirsle.net
<VirtualHost *:80>
    ServerName www.kirsle.net
    DocumentRoot /home/kirsle/www
    CustomLog /home/kirsle/logs/access_log combined
    ErrorLog /home/kirsle/logs/error_log
    SuexecUserGroup kirsle kirsle

    <Directory "/home/kirsle/www">
        Options Indexes FollowSymLinks ExecCGI
        AllowOverride All
        Order allow,deny
        Allow from all
    </Directory>

    <Directory "/home/kirsle/www/fcgi">
        SetHandler fcgid-script
        Options +ExecCGI
        AllowOverride all
        Order allow,deny
        Allow from all
    </Directory>
</VirtualHost>
```

## .htaccess configuration:

This goes in `~/www/.htaccess`

```apache
<IfModule mod_rewrite.c>
    RewriteEngine on
    RewriteBase /
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^(.*)$ /fcgi/index.fcgi/$1 [QSA,L]
    RewriteRule ^$ /fcgi/index.fcgi/ [QSA,L]
</IfModule>
```

## FastCGI script

This is my FastCGI script I wrote to launch Rophako. Important things to note:

* The shebang line points to the Python binary in my virtualenv.
* I modify sys.path and chdir to my git checkout folder for Rophako.
* The `ScriptNameStripper` allows `mod_rewrite` to work best. Without it you'll
  sometimes get URL paths like `/fcgi/index.fcgi/blog/entry/...` etc. from Flask
  because that's what it thinks its path is.

```python
#!/home/kirsle/.virtualenv/rophako/bin/python

import os
import sys
sys.path.append("/home/kirsle/git/rophako")
os.chdir("/home/kirsle/git/rophako")

from flup.server.fcgi import WSGIServer
from rophako import app

class ScriptNameStripper(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        environ["SCRIPT_NAME"] = ""
        return self.app(environ, start_response)

app = ScriptNameStripper(app)

if __name__ == "__main__":
    WSGIServer(app).run()
```
