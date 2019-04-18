import sickrage
from sickrage.core import AccountAPI
from sickrage.core.api import API
from sickrage.core.webserver.handlers.base import BaseHandler


class LoginHandler(BaseHandler):
    def prepare(self, *args, **kwargs):
        redirect_uri = "{}://{}{}/login".format(self.request.protocol, self.request.host, sickrage.app.config.web_root)

        code = self.get_argument('code', False)
        if code:
            try:
                token = sickrage.app.oidc_client.authorization_code(code, redirect_uri)
                userinfo = sickrage.app.oidc_client.userinfo(token['access_token'])

                self.set_secure_cookie('sr_access_token', token['access_token'])
                self.set_secure_cookie('sr_refresh_token', token['refresh_token'])

                if not userinfo.get('sub'):
                    return self.redirect('/logout')

                if not sickrage.app.config.sub_id:
                    sickrage.app.config.sub_id = userinfo.get('sub')
                    sickrage.app.config.save()
                elif sickrage.app.config.sub_id != userinfo.get('sub'):
                    if API().token:
                        allowed_usernames = API().allowed_usernames()['data']
                        if not userinfo['preferred_username'] in allowed_usernames:
                            sickrage.app.log.debug(
                                "USERNAME:{} IP:{} - ACCESS DENIED".format(userinfo['preferred_username'],
                                                                           self.request.remote_ip)
                            )
                            return self.redirect('/logout')
                    else:
                        return self.redirect('/logout')

                if not API().token:
                    exchange = {'scope': 'offline_access', 'subject_token': token['access_token']}
                    API().token = sickrage.app.oidc_client.token_exchange(**exchange)
            except Exception as e:
                return self.redirect('/logout')

            if not sickrage.app.config.app_id:
                sickrage.app.config.app_id = AccountAPI().register_app_id()
                sickrage.app.config.save()

            redirect_uri = self.get_argument('next', "/{}/".format(sickrage.app.config.default_page))
            return self.redirect("{}".format(redirect_uri))
        else:
            authorization_url = sickrage.app.oidc_client.authorization_url(redirect_uri=redirect_uri)
            return super(BaseHandler, self).redirect(authorization_url)
