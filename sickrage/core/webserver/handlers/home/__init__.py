import datetime
import os
from collections import OrderedDict
from functools import cmp_to_key
from urllib.parse import unquote_plus, quote_plus

from sqlalchemy import orm
from tornado import gen
from tornado.escape import json_encode

import sickrage
from sickrage.clients import getClientIstance
from sickrage.clients.sabnzbd import SabNZBd
from sickrage.core.blackandwhitelist import BlackAndWhiteList
from sickrage.core.common import Overview, Quality, cpu_presets, statusStrings, WANTED, FAILED, UNAIRED, IGNORED, \
    SKIPPED
from sickrage.core.databases.main import MainDB
from sickrage.core.exceptions import AnidbAdbaConnectionException, CantRefreshShowException, NoNFOException, \
    CantUpdateShowException, CantRemoveShowException, EpisodeDeletedException
from sickrage.core.helpers import app_statistics, clean_url, clean_host, clean_hosts, findCertainShow, \
    getDiskSpaceUsage, remove_article, checkbox_to_value, try_int
from sickrage.core.helpers.anidb import get_release_groups_for_anime, short_group_names
from sickrage.core.helpers.srdatetime import srDateTime
from sickrage.core.queues.search import BacklogQueueItem, FailedQueueItem, ManualSearchQueueItem, MANUAL_SEARCH_HISTORY
from sickrage.core.scene_exceptions import get_scene_exceptions, update_scene_exceptions
from sickrage.core.scene_numbering import get_scene_numbering_for_show, get_xem_numbering_for_show, \
    get_scene_absolute_numbering_for_show, get_xem_absolute_numbering_for_show, xem_refresh, set_scene_numbering, \
    get_scene_absolute_numbering, get_scene_numbering
from sickrage.core.traktapi import srTraktAPI
from sickrage.core.tv.episode import TVEpisode
from sickrage.core.webserver.handlers.base import BaseHandler
from sickrage.indexers import IndexerApi
from sickrage.subtitles import name_from_code


def _get_episode(show, season=None, episode=None, absolute=None):
    if show is None:
        return _("Invalid show parameters")

    showObj = findCertainShow(int(show))

    if showObj is None:
        return _("Invalid show paramaters")

    if absolute:
        epObj = showObj.get_episode(absolute_number=int(absolute))
    elif season and episode:
        epObj = showObj.get_episode(int(season), int(episode))
    else:
        return _("Invalid paramaters")

    if epObj is None:
        return _("Episode couldn't be retrieved")

    return epObj


def have_kodi():
    return sickrage.app.config.use_kodi and sickrage.app.config.kodi_update_library


def have_plex():
    return sickrage.app.config.use_plex and sickrage.app.config.plex_update_library


def have_emby():
    return sickrage.app.config.use_emby


def have_torrent():
    if sickrage.app.config.use_torrents and sickrage.app.config.torrent_method != 'blackhole' and \
            (sickrage.app.config.enable_https and sickrage.app.config.torrent_host[:5] == 'https' or not
            sickrage.app.config.enable_https and sickrage.app.config.torrent_host[:5] == 'http:'):
        return True
    return False


class HomeHandler(BaseHandler):
    def get(self):
        if not len(sickrage.app.showlist):
            return self.redirect('/home/addShows/')

        showlists = OrderedDict({'Shows': []})
        if sickrage.app.config.anime_split_home:
            for show in sickrage.app.showlist:
                if show.is_anime:
                    if 'Anime' not in list(showlists.keys()):
                        showlists['Anime'] = []
                    showlists['Anime'] += [show]
                else:
                    showlists['Shows'] += [show]
        else:
            showlists['Shows'] = sickrage.app.showlist

        app_stats = app_statistics()

        return self.render(
            "/home/index.mako",
            title="Home",
            header="Show List",
            topmenu="home",
            showlists=showlists,
            show_stat=app_stats[0],
            overall_stats=app_stats[1],
            max_download_count=app_stats[2],
            controller='home',
            action='index'
        )


class IsAliveHandler(BaseHandler):
    def get(self, *args, **kwargs):
        self.set_header('Content-Type', 'text/javascript')

        if not all([kwargs.get('srcallback'), kwargs.get('_')]):
            return _("Error: Unsupported Request. Send jsonp request with 'srcallback' variable in the query string.")

        if sickrage.app.started:
            return "%s({'msg':%s})" % (kwargs['srcallback'], str(sickrage.app.pid))
        else:
            return "%s({'msg':%s})" % (kwargs['srcallback'], "nope")


class TestSABnzbdHandler(BaseHandler):
    def get(self, host=None, username=None, password=None, apikey=None):
        host = clean_url(host)

        connection, accesMsg = SabNZBd.getSabAccesMethod(host)
        if connection:
            authed, authMsg = SabNZBd.test_authentication(host, username, password, apikey)
            if authed:
                return _('Success. Connected and authenticated')
            else:
                return _('Authentication failed. SABnzbd expects ') + accesMsg + _(
                    ' as authentication method, ') + authMsg
        else:
            return _('Unable to connect to host')


class TestTorrentHandler(BaseHandler):
    def get(self, torrent_method=None, host=None, username=None, password=None):
        host = clean_url(host)
        client = getClientIstance(torrent_method)
        __, accesMsg = client(host, username, password).test_authentication()
        return accesMsg


class TestFreeMobileHandler(BaseHandler):
    def get(self, freemobile_id=None, freemobile_apikey=None):
        result, message = sickrage.app.notifier_providers['freemobile'].test_notify(freemobile_id, freemobile_apikey)
        if result:
            return _('SMS sent successfully')
        else:
            return _('Problem sending SMS: ') + message


class TestTelegramHandler(BaseHandler):
    def get(self, telegram_id=None, telegram_apikey=None):
        result, message = sickrage.app.notifier_providers['telegram'].test_notify(telegram_id, telegram_apikey)
        if result:
            return _('Telegram notification succeeded. Check your Telegram clients to make sure it worked')
        else:
            return _('Error sending Telegram notification: {message}').format(message=message)


class TestJoinHandler(BaseHandler):
    def get(self, join_id=None, join_apikey=None):
        result, message = sickrage.app.notifier_providers['join'].test_notify(join_id, join_apikey)
        if result:
            return _('Join notification succeeded. Check your Join clients to make sure it worked')
        else:
            return _('Error sending Join notification: {message}').format(message=message)


class TestGrowlHandler(BaseHandler):
    def get(self, host=None, password=None):
        host = clean_host(host, default_port=23053)

        result = sickrage.app.notifier_providers['growl'].test_notify(host, password)
        if password is None or password == '':
            pw_append = ''
        else:
            pw_append = _(' with password: ') + password

        if result:
            return _('Registered and Tested growl successfully ') + unquote_plus(host) + pw_append
        else:
            return _('Registration and Testing of growl failed ') + unquote_plus(host) + pw_append


class TestProwlHandler(BaseHandler):
    def get(self, prowl_api=None, prowl_priority=0):
        result = sickrage.app.notifier_providers['prowl'].test_notify(prowl_api, prowl_priority)
        if result:
            return _('Test prowl notice sent successfully')
        else:
            return _('Test prowl notice failed')


class TestBoxcar2Handler(BaseHandler):
    def get(self, accesstoken=None):
        result = sickrage.app.notifier_providers['boxcar2'].test_notify(accesstoken)
        if result:
            return _('Boxcar2 notification succeeded. Check your Boxcar2 clients to make sure it worked')
        else:
            return _('Error sending Boxcar2 notification')


class TestPushoverHandler(BaseHandler):
    def get(self, userKey=None, apiKey=None):
        result = sickrage.app.notifier_providers['pushover'].test_notify(userKey, apiKey)
        if result:
            return _('Pushover notification succeeded. Check your Pushover clients to make sure it worked')
        return _('Error sending Pushover notification')


class TwitterStep1Handler(BaseHandler):
    def get(self, *args, **kwargs):
        return sickrage.app.notifier_providers['twitter']._get_authorization()


class TwitterStep2Handler(BaseHandler):
    def get(self, *args, **kwargs):
        key = self.get_argument('key')
        result = sickrage.app.notifier_providers['twitter']._get_credentials(key)
        sickrage.app.log.info("result: " + str(result))
        if result:
            return _('Key verification successful')
        return _('Unable to verify key')


class TestTwitterHandler(BaseHandler):
    def get(self, *args, **kwargs):
        result = sickrage.app.notifier_providers['twitter'].test_notify()
        if result:
            return _('Tweet successful, check your twitter to make sure it worked')
        return _('Error sending tweet')


class TestTwilioHandler(BaseHandler):
    def get(self, account_sid=None, auth_token=None, phone_sid=None, to_number=None):
        if not sickrage.app.notifier_providers['twilio'].account_regex.match(account_sid):
            return _('Please enter a valid account sid')

        if not sickrage.app.notifier_providers['twilio'].auth_regex.match(auth_token):
            return _('Please enter a valid auth token')

        if not sickrage.app.notifier_providers['twilio'].phone_regex.match(phone_sid):
            return _('Please enter a valid phone sid')

        if not sickrage.app.notifier_providers['twilio'].number_regex.match(to_number):
            return _('Please format the phone number as "+1-###-###-####"')

        result = sickrage.app.notifier_providers['twilio'].test_notify()
        if result:
            return _('Authorization successful and number ownership verified')
        else:
            return _('Error sending sms')


class TestSlackHandler(BaseHandler):
    def get(self):
        result = sickrage.app.notifier_providers['slack'].test_notify()
        if result:
            return _('Slack message successful')
        else:
            return _('Slack message failed')


class TestDiscordHandler(BaseHandler):
    def get(self):
        result = sickrage.app.notifier_providers['discord'].test_notify()
        if result:
            return _('Discord message successful')
        else:
            return _('Discord message failed')


class TestKODIHandler(BaseHandler):
    def get(self, host=None, username=None, password=None):

        host = clean_hosts(host)
        finalResult = ''
        for curHost in [x.strip() for x in host.split(",")]:
            curResult = sickrage.app.notifier_providers['kodi'].test_notify(unquote_plus(curHost), username,
                                                                            password)
            if len(curResult.split(":")) > 2 and 'OK' in curResult.split(":")[2]:
                finalResult += _('Test KODI notice sent successfully to ') + unquote_plus(curHost)
            else:
                finalResult += _('Test KODI notice failed to ') + unquote_plus(curHost)
            finalResult += "<br>\n"

        return finalResult


class TestPMCHandler(BaseHandler):
    def get(self, host=None, username=None, password=None):
        if None is not password and set('*') == set(password):
            password = sickrage.app.config.plex_client_password

        finalResult = ''
        for curHost in [x.strip() for x in host.split(',')]:
            curResult = sickrage.app.notifier_providers['plex'].test_notify_pmc(unquote_plus(curHost),
                                                                                username,
                                                                                password)
            if len(curResult.split(':')) > 2 and 'OK' in curResult.split(':')[2]:
                finalResult += _('Successful test notice sent to Plex client ... ') + unquote_plus(curHost)
            else:
                finalResult += _('Test failed for Plex client ... ') + unquote_plus(curHost)
            finalResult += '<br>' + '\n'

        sickrage.app.alerts.message(_('Tested Plex client(s): '),
                                    unquote_plus(host.replace(',', ', ')))

        return finalResult


class TestPMSHandler(BaseHandler):
    def get(self, host=None, username=None, password=None, plex_server_token=None):
        if password is not None and set('*') == set(password):
            password = sickrage.app.config.plex_password

        finalResult = ''

        curResult = sickrage.app.notifier_providers['plex'].test_notify_pms(unquote_plus(host), username,
                                                                            password,
                                                                            plex_server_token)
        if curResult is None:
            finalResult += _('Successful test of Plex server(s) ... ') + \
                           unquote_plus(host.replace(',', ', '))
        elif curResult is False:
            finalResult += _('Test failed, No Plex Media Server host specified')
        else:
            finalResult += _('Test failed for Plex server(s) ... ') + \
                           unquote_plus(str(curResult).replace(',', ', '))
        finalResult += '<br>' + '\n'

        sickrage.app.alerts.message(_('Tested Plex Media Server host(s): '),
                                    unquote_plus(host.replace(',', ', ')))

        return finalResult


class TestLibnotifyHandler(BaseHandler):
    def get(self):
        if sickrage.app.notifier_providers['libnotify'].notifier.test_notify():
            return _('Tried sending desktop notification via libnotify')
        else:
            return sickrage.app.notifier_providers['libnotify'].diagnose()


class TestEMBYHandler(BaseHandler):
    def get(self, host=None, emby_apikey=None):
        host = clean_host(host)
        result = sickrage.app.notifier_providers['emby'].test_notify(unquote_plus(host), emby_apikey)
        if result:
            return _('Test notice sent successfully to ') + unquote_plus(host)
        else:
            return _('Test notice failed to ') + unquote_plus(host)


class TestNMJHandler(BaseHandler):
    def get(self, host=None, database=None, mount=None):
        host = clean_host(host)
        result = sickrage.app.notifier_providers['nmj'].test_notify(unquote_plus(host), database, mount)
        if result:
            return _('Successfully started the scan update')
        else:
            return _('Test failed to start the scan update')


class SettingsNMJHandler(BaseHandler):
    def get(self, host=None):
        host = clean_host(host)
        result = sickrage.app.notifier_providers['nmj'].notify_settings(unquote_plus(host))
        if result:
            return '{"message": "%(message)s %(host)s", "database": "%(database)s", "mount": "%(mount)s"}' % {
                "message": _('Got settings from'),
                "host": host, "database": sickrage.app.config.nmj_database,
                "mount": sickrage.app.config.nmj_mount
            }
        else:
            message = _('Failed! Make sure your Popcorn is on and NMJ is running. (see Log & Errors -> Debug for '
                        'detailed info)')
            return '{"message": {}, "database": "", "mount": ""}'.format(message)


class TestNMJv2Handler(BaseHandler):
    def get(self, host=None):
        host = clean_host(host)
        result = sickrage.app.notifier_providers['nmjv2'].test_notify(unquote_plus(host))
        if result:
            return _('Test notice sent successfully to ') + unquote_plus(host)
        else:
            return _('Test notice failed to ') + unquote_plus(host)


class SettingsNMJv2Handler(BaseHandler):
    def get(self, host=None, dbloc=None, instance=None):
        host = clean_host(host)
        result = sickrage.app.notifier_providers['nmjv2'].notify_settings(unquote_plus(host), dbloc,
                                                                          instance)
        if result:
            return '{"message": "NMJ Database found at: %(host)s", "database": "%(database)s"}' % {"host": host,
                                                                                                   "database": sickrage.app.config.nmjv2_database}
        else:
            return '{"message": "Unable to find NMJ Database at location: %(dbloc)s. Is the right location selected and PCH running?", "database": ""}' % {
                "dbloc": dbloc}


class GetTraktTokenHandler(BaseHandler):
    def get(self, trakt_pin=None):
        if srTraktAPI().authenticate(trakt_pin):
            return _('Trakt Authorized')
        return _('Trakt Not Authorized!')


class TestTraktHandler(BaseHandler):
    def get(self, username=None, blacklist_name=None):
        return sickrage.app.notifier_providers['trakt'].test_notify(username, blacklist_name)


class LoadShowNotifyListsHandler(BaseHandler):
    def get(self):
        data = {'_size': 0}
        for s in sorted(sickrage.app.showlist, key=lambda k: k.name):
            data[s.indexerid] = {'id': s.indexerid, 'name': s.name, 'list': s.notify_list}
            data['_size'] += 1
        return json_encode(data)


class SaveShowNotifyListHandler(BaseHandler):
    def get(self, show=None, emails=None):
        try:
            show = findCertainShow(int(show))
            show.notify_list = emails
            show.save_to_db()
        except Exception:
            return 'ERROR'


class TestEmailHandler(BaseHandler):
    def get(self, host=None, port=None, smtp_from=None, use_tls=None, user=None, pwd=None, to=None):
        host = clean_host(host)
        if sickrage.app.notifier_providers['email'].test_notify(host, port, smtp_from, use_tls, user, pwd, to):
            return _('Test email sent successfully! Check inbox.')
        else:
            return _('ERROR: %s') % sickrage.app.notifier_providers['email'].last_err


class TestNMAHandler(BaseHandler):
    def get(self, nma_api=None, nma_priority=0):

        result = sickrage.app.notifier_providers['nma'].test_notify(nma_api, nma_priority)
        if result:
            return _('Test NMA notice sent successfully')
        else:
            return _('Test NMA notice failed')


class TestPushalotHandler(BaseHandler):
    def get(self, authorizationToken=None):
        result = sickrage.app.notifier_providers['pushalot'].test_notify(authorizationToken)
        if result:
            return _('Pushalot notification succeeded. Check your Pushalot clients to make sure it worked')
        else:
            return _('Error sending Pushalot notification')


class TestPushbulletHandler(BaseHandler):
    def get(self, api=None):
        result = sickrage.app.notifier_providers['pushbullet'].test_notify(api)
        if result:
            return _('Pushbullet notification succeeded. Check your device to make sure it worked')
        else:
            return _('Error sending Pushbullet notification')


class GetPushbulletDevicesHandler(BaseHandler):
    def get(api=None):
        result = sickrage.app.notifier_providers['pushbullet'].get_devices(api)
        if result:
            return result
        else:
            return _('Error getting Pushbullet devices')


class StatusHandler(BaseHandler):
    def get(self):
        tvdirFree = getDiskSpaceUsage(sickrage.app.config.tv_download_dir)
        rootDir = {}
        if sickrage.app.config.root_dirs:
            backend_pieces = sickrage.app.config.root_dirs.split('|')
            backend_dirs = backend_pieces[1:]
        else:
            backend_dirs = []

        if len(backend_dirs):
            for subject in backend_dirs:
                rootDir[subject] = getDiskSpaceUsage(subject)

        return self.render(
            "/home/status.mako",
            title=_('Status'),
            header=_('Status'),
            topmenu='system',
            tvdirFree=tvdirFree,
            rootDir=rootDir,
            controller='home',
            action='status'
        )


class ShutdownHandler(BaseHandler):
    def get(self, pid=None):
        if str(pid) != str(sickrage.app.pid):
            return self.redirect("/{}/".format(sickrage.app.config.default_page))

        self._genericMessage(_("Shutting down"), _("SiCKRAGE is shutting down"))
        sickrage.app.shutdown()


class RestartHandler(BaseHandler):
    def get(self, pid=None, force=False):
        if str(pid) != str(sickrage.app.pid) and not force:
            return self.redirect("/{}/".format(sickrage.app.config.default_page))

        # clear current user to disable header and footer
        self.current_user = None

        if not force:
            self._genericMessage(_("Restarting"), _("SiCKRAGE is restarting"))

        sickrage.app.io_loop.add_timeout(datetime.timedelta(seconds=5), sickrage.app.shutdown, restart=True)

        return self.render(
            "/home/restart.mako",
            title="Home",
            header="Restarting SiCKRAGE",
            topmenu="system",
            controller='home',
            action="restart",
        )  # if not force else 'SiCKRAGE is now restarting, please wait a minute then manually go back to the main page'


class UpdateCheckHandler(BaseHandler):
    def get(self, pid=None):
        if str(pid) != str(sickrage.app.pid):
            return self.redirect("/{}/".format(sickrage.app.config.default_page))

        sickrage.app.alerts.message(_("Updater"), _('Checking for updates'))

        # check for new app updates
        if not sickrage.app.version_updater.check_for_new_version(force=True):
            sickrage.app.alerts.message(_("Updater"), _('No new updates available!'))

        return self.redirect(self.previous_url())


class UpdateHandler(BaseHandler):
    def get(self, pid=None):
        if str(pid) != str(sickrage.app.pid):
            return self.redirect("/{}/".format(sickrage.app.config.default_page))

        sickrage.app.alerts.message(_("Updater"), _('Updating SiCKRAGE'))

        sickrage.app.event_queue.fire_event(sickrage.app.version_updater.update, webui=True)

        return self.redirect(self.previous_url())


class VerifyPathHandler(BaseHandler):
    def get(self, path):
        if os.path.isfile(path):
            return _('Successfully found {path}'.format(path=path))
        else:
            return _('Failed to find {path}'.format(path=path))


class InstallRequirementsHandler(BaseHandler):
    def get(self):
        sickrage.app.alerts.message(_('Installing SiCKRAGE requirements'))
        if not sickrage.app.version_updater.updater.install_requirements(
                sickrage.app.version_updater.updater.current_branch):
            sickrage.app.alerts.message(_('Failed to install SiCKRAGE requirements'))
        else:
            sickrage.app.alerts.message(_('Installed SiCKRAGE requirements successfully!'))

        return self.redirect(self.previous_url())


class BranchCheckoutHandler(BaseHandler):
    def get(self, branch):
        if branch and sickrage.app.version_updater.updater.current_branch != branch:
            sickrage.app.alerts.message(_('Checking out branch: '), branch)
            if sickrage.app.version_updater.updater.checkout_branch(branch):
                sickrage.app.alerts.message(_('Branch checkout successful, restarting: '), branch)
                return self.restart(sickrage.app.pid)
        else:
            sickrage.app.alerts.message(_('Already on branch: '), branch)

        return self.redirect(self.previous_url())


class DisplayShowHandler(BaseHandler):
    def get(self, *args, **kwargs):
        submenu = []

        show = self.get_argument('show')

        if show is None:
            return self._genericMessage(_("Error"), _("Invalid show ID"))
        else:
            showObj = findCertainShow(int(show))

            if showObj is None:
                return self._genericMessage(_("Error"), _("Show not in show list"))

        episodeResults = MainDB.TVEpisode.query.filter_by(showid=showObj.indexerid).order_by(
            MainDB.TVEpisode.season.desc(),
            MainDB.TVEpisode.episode.desc())

        seasonResults = list({x.season for x in episodeResults})

        submenu.append({
            'title': _('Edit'),
            'path': '/home/editShow?show=%d' % showObj.indexerid,
            'icon': 'fas fa-edit'
        })

        showLoc = showObj.location

        show_message = ''

        if sickrage.app.show_queue.is_being_added(showObj):
            show_message = _('This show is in the process of being downloaded - the info below is incomplete.')

        elif sickrage.app.show_queue.is_being_updated(showObj):
            show_message = _('The information on this page is in the process of being updated.')

        elif sickrage.app.show_queue.is_being_refreshed(showObj):
            show_message = _('The episodes below are currently being refreshed from disk')

        elif sickrage.app.show_queue.is_being_subtitled(showObj):
            show_message = _('Currently downloading subtitles for this show')

        elif sickrage.app.show_queue.is_in_refresh_queue(showObj):
            show_message = _('This show is queued to be refreshed.')

        elif sickrage.app.show_queue.is_in_update_queue(showObj):
            show_message = _('This show is queued and awaiting an update.')

        elif sickrage.app.show_queue.is_in_subtitle_queue(showObj):
            show_message = _('This show is queued and awaiting subtitles download.')

        if not sickrage.app.show_queue.is_being_added(showObj):
            if not sickrage.app.show_queue.is_being_updated(showObj):
                if showObj.paused:
                    submenu.append({
                        'title': _('Resume'),
                        'path': '/home/togglePause?show=%d' % showObj.indexerid,
                        'icon': 'fas fa-play'
                    })
                else:
                    submenu.append({
                        'title': _('Pause'),
                        'path': '/home/togglePause?show=%d' % showObj.indexerid,
                        'icon': 'fas fa-pause'
                    })

                submenu.append({
                    'title': _('Remove'),
                    'path': '/home/deleteShow?show=%d' % showObj.indexerid,
                    'class': 'removeshow',
                    'confirm': True,
                    'icon': 'fas fa-trash'
                })

                submenu.append({
                    'title': _('Re-scan files'),
                    'path': '/home/refreshShow?show=%d' % showObj.indexerid,
                    'icon': 'fas fa-compass'
                })

                submenu.append({
                    'title': _('Full Update'),
                    'path': '/home/updateShow?show=%d&amp;force=1' % showObj.indexerid,
                    'icon': 'fas fa-sync'
                })

                submenu.append({
                    'title': _('Update show in KODI'),
                    'path': '/home/updateKODI?show=%d' % showObj.indexerid,
                    'requires': have_kodi(),
                    'icon': 'fas fa-tv'
                })

                submenu.append({
                    'title': _('Update show in Emby'),
                    'path': '/home/updateEMBY?show=%d' % showObj.indexerid,
                    'requires': have_emby(),
                    'icon': 'fas fa-tv'
                })

                submenu.append({
                    'title': _('Preview Rename'),
                    'path': '/home/testRename?show=%d' % showObj.indexerid,
                    'icon': 'fas fa-tag'
                })

                if sickrage.app.config.use_subtitles and showObj.subtitles:
                    if not sickrage.app.show_queue.is_being_subtitled(showObj):
                        submenu.append({
                            'title': _('Download Subtitles'),
                            'path': '/home/subtitleShow?show=%d' % showObj.indexerid,
                            'icon': 'fas fa-comment'
                        })

        epCats = {}
        epCounts = {
            Overview.SKIPPED: 0,
            Overview.WANTED: 0,
            Overview.QUAL: 0,
            Overview.GOOD: 0,
            Overview.UNAIRED: 0,
            Overview.SNATCHED: 0,
            Overview.SNATCHED_PROPER: 0,
            Overview.SNATCHED_BEST: 0,
            Overview.MISSED: 0,
        }

        for curEp in episodeResults:
            curEpCat = showObj.get_overview(int(curEp.status or -1))

            if curEp.airdate != 1:
                today = datetime.datetime.now().replace(tzinfo=sickrage.app.tz)
                airDate = datetime.datetime.fromordinal(curEp.airdate)
                if airDate.year >= 1970 or showObj.network:
                    airDate = srDateTime(
                        sickrage.app.tz_updater.parse_date_time(curEp.airdate, showObj.airs, showObj.network),
                        convert=True).dt

                if curEpCat == Overview.WANTED and airDate < today:
                    curEpCat = Overview.MISSED

            if curEpCat:
                epCats[str(curEp.season) + "x" + str(curEp.episode)] = curEpCat
                epCounts[curEpCat] += 1

        def titler(x):
            return (remove_article(x), x)[not x or sickrage.app.config.sort_article]

        if sickrage.app.config.anime_split_home:
            shows = []
            anime = []
            for show in sickrage.app.showlist:
                if show.is_anime:
                    anime.append(show)
                else:
                    shows.append(show)

            sortedShowLists = {"Shows": sorted(shows, key=cmp_to_key(
                lambda x, y: titler(x.name).lower() < titler(y.name).lower())),
                               "Anime": sorted(anime, key=cmp_to_key(
                                   lambda x, y: titler(x.name).lower() < titler(y.name).lower()))}
        else:
            sortedShowLists = {"Shows": sorted(sickrage.app.showlist, key=cmp_to_key(
                lambda x, y: titler(x.name).lower() < titler(y.name).lower()))}

        bwl = None
        if showObj.is_anime:
            bwl = showObj.release_groups

        showObj.exceptions = get_scene_exceptions(showObj.indexerid)

        indexerid = int(showObj.indexerid)
        indexer = int(showObj.indexer)

        # Delete any previous occurrances
        for index, recentShow in enumerate(sickrage.app.config.shows_recent):
            if recentShow['indexerid'] == indexerid:
                del sickrage.app.config.shows_recent[index]

        # Only track 5 most recent shows
        del sickrage.app.config.shows_recent[4:]

        # Insert most recent show
        sickrage.app.config.shows_recent.insert(0, {
            'indexerid': indexerid,
            'name': showObj.name,
        })

        return self.render(
            "/home/display_show.mako",
            submenu=submenu,
            showLoc=showLoc,
            show_message=show_message,
            show=showObj,
            episodeResults=episodeResults,
            seasonResults=seasonResults,
            sortedShowLists=sortedShowLists,
            bwl=bwl,
            epCounts=epCounts,
            epCats=epCats,
            all_scene_exceptions=showObj.exceptions,
            scene_numbering=get_scene_numbering_for_show(indexerid, indexer),
            xem_numbering=get_xem_numbering_for_show(indexerid, indexer),
            scene_absolute_numbering=get_scene_absolute_numbering_for_show(indexerid, indexer),
            xem_absolute_numbering=get_xem_absolute_numbering_for_show(indexerid, indexer),
            title=showObj.name,
            controller='home',
            action="display_show"
        )


class EditShowHandler(BaseHandler):
    def get(self, show=None, location=None, anyQualities=None, bestQualities=None, exceptions_list=None,
            flatten_folders=None, paused=None, directCall=False, air_by_date=None, sports=None, dvdorder=None,
            indexerLang=None, subtitles=None, subtitles_sr_metadata=None, skip_downloaded=None,
            rls_ignore_words=None, rls_require_words=None, anime=None, blacklist=None, whitelist=None,
            scene=None, defaultEpStatus=None, quality_preset=None, search_delay=None):

        if exceptions_list is None:
            exceptions_list = []
        if bestQualities is None:
            bestQualities = []
        if anyQualities is None:
            anyQualities = []

        if show is None:
            errString = _("Invalid show ID: ") + str(show)
            if directCall:
                return [errString]
            else:
                return self._genericMessage(_("Error"), errString)

        showObj = findCertainShow(int(show))

        if not showObj:
            errString = _("Unable to find the specified show: ") + str(show)
            if directCall:
                return [errString]
            else:
                return self._genericMessage(_("Error"), errString)

        showObj.exceptions = get_scene_exceptions(showObj.indexerid)

        groups = []
        if not location and not anyQualities and not bestQualities and not quality_preset and not flatten_folders:
            if showObj.is_anime:
                whitelist = showObj.release_groups.whitelist
                blacklist = showObj.release_groups.blacklist

                try:
                    groups = get_release_groups_for_anime(showObj.name)
                except AnidbAdbaConnectionException as e:
                    sickrage.app.log.debug('Unable to get ReleaseGroups: {}'.format(e))

            with showObj.lock:
                scene_exceptions = get_scene_exceptions(showObj.indexerid)

            if showObj.is_anime:
                return self.render(
                    "/home/edit_show.mako",
                    show=showObj,
                    quality=showObj.quality,
                    scene_exceptions=scene_exceptions,
                    groups=groups,
                    whitelist=whitelist,
                    blacklist=blacklist,
                    title=_('Edit Show'),
                    header=_('Edit Show'),
                    controller='home',
                    action="edit_show"
                )
            else:
                return self.render(
                    "/home/edit_show.mako",
                    show=showObj,
                    quality=showObj.quality,
                    scene_exceptions=scene_exceptions,
                    title=_('Edit Show'),
                    header=_('Edit Show'),
                    controller='home',
                    action="edit_show"
                )

        flatten_folders = not checkbox_to_value(flatten_folders)  # UI inverts this value
        dvdorder = checkbox_to_value(dvdorder)
        skip_downloaded = checkbox_to_value(skip_downloaded)
        paused = checkbox_to_value(paused)
        air_by_date = checkbox_to_value(air_by_date)
        scene = checkbox_to_value(scene)
        sports = checkbox_to_value(sports)
        anime = checkbox_to_value(anime)
        subtitles = checkbox_to_value(subtitles)
        subtitles_sr_metadata = checkbox_to_value(subtitles_sr_metadata)

        if indexerLang and indexerLang in IndexerApi(showObj.indexer).indexer().languages.keys():
            indexer_lang = indexerLang
        else:
            indexer_lang = showObj.lang

        # if we changed the language then kick off an update
        if indexer_lang == showObj.lang:
            do_update = False
        else:
            do_update = True

        if scene == showObj.scene or anime == showObj.anime:
            do_update_scene_numbering = False
        else:
            do_update_scene_numbering = True

        if not isinstance(anyQualities, list):
            anyQualities = [anyQualities]

        if not isinstance(bestQualities, list):
            bestQualities = [bestQualities]

        if not isinstance(exceptions_list, list):
            exceptions_list = [exceptions_list]

        # If directCall from mass_edit_update no scene exceptions handling or blackandwhite list handling
        if directCall:
            do_update_exceptions = False
        else:
            if set(exceptions_list) == set(showObj.exceptions):
                do_update_exceptions = False
            else:
                do_update_exceptions = True

            with showObj.lock:
                if anime:
                    if not showObj.release_groups:
                        showObj.release_groups = BlackAndWhiteList(showObj.indexerid)

                    if whitelist:
                        shortwhitelist = short_group_names(whitelist)
                        showObj.release_groups.set_white_keywords(shortwhitelist)
                    else:
                        showObj.release_groups.set_white_keywords([])

                    if blacklist:
                        shortblacklist = short_group_names(blacklist)
                        showObj.release_groups.set_black_keywords(shortblacklist)
                    else:
                        showObj.release_groups.set_black_keywords([])

        warnings, errors = [], []

        with showObj.lock:
            newQuality = try_int(quality_preset, None)
            if not newQuality:
                newQuality = Quality.combine_qualities(list(map(int, anyQualities)), list(map(int, bestQualities)))

            showObj.quality = newQuality
            showObj.skip_downloaded = skip_downloaded

            # reversed for now
            if bool(showObj.flatten_folders) != bool(flatten_folders):
                showObj.flatten_folders = flatten_folders
                try:
                    sickrage.app.show_queue.refreshShow(showObj, True)
                except CantRefreshShowException as e:
                    errors.append(_("Unable to refresh this show: {}").format(e))

            showObj.paused = paused
            showObj.scene = scene
            showObj.anime = anime
            showObj.sports = sports
            showObj.subtitles = subtitles
            showObj.subtitles_sr_metadata = subtitles_sr_metadata
            showObj.air_by_date = air_by_date
            showObj.default_ep_status = int(defaultEpStatus)

            if not directCall:
                showObj.lang = indexer_lang
                showObj.dvdorder = dvdorder
                showObj.rls_ignore_words = rls_ignore_words.strip()
                showObj.rls_require_words = rls_require_words.strip()
                showObj.search_delay = int(search_delay)

            # if we change location clear the db of episodes, change it, write to db, and rescan
            if os.path.normpath(showObj.location) != os.path.normpath(location):
                sickrage.app.log.debug(os.path.normpath(showObj.location) + " != " + os.path.normpath(location))
                if not os.path.isdir(location) and not sickrage.app.config.create_missing_show_dirs:
                    warnings.append("New location {} does not exist".format(location))

                # don't bother if we're going to update anyway
                elif not do_update:
                    # change it
                    try:
                        showObj.location = location
                        try:
                            sickrage.app.show_queue.refreshShow(showObj, True)
                        except CantRefreshShowException as e:
                            errors.append(_("Unable to refresh this show:{}").format(e))
                            # grab updated info from TVDB
                            # showObj.loadEpisodesFromIndexer()
                            # rescan the episodes in the new folder
                    except NoNFOException:
                        warnings.append(
                            _("The folder at %s doesn't contain a tvshow.nfo - copy your files to that folder before "
                              "you change the directory in SiCKRAGE.") % location)

            # save it to the DB
            showObj.save_to_db()

        # force the update
        if do_update:
            try:
                sickrage.app.show_queue.updateShow(showObj, force=True)
                gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])
            except CantUpdateShowException as e:
                errors.append(_("Unable to update show: {}").format(e))

        if do_update_exceptions:
            try:
                update_scene_exceptions(showObj.indexerid, exceptions_list)
                gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])
            except CantUpdateShowException as e:
                warnings.append(_("Unable to force an update on scene exceptions of the show."))

        if do_update_scene_numbering:
            try:
                xem_refresh(showObj.indexerid, showObj.indexer, True)
                gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])
            except CantUpdateShowException as e:
                warnings.append(_("Unable to force an update on scene numbering of the show."))

        if directCall:
            return map(str, warnings + errors)

        if len(warnings) > 0:
            sickrage.app.alerts.message(
                _('{num_warnings:d} warning{plural} while saving changes:').format(num_warnings=len(warnings),
                                                                                   plural="" if len(
                                                                                       warnings) == 1 else "s"),
                '<ul>' + '\n'.join(['<li>{0}</li>'.format(warning) for warning in warnings]) + "</ul>")

        if len(errors) > 0:
            sickrage.app.alerts.error(
                _('{num_errors:d} error{plural} while saving changes:').format(num_errors=len(errors),
                                                                               plural="" if len(errors) == 1 else "s"),
                '<ul>' + '\n'.join(['<li>{0}</li>'.format(error) for error in errors]) + "</ul>")

        return self.redirect("/home/displayShow?show=" + show)


class TogglePauseHandler(BaseHandler):
    def get(self, show=None):
        if show is None:
            return self._genericMessage(_("Error"), _("Invalid show ID"))

        showObj = findCertainShow(int(show))

        if showObj is None:
            return self._genericMessage(_("Error"), _("Unable to find the specified show"))

        showObj.paused = not showObj.paused

        showObj.save_to_db()

        sickrage.app.alerts.message(
            _('%s has been %s') % (showObj.name, (_('resumed'), _('paused'))[showObj.paused]))

        return self.redirect("/home/displayShow?show=%i" % showObj.indexerid)


class DeleteShowHandler(BaseHandler):
    def get(self, show=None, full=0):
        if show is None:
            return self._genericMessage(_("Error"), _("Invalid show ID"))

        showObj = findCertainShow(int(show))

        if showObj is None:
            return self._genericMessage(_("Error"), _("Unable to find the specified show"))

        try:
            sickrage.app.show_queue.removeShow(showObj, bool(full))
            sickrage.app.alerts.message(
                _('%s has been %s %s') %
                (
                    showObj.name,
                    (_('deleted'), _('trashed'))[bool(sickrage.app.config.trash_remove_show)],
                    (_('(media untouched)'), _('(with all related media)'))[bool(full)]
                )
            )
        except CantRemoveShowException as e:
            sickrage.app.alerts.error(_('Unable to delete this show.'), str(e))

        gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])

        # Don't redirect to the default page, so the user can confirm that the show was deleted
        return self.redirect('/home/')


class RefreshShowHandler(BaseHandler):
    def get(self, show=None):
        if show is None:
            return self._genericMessage(_("Error"), _("Invalid show ID"))

        showObj = findCertainShow(int(show))

        if showObj is None:
            return self._genericMessage(_("Error"), _("Unable to find the specified show"))

        try:
            sickrage.app.show_queue.refreshShow(showObj, True)
        except CantRefreshShowException as e:
            sickrage.app.alerts.error(_('Unable to refresh this show.'), str(e))

        gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])

        return self.redirect("/home/displayShow?show=" + str(showObj.indexerid))


class UpdateShowHandler(BaseHandler):
    def get(self, show=None, force=0):
        if show is None:
            return self._genericMessage(_("Error"), _("Invalid show ID"))

        showObj = findCertainShow(int(show))

        if showObj is None:
            return self._genericMessage(_("Error"), _("Unable to find the specified show"))

        # force the update
        try:
            sickrage.app.show_queue.updateShow(showObj, force=bool(force))
        except CantUpdateShowException as e:
            sickrage.app.alerts.error(_("Unable to update this show."), str(e))

        # just give it some time
        gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])

        return self.redirect("/home/displayShow?show=" + str(showObj.indexerid))

class SubtitleShowHandler(BaseHandler):
    def get(self, show=None):

        if show is None:
            return self._genericMessage(_("Error"), _("Invalid show ID"))

        showObj = findCertainShow(int(show))

        if showObj is None:
            return self._genericMessage(_("Error"), _("Unable to find the specified show"))

        # search and download subtitles
        sickrage.app.show_queue.download_subtitles(showObj)

        gen.sleep(cpu_presets[sickrage.app.config.cpu_preset])

        return self.redirect("/home/displayShow?show=" + str(showObj.indexerid))

class UpdateKODIHandler(BaseHandler):
    def get(self, show=None):
        showName = None
        showObj = None

        if show:
            showObj = findCertainShow(int(show))
            if showObj:
                showName = quote_plus(showObj.name.encode())

        if sickrage.app.config.kodi_update_onlyfirst:
            host = sickrage.app.config.kodi_host.split(",")[0].strip()
        else:
            host = sickrage.app.config.kodi_host

        if sickrage.app.notifier_providers['kodi'].update_library(showName=showName):
            sickrage.app.alerts.message(_("Library update command sent to KODI host(s): ") + host)
        else:
            sickrage.app.alerts.error(_("Unable to contact one or more KODI host(s): ") + host)

        if showObj:
            return self.redirect('/home/displayShow?show=' + str(showObj.indexerid))
        else:
            return self.redirect('/home/')

class UpdatePLEXHandler(BaseHandler):
    def get(self):
        if None is sickrage.app.notifier_providers['plex'].update_library():
            sickrage.app.alerts.message(
                _("Library update command sent to Plex Media Server host: ") +
                sickrage.app.config.plex_server_host)
        else:
            sickrage.app.alerts.error(
                _("Unable to contact Plex Media Server host: ") +
                sickrage.app.config.plex_server_host)
        return self.redirect('/home/')

class UpdateEMBYHandler(BaseHandler):
    def get(self, show=None):
        showObj = None

        if show:
            showObj = findCertainShow(int(show))

        if sickrage.app.notifier_providers['emby'].update_library(showObj):
            sickrage.app.alerts.message(
                _("Library update command sent to Emby host: ") + sickrage.app.config.emby_host)
        else:
            sickrage.app.alerts.error(
                _("Unable to contact Emby host: ") + sickrage.app.config.emby_host)

        if showObj:
            return self.redirect('/home/displayShow?show=' + str(showObj.indexerid))
        else:
            return self.redirect('/home/')

class SyncTraktHandler(BaseHandler):
    def get(self):
        if sickrage.app.scheduler.get_job('TRAKTSEARCHER').func():
            sickrage.app.log.info("Syncing Trakt with SiCKRAGE")
            sickrage.app.alerts.message(_('Syncing Trakt with SiCKRAGE'))

        return self.redirect("/home/")

class DeleteEpisodeHandler(BaseHandler):
    def get(self, show=None, eps=None, direct=False):
        if not all([show, eps]):
            errMsg = _("You must specify a show and at least one episode")
            if direct:
                sickrage.app.alerts.error(_('Error'), errMsg)
                return json_encode({'result': 'error'})
            else:
                return self._genericMessage(_("Error"), errMsg)

        showObj = findCertainShow(int(show))
        if not showObj:
            errMsg = _("Error", "Show not in show list")
            if direct:
                sickrage.app.alerts.error(_('Error'), errMsg)
                return json_encode({'result': 'error'})
            else:
                return self._genericMessage(_("Error"), errMsg)

        if eps:
            for curEp in eps.split('|'):
                if not curEp:
                    sickrage.app.log.debug("curEp was empty when trying to deleteEpisode")

                sickrage.app.log.debug("Attempting to delete episode " + curEp)

                epInfo = curEp.split('x')

                if not all(epInfo):
                    sickrage.app.log.debug(
                        "Something went wrong when trying to deleteEpisode, epInfo[0]: %s, epInfo[1]: %s" % (
                            epInfo[0], epInfo[1]))
                    continue

                epObj = showObj.get_episode(int(epInfo[0]), int(epInfo[1]))
                if not epObj:
                    return self._genericMessage(_("Error"), _("Episode couldn't be retrieved"))

                with epObj.lock:
                    try:
                        epObj.deleteEpisode(full=True)
                    except EpisodeDeletedException:
                        pass

        if direct:
            return json_encode({'result': 'success'})
        else:
            return self.redirect("/home/displayShow?show=" + show)

class SetStatusHandler(BaseHandler):
    def get(self, show=None, eps=None, status=None, direct=False):
        if not all([show, eps, status]):
            errMsg = _("You must specify a show and at least one episode")
            if direct:
                sickrage.app.alerts.error(_('Error'), errMsg)
                return json_encode({'result': 'error'})
            else:
                return self._genericMessage(_("Error"), errMsg)

        if int(status) not in statusStrings:
            errMsg = _("Invalid status")
            if direct:
                sickrage.app.alerts.error(_('Error'), errMsg)
                return json_encode({'result': 'error'})
            else:
                return self._genericMessage(_("Error"), errMsg)

        showObj = findCertainShow(int(show))

        if not showObj:
            errMsg = _("Error", "Show not in show list")
            if direct:
                sickrage.app.alerts.error(_('Error'), errMsg)
                return json_encode({'result': 'error'})
            else:
                return self._genericMessage(_("Error"), errMsg)

        segments = {}
        trakt_data = []
        if eps:
            for curEp in eps.split('|'):

                if not curEp:
                    sickrage.app.log.debug("curEp was empty when trying to setStatus")

                sickrage.app.log.debug("Attempting to set status on episode " + curEp + " to " + status)

                epInfo = curEp.split('x')

                if not all(epInfo):
                    sickrage.app.log.debug(
                        "Something went wrong when trying to setStatus, epInfo[0]: %s, epInfo[1]: %s" % (
                            epInfo[0], epInfo[1]))
                    continue

                epObj = showObj.get_episode(int(epInfo[0]), int(epInfo[1]))

                if not epObj:
                    return self._genericMessage(_("Error"), _("Episode couldn't be retrieved"))

                if int(status) in [WANTED, FAILED]:
                    # figure out what episodes are wanted so we can backlog them
                    if epObj.season in segments:
                        segments[epObj.season].append(epObj)
                    else:
                        segments[epObj.season] = [epObj]

                with epObj.lock:
                    # don't let them mess up UNAIRED episodes
                    if epObj.status == UNAIRED:
                        sickrage.app.log.warning(
                            "Refusing to change status of " + curEp + " because it is UNAIRED")
                        continue

                    if int(status) in Quality.DOWNLOADED and epObj.status not in Quality.SNATCHED + \
                            Quality.SNATCHED_PROPER + Quality.SNATCHED_BEST + Quality.DOWNLOADED + [
                        IGNORED] and not os.path.isfile(epObj.location):
                        sickrage.app.log.warning(
                            "Refusing to change status of " + curEp + " to DOWNLOADED because it's not SNATCHED/DOWNLOADED")
                        continue

                    if int(status) == FAILED and epObj.status not in Quality.SNATCHED + Quality.SNATCHED_PROPER + \
                            Quality.SNATCHED_BEST + Quality.DOWNLOADED + Quality.ARCHIVED:
                        sickrage.app.log.warning(
                            "Refusing to change status of " + curEp + " to FAILED because it's not SNATCHED/DOWNLOADED")
                        continue

                    if epObj.status in Quality.DOWNLOADED + Quality.ARCHIVED and int(status) == WANTED:
                        sickrage.app.log.info(
                            "Removing release_name for episode as you want to set a downloaded episode back to wanted, so obviously you want it replaced")
                        epObj.release_name = ""

                    epObj.status = int(status)

                    # save to database
                    epObj.save_to_db()

                    trakt_data.append((epObj.season, epObj.episode))

            data = sickrage.app.notifier_providers['trakt'].trakt_episode_data_generate(trakt_data)
            if data and sickrage.app.config.use_trakt and sickrage.app.config.trakt_sync_watchlist:
                if int(status) in [WANTED, FAILED]:
                    sickrage.app.log.debug(
                        "Add episodes, showid: indexerid " + str(showObj.indexerid) + ", Title " + str(
                            showObj.name) + " to Watchlist")
                    sickrage.app.notifier_providers['trakt'].update_watchlist(showObj, data_episode=data,
                                                                              update="add")
                elif int(status) in [IGNORED, SKIPPED] + Quality.DOWNLOADED + Quality.ARCHIVED:
                    sickrage.app.log.debug(
                        "Remove episodes, showid: indexerid " + str(showObj.indexerid) + ", Title " + str(
                            showObj.name) + " from Watchlist")
                    sickrage.app.notifier_providers['trakt'].update_watchlist(showObj, data_episode=data,
                                                                              update="remove")

        if int(status) == WANTED and not showObj.paused:
            msg = _(
                "Backlog was automatically started for the following seasons of ") + "<b>" + showObj.name + "</b>:<br>"
            msg += '<ul>'

            for season, segment in segments.items():
                sickrage.app.search_queue.put(BacklogQueueItem(showObj, segment))

                msg += "<li>" + _("Season ") + str(season) + "</li>"
                sickrage.app.log.info("Sending backlog for " + showObj.name + " season " + str(
                    season) + " because some eps were set to wanted")

            msg += "</ul>"

            if segments:
                sickrage.app.alerts.message(_("Backlog started"), msg)
        elif int(status) == WANTED and showObj.paused:
            sickrage.app.log.info(
                "Some episodes were set to wanted, but " + showObj.name + " is paused. Not adding to Backlog until show is unpaused")

        if int(status) == FAILED:
            msg = _(
                "Retrying Search was automatically started for the following season of ") + "<b>" + showObj.name + "</b>:<br>"
            msg += '<ul>'

            for season, segment in segments.items():
                sickrage.app.search_queue.put(FailedQueueItem(showObj, segment))

                msg += "<li>" + _("Season ") + str(season) + "</li>"
                sickrage.app.log.info("Retrying Search for " + showObj.name + " season " + str(
                    season) + " because some eps were set to failed")

            msg += "</ul>"

            if segments:
                sickrage.app.alerts.message(_("Retry Search started"), msg)

        if direct:
            return json_encode({'result': 'success'})
        else:
            return self.redirect("/home/displayShow?show=" + show)

class TestRenameHandler(BaseHandler):
    def get(self, show=None):

        if show is None:
            return self._genericMessage(_("Error"), _("You must specify a show"))

        showObj = findCertainShow(int(show))

        if showObj is None:
            return self._genericMessage(_("Error"), _("Show not in show list"))

        if not os.path.isdir(showObj.location):
            return self._genericMessage(_("Error"), _("Can't rename episodes when the show dir is missing."))

        ep_obj_rename_list = []

        ep_obj_list = showObj.get_all_episodes(has_location=True)

        for cur_ep_obj in ep_obj_list:
            # Only want to rename if we have a location
            if cur_ep_obj.location:
                if cur_ep_obj.relatedEps:
                    # do we have one of multi-episodes in the rename list already
                    have_already = False
                    for cur_related_ep in cur_ep_obj.relatedEps + [cur_ep_obj]:
                        if cur_related_ep in ep_obj_rename_list:
                            have_already = True
                            break
                        if not have_already:
                            ep_obj_rename_list.append(cur_ep_obj)
                else:
                    ep_obj_rename_list.append(cur_ep_obj)

        if ep_obj_rename_list:
            # present season DESC episode DESC on screen
            ep_obj_rename_list.reverse()

        submenu = [
            {'title': _('Edit'), 'path': '/home/editShow?show=%d' % showObj.indexerid,
             'icon': 'fas fa-edit'}]

        return self.render(
            "/home/test_renaming.mako",
            submenu=submenu,
            ep_obj_list=ep_obj_rename_list,
            show=showObj,
            title=_('Preview Rename'),
            header=_('Preview Rename'),
            controller='home',
            action="test_renaming"
        )

class DoRenameHandler(BaseHandler):
    def get(self, show=None, eps=None):
        if show is None or eps is None:
            errMsg = _("You must specify a show and at least one episode")
            return self._genericMessage(_("Error"), errMsg)

        show_obj = findCertainShow(int(show))

        if show_obj is None:
            errMsg = _("Show not in show list")
            return self._genericMessage(_("Error"), errMsg)

        if not os.path.isdir(show_obj.location):
            return self._genericMessage(_("Error"), _("Can't rename episodes when the show dir is missing."))

        if eps is None:
            return self.redirect("/home/displayShow?show=" + show)

        for curEp in eps.split('|'):
            epInfo = curEp.split('x')

            try:
                ep_result = MainDB.TVEpisode.query.filter_by(showid=int(show), season=int(epInfo[0]),
                                                             episode=int(epInfo[1])).one()
            except orm.exc.NoResultFound:
                sickrage.app.log.warning("Unable to find an episode for " + curEp + ", skipping")
                continue

            root_ep_obj = show_obj.get_episode(int(epInfo[0]), int(epInfo[1]))
            root_ep_obj.relatedEps = []

            for cur_related_ep in MainDB.TVEpisode.query.filter_by(location=ep_result.location).filter(
                    MainDB.TVEpisode.episode != int(epInfo[1])):
                related_ep_obj = show_obj.get_episode(int(cur_related_ep.season), int(cur_related_ep.episode))
                if related_ep_obj not in root_ep_obj.relatedEps:
                    root_ep_obj.relatedEps.append(related_ep_obj)

            root_ep_obj.rename()

        return self.redirect("/home/displayShow?show=" + show)

class SearchEpisodeHandler(BaseHandler):
    def get(self, show=None, season=None, episode=None, downCurQuality=0):
        # retrieve the episode object and fail if we can't get one
        ep_obj = _get_episode(show, season, episode)
        if isinstance(ep_obj, TVEpisode):
            # make a queue item for it and put it on the queue
            ep_queue_item = ManualSearchQueueItem(ep_obj.show, ep_obj, bool(int(downCurQuality)))

            sickrage.app.search_queue.put(ep_queue_item)
            if not all([ep_queue_item.started, ep_queue_item.success]):
                return json_encode({'result': 'success'})
        return json_encode({'result': 'failure'})

class GetManualSearchStatusHandler(BaseHandler):
    def get(self, show=None):
        def getEpisodes(searchThread, searchstatus):
            results = []
            showObj = findCertainShow(int(searchThread.show.indexerid))

            if not showObj:
                sickrage.app.log.warning(
                    'No Show Object found for show with indexerID: ' + str(searchThread.show.indexerid))
                return results

            if isinstance(searchThread, ManualSearchQueueItem):
                results.append({'show': searchThread.show.indexerid,
                                'episode': searchThread.segment.episode,
                                'episodeindexid': searchThread.segment.indexerid,
                                'season': searchThread.segment.season,
                                'searchstatus': searchstatus,
                                'status': statusStrings[searchThread.segment.status],
                                'quality': self.getQualityClass(searchThread.segment),
                                'overview': Overview.overviewStrings[
                                    showObj.get_overview(int(searchThread.segment.status or -1))]})
            else:
                for epObj in searchThread.segment:
                    results.append({'show': epObj.show.indexerid,
                                    'episode': epObj.episode,
                                    'episodeindexid': epObj.indexerid,
                                    'season': epObj.season,
                                    'searchstatus': searchstatus,
                                    'status': statusStrings[epObj.status],
                                    'quality': self.getQualityClass(epObj),
                                    'overview': Overview.overviewStrings[
                                        showObj.get_overview(int(epObj.status or -1))]})

            return results

        episodes = []

        # Queued Searches
        searchstatus = 'queued'
        for searchThread in sickrage.app.search_queue.get_all_ep_from_queue(show):
            episodes += getEpisodes(searchThread, searchstatus)

        # Running Searches
        searchstatus = 'searching'
        if sickrage.app.search_queue.is_manualsearch_in_progress():
            searchThread = sickrage.app.search_queue.current_item

            if searchThread.success:
                searchstatus = 'finished'

            episodes += getEpisodes(searchThread, searchstatus)

        # Finished Searches
        searchstatus = 'finished'
        for searchThread in MANUAL_SEARCH_HISTORY:
            if show is not None:
                if not str(searchThread.show.indexerid) == show:
                    continue

            if isinstance(searchThread, ManualSearchQueueItem):
                if not [x for x in episodes if x['episodeindexid'] == searchThread.segment.indexerid]:
                    episodes += getEpisodes(searchThread, searchstatus)
            else:
                ### These are only Failed Downloads/Retry SearchThreadItems.. lets loop through the segement/episodes
                if not [i for i, j in zip(searchThread.segment, episodes) if i.indexerid == j['episodeindexid']]:
                    episodes += getEpisodes(searchThread, searchstatus)

        return json_encode({'episodes': episodes})

class GetQualityClassHandler(BaseHandler):
    def get(self, ep_obj):
        # return the correct json value

        # Find the quality class for the episode
        __, ep_quality = Quality.split_composite_status(ep_obj.status)
        if ep_quality in Quality.cssClassStrings:
            quality_class = Quality.cssClassStrings[ep_quality]
        else:
            quality_class = Quality.cssClassStrings[Quality.UNKNOWN]

        return quality_class


class SearchEpisodeSubtitlesHandler(BaseHandler):
    def get(self, show=None, season=None, episode=None):
        # retrieve the episode object and fail if we can't get one
        ep_obj = _get_episode(show, season, episode)
        if isinstance(ep_obj, TVEpisode):
            try:
                newSubtitles = ep_obj.download_subtitles()
            except Exception:
                return json_encode({'result': 'failure'})

            if newSubtitles:
                newLangs = [name_from_code(newSub) for newSub in newSubtitles]
                status = _('New subtitles downloaded: %s') % ', '.join([newLang for newLang in newLangs])
            else:
                status = _('No subtitles downloaded')

            sickrage.app.alerts.message(ep_obj.show.name, status)
            return json_encode({'result': status, 'subtitles': ','.join(ep_obj.subtitles)})

        return json_encode({'result': 'failure'})

class SetSceneNumberingHandler(BaseHandler):
    def get(self, show, indexer, forSeason=None, forEpisode=None, forAbsolute=None, sceneSeason=None,
                          sceneEpisode=None, sceneAbsolute=None):

        # sanitize:
        if forSeason in ['null', '']:
            forSeason = None
        if forEpisode in ['null', '']:
            forEpisode = None
        if forAbsolute in ['null', '']:
            forAbsolute = None
        if sceneSeason in ['null', '']:
            sceneSeason = None
        if sceneEpisode in ['null', '']:
            sceneEpisode = None
        if sceneAbsolute in ['null', '']:
            sceneAbsolute = None

        showObj = findCertainShow(int(show))

        if showObj.is_anime:
            result = {
                'success': True,
                'forAbsolute': forAbsolute,
            }
        else:
            result = {
                'success': True,
                'forSeason': forSeason,
                'forEpisode': forEpisode,
            }

        # retrieve the episode object and fail if we can't get one
        if showObj.is_anime:
            ep_obj = _get_episode(show, absolute=forAbsolute)
        else:
            ep_obj = _get_episode(show, forSeason, forEpisode)

        if isinstance(ep_obj, str):
            result['success'] = False
            result['errorMessage'] = ep_obj
        elif showObj.is_anime:
            sickrage.app.log.debug("setAbsoluteSceneNumbering for %s from %s to %s" %
                                   (show, forAbsolute, sceneAbsolute))

            show = int(show)
            indexer = int(indexer)
            forAbsolute = int(forAbsolute)
            if sceneAbsolute is not None:
                sceneAbsolute = int(sceneAbsolute)

            set_scene_numbering(show, indexer, absolute_number=forAbsolute, sceneAbsolute=sceneAbsolute)
        else:
            sickrage.app.log.debug("setEpisodeSceneNumbering for %s from %sx%s to %sx%s" %
                                   (show, forSeason, forEpisode, sceneSeason, sceneEpisode))

            show = int(show)
            indexer = int(indexer)
            forSeason = int(forSeason)
            forEpisode = int(forEpisode)
            if sceneSeason is not None:
                sceneSeason = int(sceneSeason)
            if sceneEpisode is not None:
                sceneEpisode = int(sceneEpisode)

            set_scene_numbering(show, indexer, season=forSeason, episode=forEpisode, sceneSeason=sceneSeason,
                                sceneEpisode=sceneEpisode)

        if showObj.is_anime:
            sn = get_scene_absolute_numbering(show, indexer, forAbsolute)
            if sn:
                result['sceneAbsolute'] = sn
            else:
                result['sceneAbsolute'] = None
        else:
            sn = get_scene_numbering(show, indexer, forSeason, forEpisode)
            if sn:
                (result['sceneSeason'], result['sceneEpisode']) = sn
            else:
                (result['sceneSeason'], result['sceneEpisode']) = (None, None)

        return json_encode(result)


class RetryEpisodeHandler(BaseHandler):
    def get(self, show, season, episode, downCurQuality):
        # retrieve the episode object and fail if we can't get one
        ep_obj = _get_episode(show, season, episode)
        if isinstance(ep_obj, TVEpisode):
            # make a queue item for it and put it on the queue
            ep_queue_item = FailedQueueItem(ep_obj.show, [ep_obj], bool(int(downCurQuality)))

            sickrage.app.search_queue.put(ep_queue_item)
            if not all([ep_queue_item.started, ep_queue_item.success]):
                return json_encode({'result': 'success'})
        return json_encode({'result': 'failure'})


class FetchReleasegroupsHandler(BaseHandler):
    async def get(self, show_name):
        sickrage.app.log.info('ReleaseGroups: {}'.format(show_name))

        try:
            groups = await get_release_groups_for_anime(show_name)
            sickrage.app.log.info('ReleaseGroups: {}'.format(groups))
        except AnidbAdbaConnectionException as e:
            sickrage.app.log.debug('Unable to get ReleaseGroups: {}'.format(e))
        else:
            return json_encode({'result': 'success', 'groups': groups})

        return json_encode({'result': 'failure'})
