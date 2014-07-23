#!/usr/bin/env python

"""Dynamic CMS plugin loader."""

import os
from importlib import import_module
from rophako.app import app, BLUEPRINT_PATHS

def load_plugin(name, as_blueprint=True, template_path=None):
    """Load a Rophako CMS plugin.

    * `name` is a Python module name, i.e. `rophako.modules.blog`
    * `as_blueprint` is True if the module exports a blueprint object called
      `mod` that can be attached to the Flask app. Set this value to False if
      you simply need to include a Python module that isn't a blueprint.
    * `template_path` is a filesystem path where the blueprint's templates
      can be found. If not provided, the path is automatically determined
      based on the module name, which is suitable for the built-in plugins."""
    module = import_module(name)
    if as_blueprint:
        mod = getattr(module, "mod")
        app.register_blueprint(mod)

        # Get the template path to add to the BLUEPRINT_PATHS.
        if template_path is None:
            module_path   = name.replace(".", "/")
            template_path = os.path.join(module_path, "templates")

        BLUEPRINT_PATHS.append(template_path)