import sickrage
from sickrage.core.helpers import checkbox_to_value
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/config/anime(/?.*)')
class ConfigAnime(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigAnime, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/config/anime.mako",
            submenu=self.ConfigMenu(),
            title=_('Config - Anime'),
            header=_('Anime'),
            topmenu='config',
            controller='config',
            action='anime'
        )

    def saveAnime(self, use_anidb=None, anidb_username=None, anidb_password=None, anidb_use_mylist=None,
                  split_home=None):

        results = []

        sickrage.app.config.use_anidb = checkbox_to_value(use_anidb)
        sickrage.app.config.anidb_username = anidb_username
        sickrage.app.config.anidb_password = anidb_password
        sickrage.app.config.anidb_use_mylist = checkbox_to_value(anidb_use_mylist)
        sickrage.app.config.anime_split_home = checkbox_to_value(split_home)

        sickrage.app.config.save()

        if len(results) > 0:
            [sickrage.app.log.error(x) for x in results]
            sickrage.app.alerts.error(_('Error(s) Saving Configuration'), '<br>\n'.join(results))
        else:
            sickrage.app.alerts.message(_('[ANIME] Configuration Encrypted and Saved to SiCKRAGE Cloud'))

        return self.redirect("/config/anime/")