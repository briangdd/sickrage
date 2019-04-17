import datetime
import os
from functools import cmp_to_key

from tornado.escape import json_encode

import sickrage
from sickrage.core import AccountAPI
from sickrage.core.api import API
from sickrage.core.databases.main import MainDB
from sickrage.core.helpers import remove_article
from sickrage.core.tv.show.coming_episodes import ComingEpisodes
from sickrage.core.webserver import ApiHandler
from sickrage.core.webserver.handlers.base import BaseHandler


class WebRootHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(WebRootHandler, self).__init__(*args, **kwargs)

    def robots_txt(self):
        """ Keep web crawlers out """
        self.set_header('Content-Type', 'text/plain')
        return "User-agent: *\nDisallow: /"

    def messages_po(self):
        """ Get /sickrage/locale/{lang_code}/LC_MESSAGES/messages.po """
        if sickrage.app.config.gui_lang:
            locale_file = os.path.join(sickrage.LOCALE_DIR, sickrage.app.config.gui_lang, 'LC_MESSAGES/messages.po')
            if os.path.isfile(locale_file):
                with open(locale_file, 'r', encoding='utf8') as f:
                    return f.read()

    def apibuilder(self):
        def titler(x):
            return (remove_article(x), x)[not x or sickrage.app.config.sort_article]

        episodes = {}

        for result in MainDB.TVEpisode.query.order_by(MainDB.TVEpisode.season, MainDB.TVEpisode.episode):

            if result['showid'] not in episodes:
                episodes[result['showid']] = {}

            if result['season'] not in episodes[result['showid']]:
                episodes[result['showid']][result['season']] = []

            episodes[result['showid']][result['season']].append(result['episode'])

        if len(sickrage.app.config.api_key) == 32:
            apikey = sickrage.app.config.api_key
        else:
            apikey = _('API Key not generated')

        return self.render(
            'api_builder.mako',
            title=_('API Builder'),
            header=_('API Builder'),
            shows=sorted(sickrage.app.showlist, key=cmp_to_key(lambda x, y: titler(x.name) < titler(y.name))),
            episodes=episodes,
            apikey=apikey,
            commands=ApiHandler(self.application, self.request).api_calls,
            controller='root',
            action='api_builder'
        )

    def setHomeLayout(self, layout):
        if layout not in ('poster', 'small', 'banner', 'simple', 'coverflow'):
            layout = 'poster'

        sickrage.app.config.home_layout = layout

        # Don't redirect to default page so user can see new layout
        return self.redirect("/home/")

    @staticmethod
    def setPosterSortBy(sort):

        if sort not in ('name', 'date', 'network', 'progress'):
            sort = 'name'

        sickrage.app.config.poster_sortby = sort
        sickrage.app.config.save()

    @staticmethod
    def setPosterSortDir(direction):

        sickrage.app.config.poster_sortdir = int(direction)
        sickrage.app.config.save()

    def setHistoryLayout(self, layout):

        if layout not in ('compact', 'detailed'):
            layout = 'detailed'

        sickrage.app.config.history_layout = layout

        return self.redirect("/history/")

    def toggleDisplayShowSpecials(self, show):

        sickrage.app.config.display_show_specials = not sickrage.app.config.display_show_specials

        return self.redirect("/home/displayShow?show=" + show)

    def setScheduleLayout(self, layout):
        if layout not in ('poster', 'banner', 'list', 'calendar'):
            layout = 'banner'

        if layout == 'calendar':
            sickrage.app.config.coming_eps_sort = 'date'

        sickrage.app.config.coming_eps_layout = layout

        return self.redirect("/schedule/")

    def toggleScheduleDisplayPaused(self):

        sickrage.app.config.coming_eps_display_paused = not sickrage.app.config.coming_eps_display_paused

        return self.redirect("/schedule/")

    def setScheduleSort(self, sort):
        if sort not in ('date', 'network', 'show'):
            sort = 'date'

        if sickrage.app.config.coming_eps_layout == 'calendar':
            sort = 'date'

        sickrage.app.config.coming_eps_sort = sort

        return self.redirect("/schedule/")

    def schedule(self, layout=None):
        next_week = datetime.date.today() + datetime.timedelta(days=7)
        next_week1 = datetime.datetime.combine(next_week,
                                               datetime.datetime.now().time().replace(tzinfo=sickrage.app.tz))
        results = ComingEpisodes.get_coming_episodes(ComingEpisodes.categories,
                                                     sickrage.app.config.coming_eps_sort,
                                                     False)
        today = datetime.datetime.now().replace(tzinfo=sickrage.app.tz)

        # Allow local overriding of layout parameter
        if layout and layout in ('poster', 'banner', 'list', 'calendar'):
            layout = layout
        else:
            layout = sickrage.app.config.coming_eps_layout

        return self.render(
            'schedule.mako',
            next_week=next_week1,
            today=today,
            results=results,
            layout=layout,
            title=_('Schedule'),
            header=_('Schedule'),
            topmenu='schedule',
            controller='root',
            action='schedule'
        )

    def unlink(self):
        if not sickrage.app.config.sub_id == self.get_current_user().get('sub'):
            return self.redirect("/{}/".format(sickrage.app.config.default_page))

        AccountAPI().unregister_app_id(sickrage.app.config.app_id)

        sickrage.app.config.sub_id = ""
        sickrage.app.config.save()

        API().token = sickrage.app.oidc_client.logout(API().token['refresh_token'])

        return self.redirect('/logout/')

    def quicksearch_json(self, term):
        shows = sickrage.app.quicksearch_cache.get_shows(term)
        episodes = sickrage.app.quicksearch_cache.get_episodes(term)

        if not len(shows):
            shows = [{
                'category': 'shows',
                'showid': '',
                'name': term,
                'img': '/images/poster-thumb.png',
                'seasons': 0,
            }]

        return json_encode(str(shows + episodes))