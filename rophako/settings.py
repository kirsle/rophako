# -*- coding: utf-8 -*-
from __future__ import unicode_literals, print_function, absolute_import

import os
import datetime
from yamlsettings import YamlSettings

from rophako.plugin import load_plugin

# Get the base directory of the git root.
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.path.pardir))

class ConfigHandler(object):
    settings = None

    def load_settings(self):
        """Load the settings and make them available in the global config."""
        settings_file = os.environ.get("ROPHAKO_SETTINGS", "settings.yml")
        project_settings = YamlSettings("defaults.yml", settings_file,
            default_section="rophako")
        self.settings = project_settings.get_settings()

        # Extrapolate {basedir} in certain keys.
        # TODO: find a better way...
        self.site.site_root = self.site.site_root.format(basedir=basedir)
        self.emoticons.root_private = self.emoticons.root_private.format(
            basedir=basedir
        )
        self.photo.root_private = self.photo.root_private.format(basedir=basedir)
        self.blog.copyright = self.blog.copyright.format(
            year=datetime.datetime.utcnow().strftime("%Y")
        )

    def print_settings(self):
        """Pretty-print the contents of the configuration."""
        print(self.settings)

    def load_plugins(self):
        """Load all the plugins specified by the config file."""
        for plugin in self.blueprints:
            plugin = plugin.strip()
            if not plugin: continue
            load_plugin(plugin)
        for custom in self.custom:
            custom = custom.strip()
            if not custom: continue
            load_plugin(custom, as_blueprint=False)

    def __getattr__(self, section):
        """Attribute accessor for the config object. Acts as a simple pass-thru
        to YamlSettings."""
        return getattr(self.settings, section)

Config = ConfigHandler()
