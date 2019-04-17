import os

import sickrage
from sickrage.core.helpers import checkbox_to_value, try_int, clean_url, clean_host, torrent_webui_url
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/config/search(/?.*)')
class ConfigSearch(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigSearch, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/config/search.mako",
            submenu=self.ConfigMenu(),
            title=_('Config - Search Clients'),
            header=_('Search Clients'),
            topmenu='config',
            controller='config',
            action='search'
        )

    def saveSearch(self, use_nzbs=None, use_torrents=None, nzb_dir=None, sab_username=None, sab_password=None,
                   sab_apikey=None, sab_category=None, sab_category_anime=None, sab_category_backlog=None,
                   sab_category_anime_backlog=None, sab_host=None, nzbget_username=None,
                   nzbget_password=None, nzbget_category=None, nzbget_category_backlog=None, nzbget_category_anime=None,
                   nzbget_category_anime_backlog=None, nzbget_priority=None,
                   nzbget_host=None, nzbget_use_https=None, backlog_frequency=None,
                   dailysearch_frequency=None, nzb_method=None, torrent_method=None, usenet_retention=None,
                   download_propers=None, check_propers_interval=None, allow_high_priority=None, sab_forced=None,
                   randomize_providers=None, use_failed_snatcher=None, failed_snatch_age=None,
                   torrent_dir=None, torrent_username=None, torrent_password=None, torrent_host=None,
                   torrent_label=None, torrent_label_anime=None, torrent_path=None, torrent_verify_cert=None,
                   torrent_seed_time=None, torrent_paused=None, torrent_high_bandwidth=None,
                   torrent_rpcurl=None, torrent_auth_type=None, ignore_words=None, require_words=None,
                   ignored_subs_list=None, enable_rss_cache=None,
                   torrent_file_to_magnet=None, download_unverified_magnet_link=None):

        results = []

        if not sickrage.app.config.change_nzb_dir(nzb_dir):
            results += [_("Unable to create directory ") + os.path.normpath(nzb_dir) + _(", dir not changed.")]

        if not sickrage.app.config.change_torrent_dir(torrent_dir):
            results += [_("Unable to create directory ") + os.path.normpath(torrent_dir) + _(", dir not changed.")]

        sickrage.app.config.change_failed_snatch_age(failed_snatch_age)
        sickrage.app.config.use_failed_snatcher = checkbox_to_value(use_failed_snatcher)
        sickrage.app.config.change_daily_searcher_freq(dailysearch_frequency)
        sickrage.app.config.change_backlog_searcher_freq(backlog_frequency)
        sickrage.app.config.use_nzbs = checkbox_to_value(use_nzbs)
        sickrage.app.config.use_torrents = checkbox_to_value(use_torrents)
        sickrage.app.config.nzb_method = nzb_method
        sickrage.app.config.torrent_method = torrent_method
        sickrage.app.config.usenet_retention = try_int(usenet_retention, 500)
        sickrage.app.config.ignore_words = ignore_words if ignore_words else ""
        sickrage.app.config.require_words = require_words if require_words else ""
        sickrage.app.config.ignored_subs_list = ignored_subs_list if ignored_subs_list else ""
        sickrage.app.config.randomize_providers = checkbox_to_value(randomize_providers)
        sickrage.app.config.enable_rss_cache = checkbox_to_value(enable_rss_cache)
        sickrage.app.config.torrent_file_to_magnet = checkbox_to_value(torrent_file_to_magnet)
        sickrage.app.config.download_unverified_magnet_link = checkbox_to_value(download_unverified_magnet_link)
        sickrage.app.config.download_propers = checkbox_to_value(download_propers)
        sickrage.app.config.proper_searcher_interval = check_propers_interval
        sickrage.app.config.allow_high_priority = checkbox_to_value(allow_high_priority)
        sickrage.app.config.sab_username = sab_username
        sickrage.app.config.sab_password = sab_password
        sickrage.app.config.sab_apikey = sab_apikey.strip()
        sickrage.app.config.sab_category = sab_category
        sickrage.app.config.sab_category_backlog = sab_category_backlog
        sickrage.app.config.sab_category_anime = sab_category_anime
        sickrage.app.config.sab_category_anime_backlog = sab_category_anime_backlog
        sickrage.app.config.sab_host = clean_url(sab_host)
        sickrage.app.config.sab_forced = checkbox_to_value(sab_forced)
        sickrage.app.config.nzbget_username = nzbget_username
        sickrage.app.config.nzbget_password = nzbget_password
        sickrage.app.config.nzbget_category = nzbget_category
        sickrage.app.config.nzbget_category_backlog = nzbget_category_backlog
        sickrage.app.config.nzbget_category_anime = nzbget_category_anime
        sickrage.app.config.nzbget_category_anime_backlog = nzbget_category_anime_backlog
        sickrage.app.config.nzbget_host = clean_host(nzbget_host)
        sickrage.app.config.nzbget_use_https = checkbox_to_value(nzbget_use_https)
        sickrage.app.config.nzbget_priority = try_int(nzbget_priority, 100)
        sickrage.app.config.torrent_username = torrent_username
        sickrage.app.config.torrent_password = torrent_password
        sickrage.app.config.torrent_label = torrent_label
        sickrage.app.config.torrent_label_anime = torrent_label_anime
        sickrage.app.config.torrent_verify_cert = checkbox_to_value(torrent_verify_cert)
        sickrage.app.config.torrent_path = torrent_path.rstrip('/\\')
        sickrage.app.config.torrent_seed_time = torrent_seed_time
        sickrage.app.config.torrent_paused = checkbox_to_value(torrent_paused)
        sickrage.app.config.torrent_high_bandwidth = checkbox_to_value(torrent_high_bandwidth)
        sickrage.app.config.torrent_host = clean_url(torrent_host)
        sickrage.app.config.torrent_rpcurl = torrent_rpcurl
        sickrage.app.config.torrent_auth_type = torrent_auth_type

        torrent_webui_url(True)

        sickrage.app.config.save()

        if len(results) > 0:
            [sickrage.app.log.error(x) for x in results]
            sickrage.app.alerts.error(_('Error(s) Saving Configuration'), '<br>\n'.join(results))
        else:
            sickrage.app.alerts.message(_('[SEARCH] Configuration Encrypted and Saved to SiCKRAGE Cloud'))

        return self.redirect("/config/search/")