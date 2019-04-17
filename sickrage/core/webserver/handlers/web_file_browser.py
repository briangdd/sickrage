import os

from tornado.escape import json_encode

from sickrage.core.helpers.browser import foldersAtPath
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/browser(/?.*)')
class WebFileBrowserHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(WebFileBrowserHandler, self).__init__(*args, **kwargs)

    def index(self, path='', includeFiles=False, fileTypes=''):
        self.set_header('Content-Type', 'application/json')
        return json_encode(foldersAtPath(path, True, bool(int(includeFiles)), fileTypes.split(',')))

    def complete(self, term, includeFiles=False, fileTypes=''):
        self.set_header('Content-Type', 'application/json')
        return json_encode([entry['path'] for entry in foldersAtPath(
            os.path.dirname(term),
            includeFiles=bool(int(includeFiles)),
            fileTypes=fileTypes.split(',')
        ) if 'path' in entry])
