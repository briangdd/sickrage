import sickrage
from sickrage.core.webserver.handlers.base import BaseHandler


class LogoutHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(LogoutHandler, self).__init__(*args, **kwargs)

    def prepare(self, *args, **kwargs):
        logout_uri = sickrage.app.oidc_client.get_url('end_session_endpoint')
        redirect_uri = "{}://{}{}/login".format(self.request.protocol, self.request.host, sickrage.app.config.web_root)

        if self.get_secure_cookie('sr_refresh_token'):
            sickrage.app.oidc_client.logout(self.get_secure_cookie('sr_refresh_token'))

        self.clear_all_cookies()

        return super(BaseHandler, self).redirect('{}?redirect_uri={}'.format(logout_uri, redirect_uri))
