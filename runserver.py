#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import sys
import argparse

from rophako import app

parser = argparse.ArgumentParser(description="Rophako")
parser.add_argument(
    "--port", "-p",
    type=int,
    help="Port to listen on",
    default=2006,
)
parser.add_argument(
    "--key", "-k",
    type=str,
    help="SSL private key file. Providing this option will turn on SSL mode " \
        + "(and will require pyOpenSSL to be installed).",
)
parser.add_argument(
    "--cert", "-c",
    type=str,
    help="SSL certificate file.",
)
args = parser.parse_args()

if __name__ == '__main__':
    flask_options = dict(
        host='0.0.0.0',
        debug=True,
        port=args.port,
        threaded=True,
    )

    if args.key and args.cert:
        from OpenSSL import SSL
        context = SSL.Context(SSL.SSLv23_METHOD)
        context.use_privatekey_file(args.key)
        context.use_certificate_file(args.cert)
        app.config['SESSION_COOKIE_SECURE'] = True
        flask_options["ssl_context"] = context

    app.run(**flask_options)

