import markdown2

import sickrage
from sickrage.core.webserver.handlers.base import BaseHandler


class ChangelogHandler(BaseHandler):
    def get(self):
        try:
            data = markdown2.markdown(sickrage.changelog(), extras=['header-ids'])
        except Exception:
            data = ''

        return data
