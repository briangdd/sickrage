import markdown2

import sickrage
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/changes(/?.*)')
class ChangelogHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ChangelogHandler, self).__init__(*args, **kwargs)

    def index(self):
        try:
            data = markdown2.markdown(sickrage.changelog(), extras=['header-ids'])
        except Exception:
            data = ''

        sickrage.app.config.view_changelog = False
        sickrage.app.config.save()
        return data