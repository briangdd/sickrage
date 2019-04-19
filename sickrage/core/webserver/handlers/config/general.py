#  Author: echel0n <echel0n@sickrage.ca>
#  URL: https://sickrage.ca/
#  Git: https://git.sickrage.ca/SiCKRAGE/sickrage.git
#
#  This file is part of SiCKRAGE.
#
#  SiCKRAGE is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SiCKRAGE is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SiCKRAGE.  If not, see <http://www.gnu.org/licenses/>.

import os

import sickrage
from sickrage.core import common
from sickrage.core.common import Quality
from sickrage.core.helpers import generateApiKey, checkbox_to_value, try_int
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/config/general(/?.*)')
class ConfigGeneral(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigGeneral, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/config/general.mako",
            title=_('Config - General'),
            header=_('General Configuration'),
            topmenu='config',
            submenu=self.ConfigMenu(),
            controller='config',
            action='general',
        )

    @staticmethod
    def generateApiKey():
        return generateApiKey()

    @staticmethod
    def saveRootDirs(rootDirString=None):
        sickrage.app.config.root_dirs = rootDirString

    @staticmethod
    def saveAddShowDefaults(defaultStatus, anyQualities, bestQualities, defaultFlattenFolders, subtitles=False,
                            anime=False, scene=False, defaultStatusAfter=common.WANTED, skip_downloaded=False,
                            add_show_year=False):

        if anyQualities:
            anyQualities = anyQualities.split(',')
        else:
            anyQualities = []

        if bestQualities:
            bestQualities = bestQualities.split(',')
        else:
            bestQualities = []

        newQuality = Quality.combine_qualities(map(int, anyQualities), map(int, bestQualities))

        sickrage.app.config.status_default = int(defaultStatus)
        sickrage.app.config.status_default_after = int(defaultStatusAfter)
        sickrage.app.config.quality_default = int(newQuality)

        sickrage.app.config.flatten_folders_default = checkbox_to_value(defaultFlattenFolders)
        sickrage.app.config.subtitles_default = checkbox_to_value(subtitles)

        sickrage.app.config.anime_default = checkbox_to_value(anime)
        sickrage.app.config.scene_default = checkbox_to_value(scene)
        sickrage.app.config.skip_downloaded_default = checkbox_to_value(skip_downloaded)
        sickrage.app.config.add_show_year_default = checkbox_to_value(add_show_year)

        sickrage.app.config.save()

    def saveGeneral(self, log_dir=None, log_nr=5, log_size=1048576, web_port=None, web_log=None,
                    web_ipv6=None, trash_remove_show=None, trash_rotate_logs=None,
                    update_frequency=None, skip_removed_files=None, indexerDefaultLang='en',
                    ep_default_deleted_status=None, launch_browser=None, showupdate_hour=3,
                    api_key=None, indexer_default=None, timezone_display=None, cpu_preset='NORMAL',
                    version_notify=None, enable_https=None, https_cert=None, https_key=None, handle_reverse_proxy=None,
                    sort_article=None, auto_update=None, notify_on_update=None, proxy_setting=None, proxy_indexers=None,
                    anon_redirect=None, git_path=None, pip3_path=None, calendar_unprotected=None, calendar_icons=None,
                    debug=None, ssl_verify=None, no_restart=None, coming_eps_missed_range=None, filter_row=None,
                    fuzzy_dating=None, trim_zero=None, date_preset=None, date_preset_na=None, time_preset=None,
                    indexer_timeout=None, download_url=None, rootDir=None, theme_name=None, default_page=None,
                    git_reset=None, git_username=None, git_password=None, git_autoissues=None, gui_language=None,
                    display_all_seasons=None, showupdate_stale=None, notify_on_login=None, allowed_video_file_exts=None,
                    enable_api_providers_cache=None, enable_upnp=None, web_external_port=None,
                    strip_special_file_bits=None, **kwargs):

        results = []

        # API
        sickrage.app.config.enable_api_providers_cache = checkbox_to_value(enable_api_providers_cache)

        # Language
        sickrage.app.config.change_gui_lang(gui_language)

        # Debug
        sickrage.app.config.debug = checkbox_to_value(debug)
        sickrage.app.log.set_level()

        # Misc
        sickrage.app.config.enable_upnp = checkbox_to_value(enable_upnp)
        sickrage.app.config.download_url = download_url
        sickrage.app.config.indexer_default_language = indexerDefaultLang
        sickrage.app.config.ep_default_deleted_status = ep_default_deleted_status
        sickrage.app.config.skip_removed_files = checkbox_to_value(skip_removed_files)
        sickrage.app.config.launch_browser = checkbox_to_value(launch_browser)
        sickrage.app.config.change_showupdate_hour(showupdate_hour)
        sickrage.app.config.change_version_notify(checkbox_to_value(version_notify))
        sickrage.app.config.auto_update = checkbox_to_value(auto_update)
        sickrage.app.config.notify_on_update = checkbox_to_value(notify_on_update)
        sickrage.app.config.notify_on_login = checkbox_to_value(notify_on_login)
        sickrage.app.config.showupdate_stale = checkbox_to_value(showupdate_stale)
        sickrage.app.config.log_nr = log_nr
        sickrage.app.config.log_size = log_size

        sickrage.app.config.trash_remove_show = checkbox_to_value(trash_remove_show)
        sickrage.app.config.trash_rotate_logs = checkbox_to_value(trash_rotate_logs)
        sickrage.app.config.change_updater_freq(update_frequency)
        sickrage.app.config.launch_browser = checkbox_to_value(launch_browser)
        sickrage.app.config.sort_article = checkbox_to_value(sort_article)
        sickrage.app.config.cpu_preset = cpu_preset
        sickrage.app.config.anon_redirect = anon_redirect
        sickrage.app.config.proxy_setting = proxy_setting
        sickrage.app.config.proxy_indexers = checkbox_to_value(proxy_indexers)
        sickrage.app.config.git_username = git_username
        sickrage.app.config.git_password = git_password
        sickrage.app.config.git_reset = 1
        sickrage.app.config.git_autoissues = checkbox_to_value(git_autoissues)
        sickrage.app.config.git_path = git_path
        sickrage.app.config.pip3_path = pip3_path
        sickrage.app.config.calendar_unprotected = checkbox_to_value(calendar_unprotected)
        sickrage.app.config.calendar_icons = checkbox_to_value(calendar_icons)
        sickrage.app.config.no_restart = checkbox_to_value(no_restart)

        sickrage.app.config.ssl_verify = checkbox_to_value(ssl_verify)
        sickrage.app.config.coming_eps_missed_range = try_int(coming_eps_missed_range, 7)
        sickrage.app.config.display_all_seasons = checkbox_to_value(display_all_seasons)

        sickrage.app.config.web_port = try_int(web_port)
        sickrage.app.config.web_ipv6 = checkbox_to_value(web_ipv6)

        sickrage.app.config.filter_row = checkbox_to_value(filter_row)
        sickrage.app.config.fuzzy_dating = checkbox_to_value(fuzzy_dating)
        sickrage.app.config.trim_zero = checkbox_to_value(trim_zero)

        sickrage.app.config.allowed_video_file_exts = [x.lower() for x in allowed_video_file_exts.split(',')]

        sickrage.app.config.strip_special_file_bits = checkbox_to_value(strip_special_file_bits)

        # sickrage.app.config.change_web_external_port(web_external_port)

        if date_preset:
            sickrage.app.config.date_preset = date_preset

        if indexer_default:
            sickrage.app.config.indexer_default = try_int(indexer_default)

        if indexer_timeout:
            sickrage.app.config.indexer_timeout = try_int(indexer_timeout)

        if time_preset:
            sickrage.app.config.time_preset_w_seconds = time_preset
            sickrage.app.config.time_preset = sickrage.app.config.time_preset_w_seconds.replace(":%S", "")

        sickrage.app.config.timezone_display = timezone_display

        sickrage.app.config.api_key = api_key

        sickrage.app.config.enable_https = checkbox_to_value(enable_https)

        if not sickrage.app.config.change_https_cert(https_cert):
            results += [
                "Unable to create directory " + os.path.normpath(https_cert) + ", https cert directory not changed."]

        if not sickrage.app.config.change_https_key(https_key):
            results += [
                "Unable to create directory " + os.path.normpath(https_key) + ", https key directory not changed."]

        sickrage.app.config.handle_reverse_proxy = checkbox_to_value(handle_reverse_proxy)

        sickrage.app.config.theme_name = theme_name

        sickrage.app.config.default_page = default_page

        sickrage.app.config.save()

        if len(results) > 0:
            [sickrage.app.log.error(x) for x in results]
            sickrage.app.alerts.error(_('Error(s) Saving Configuration'), '<br>\n'.join(results))
        else:
            sickrage.app.alerts.message(_('[GENERAL] Configuration Encrypted and Saved to SiCKRAGE Cloud'))

        return self.redirect("/config/general/")
