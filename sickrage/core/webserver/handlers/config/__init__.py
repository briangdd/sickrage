import os

import sickrage
from sickrage.core.webserver.handlers.base import BaseHandler


class Config(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(Config, self).__init__(*args, **kwargs)

    @staticmethod
    def ConfigMenu():
        menu = [
            {'title': _('Help and Info'), 'path': '/config/', 'icon': 'fas fa-info'},
            {'title': _('General'), 'path': '/config/general/', 'icon': 'fas fa-cogs'},
            {'title': _('Backup/Restore'), 'path': '/config/backuprestore/', 'icon': 'fas fa-upload'},
            {'title': _('Search Clients'), 'path': '/config/search/', 'icon': 'fas fa-binoculars'},
            {'title': _('Search Providers'), 'path': '/config/providers/', 'icon': 'fas fa-share-alt'},
            {'title': _('Subtitles Settings'), 'path': '/config/subtitles/', 'icon': 'fas fa-cc'},
            {'title': _('Quality Settings'), 'path': '/config/qualitySettings/', 'icon': 'fas fa-wrench'},
            {'title': _('Post Processing'), 'path': '/config/postProcessing/', 'icon': 'fas fa-refresh'},
            {'title': _('Notifications'), 'path': '/config/notifications/', 'icon': 'fas fa-bell'},
            {'title': _('Anime'), 'path': '/config/anime/', 'icon': 'fas fa-eye'},
        ]

        return menu

    def index(self):
        return self.render(
            "/config/index.mako",
            submenu=self.ConfigMenu(),
            title=_('Configuration'),
            header=_('Configuration'),
            topmenu="config",
            controller='config',
            action='index'
        )

    def reset(self):
        sickrage.app.config.load(True)
        sickrage.app.alerts.message(_('Configuration Reset to Defaults'),
                                    os.path.join(sickrage.app.config_file))
        return self.redirect("/config/general")
