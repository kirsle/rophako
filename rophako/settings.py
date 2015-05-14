# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import datetime
from attrdict import AttrDict
from ConfigParser import ConfigParser

from rophako.plugin import load_plugin

# Get the base directory of the git root.
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))

# https://github.com/bcj/AttrDict/issues/20
if not hasattr(AttrDict, "copy"):
    setattr(AttrDict, "copy", lambda self: self._mapping.copy())

class ConfigHandler(object):
    settings = None

    def load_settings(self):
        """Load the settings files and make them available in the global config."""
        self.settings = ConfigParser(dict_type=AttrDict)

        # Set dynamic default variables.
        self.settings.set("DEFAULT", "_basedir", basedir)
        self.settings.set("DEFAULT", "_year", str(datetime.datetime.now().strftime("%Y")))

        # Read the defaults and then apply the custom settings on top.
        settings_file = os.environ.get("ROPHAKO_SETTINGS", "settings.ini")
        self.settings.read(["defaults.ini", settings_file])

    def print_settings(self):
        """Pretty-print the contents of the configuration as JSON."""
        for section in self.settings.sections():
            print "[{}]".format(section)
            for opt in self.settings.options(section):
                print "{} = {}".format(opt, repr(self.settings.get(section, opt)))
            print ""

    def load_plugins(self):
        """Load all the plugins specified by the config file."""
        for plugin in self.plugins.blueprints.split("\n"):
            plugin = plugin.strip()
            if not plugin:
                continue
            load_plugin(plugin)
        for custom in self.plugins.custom.split("\n"):
            custom = custom.strip()
            if not custom:
                continue
            load_plugin(custom, as_blueprint=False)

    def __getattr__(self, section):
        """Attribute access for the config object.

        You can access config settings via Config.<section>.<name>, for example
        Config.site.notify_email and Config.blog.posts_per_page. All results are
        returned as strings per ConfigParser, so cast them if you need to."""
        return AttrDict(dict(self.settings.items(section)))

Config = ConfigHandler()
