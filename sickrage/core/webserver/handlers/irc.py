from sickrage.core.webserver.handlers.base import BaseHandler


class IRCHandler(BaseHandler):
    def get(self):
        return self.render(
            "/irc.mako",
            topmenu="system",
            header="IRC",
            title="IRC",
            controller='root',
            action='irc'
        )
