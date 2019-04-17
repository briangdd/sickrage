from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/IRC(/?.*)')
class IRCHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(IRCHandler, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/irc.mako",
            topmenu="system",
            header="IRC",
            title="IRC",
            controller='root',
            action='irc'
        )