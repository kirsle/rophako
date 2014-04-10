# Rophako

A simplistic content management system designed for
[kirsle.net](http://www.kirsle.net/).

Rophako is [Azulian](http://www.kirsle.net/wizards/translator.html) for
"website." Pronounce it however you like. I pronounce it "roe-fa-koe."

This project is currently in "beta" status. It is currently powering kirsle.net
and a couple other small sites.

Check out Rophako's official homepage and example site:
[rophako.kirsle.net](http://rophako.kirsle.net/)

# Installation

`pip install -r requirements.txt`

These may need to be installed for the dependencies to build:

**Fedora:** `libffi-devel libjpeg-devel libpng-devel`

# Server Configuration

Instructions and tips are currently available for the Apache web server.
See [Apache.md](https://github.com/kirsle/rophako/blob/master/Apache.md) for
information.

Copy the file `config-sample.py` as a file named `config.py`, and edit
its contents to set up your site. It's very important that you change the
`SECRET_KEY` variable, as this is used to sign the session cookies and
prevent people from tampering with them. The config script is well-documented
with comments explaining what all the options do.

# Create the Admin User

Once the web app is up and running, navigate to the `/account/setup` URL
to create the admin user account. Once the admin account has been created,
the `/account/setup` path can't be used anymore. Additional user accounts
can be created by the admin users at the `/admin` URL.

# Building Your Site

Rophako has a dual templating system. When the Rophako CMS wants to render
a template (for example, `blog/entry.html`), it will look inside your
`SITE_ROOT` path first for that template, before falling back to the default
site templates inside the `rophako/www` path.

All of the core features of Rophako (user account, blog, photo albums,
comments, etc.) exist in the default site, so the CMS is already fully
functional out-of-the-box. You can override files in the default site by
putting files with the same name in your `SITE_ROOT` folder. For example,
the default `SITE_ROOT` is set to the "site/www" folder in the git repo, and
if you put a file at `site/www/layout.html` there, it will change the web
design template for the Rophako site. A file at `site/www/index.html` will
change the index page of your site away from the default.

# Copyright

	Rophako CMS
	Copyright (C) 2014 Noah Petherbridge

	This program is free software; you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation; either version 2 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program; if not, write to the Free Software
	Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

