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

from sqlalchemy import or_
from tornado.escape import json_encode

import sickrage
from sickrage.core.databases.main import MainDB
from sickrage.core.common import SNATCHED, Quality, Overview
from sickrage.core.exceptions import CantUpdateShowException, CantRefreshShowException
from sickrage.core.helpers import try_int, findCertainShow
from sickrage.core.webserver.views import WebHandler


@Route('/manage(/?.*)')
class Manage(WebHandler):
    def __init__(self, *args, **kwargs):
        super(Manage, self).__init__(*args, **kwargs)

    def index(self):
        return self.redirect('/manage/massUpdate')

    @staticmethod
    def showEpisodeStatuses(indexer_id, whichStatus):
        status_list = [int(whichStatus)]
        if status_list[0] == SNATCHED:
            status_list = Quality.SNATCHED + Quality.SNATCHED_PROPER

        result = {}
        for dbData in MainDB.TVEpisode.query.filter_by(showid=int(indexer_id)).filter(MainDB.TVEpisode.season != 0,
                                                                                      MainDB.TVEpisode.status.in_(
                                                                                          status_list)):
            cur_season = int(dbData.season)
            cur_episode = int(dbData.episode)

            if cur_season not in result:
                result[cur_season] = {}

            result[cur_season][cur_episode] = dbData.name

        return json_encode(result)

    def episodeStatuses(self, whichStatus=None):
        ep_counts = {}
        show_names = {}
        sorted_show_ids = []
        status_list = []

        if whichStatus:
            status_list = [int(whichStatus)]
            if int(whichStatus) == SNATCHED:
                status_list = Quality.SNATCHED + Quality.SNATCHED_PROPER + Quality.SNATCHED_BEST

        # if we have no status then this is as far as we need to go
        if len(status_list):
            for cur_status_result in sorted((s for s in sickrage.app.showlist for __ in
                                             MainDB.TVEpisode.query.filter_by(showid=s.indexerid).filter(
                                                 MainDB.TVEpisode.status.in_(status_list),
                                                 MainDB.TVEpisode.season != 0)), key=lambda d: d.name):
                cur_indexer_id = int(cur_status_result.indexerid)
                if cur_indexer_id not in ep_counts:
                    ep_counts[cur_indexer_id] = 1
                else:
                    ep_counts[cur_indexer_id] += 1

                show_names[cur_indexer_id] = cur_status_result.name
                if cur_indexer_id not in sorted_show_ids:
                    sorted_show_ids.append(cur_indexer_id)

        return self.render(
            "/manage/episode_statuses.mako",
            title="Episode Overview",
            header="Episode Overview",
            topmenu='manage',
            whichStatus=whichStatus,
            show_names=show_names,
            ep_counts=ep_counts,
            sorted_show_ids=sorted_show_ids,
            controller='manage',
            action='episode_statuses'
        )

    def changeEpisodeStatuses(self, oldStatus, newStatus, *args, **kwargs):
        status_list = [int(oldStatus)]
        if status_list[0] == SNATCHED:
            status_list = Quality.SNATCHED + Quality.SNATCHED_PROPER

        to_change = {}

        # make a list of all shows and their associated args
        for arg in kwargs:
            indexer_id, what = arg.split('-')

            # we don't care about unchecked checkboxes
            if kwargs[arg] != 'on':
                continue

            if indexer_id not in to_change:
                to_change[indexer_id] = []

            to_change[indexer_id].append(what)

        for cur_indexer_id in to_change:
            # get a list of all the eps we want to change if they just said "all"
            if 'all' in to_change[cur_indexer_id]:
                all_eps = ['{}x{}'.format(x.season, x.episode) for x in
                           MainDB.TVEpisode.query.filter_by(showid=int(cur_indexer_id)).filter(
                               MainDB.TVEpisode.status.in_(status_list), MainDB.TVEpisode.season != 0)]
                to_change[cur_indexer_id] = all_eps

            self.setStatus(cur_indexer_id, '|'.join(to_change[cur_indexer_id]), newStatus, direct=True)

        return self.redirect('/manage/episodeStatuses/')

    @staticmethod
    def showSubtitleMissed(indexer_id, whichSubs):
        result = {}
        for dbData in MainDB.TVEpisode.query.filter_by(showid=int(indexer_id)).filter(
                MainDB.TVEpisode.status.endswith(4),
                MainDB.TVEpisode.season != 0):
            if whichSubs == 'all':
                if not frozenset(sickrage.subtitles.wanted_languages()).difference(dbData["subtitles"].split(',')):
                    continue
            elif whichSubs in dbData["subtitles"]:
                continue

            cur_season = int(dbData["season"])
            cur_episode = int(dbData["episode"])

            if cur_season not in result:
                result[cur_season] = {}

            if cur_episode not in result[cur_season]:
                result[cur_season][cur_episode] = {}

            result[cur_season][cur_episode]["name"] = dbData["name"]

            result[cur_season][cur_episode]["subtitles"] = dbData["subtitles"]

        return json_encode(result)

    def subtitleMissed(self, whichSubs=None):
        ep_counts = {}
        show_names = {}
        sorted_show_ids = []
        status_results = []

        if whichSubs:
            for s in sickrage.app.showlist:
                if not s.subtitles == 1:
                    continue

                for e in MainDB.TVEpisode.query.filter_by(showid=s.indexerid).filter(
                        or_(MainDB.TVEpisode.status.endswith(4), MainDB.TVEpisode.status.endswith(6)),
                        MainDB.TVEpisode.season != 0):
                    status_results += [{
                        'show_name': s.name,
                        'indexer_id': s.indexerid,
                        'subtitles': e.subtitles
                    }]

            for cur_status_result in sorted(status_results, key=lambda k: k['show_name']):
                if whichSubs == 'all':
                    if not frozenset(sickrage.subtitles.wanted_languages()).difference(
                            cur_status_result["subtitles"].split(',')):
                        continue
                elif whichSubs in cur_status_result["subtitles"]:
                    continue

                cur_indexer_id = int(cur_status_result["indexer_id"])
                if cur_indexer_id not in ep_counts:
                    ep_counts[cur_indexer_id] = 1
                else:
                    ep_counts[cur_indexer_id] += 1

                show_names[cur_indexer_id] = cur_status_result["show_name"]
                if cur_indexer_id not in sorted_show_ids:
                    sorted_show_ids.append(cur_indexer_id)

        return self.render(
            "/manage/subtitles_missed.mako",
            whichSubs=whichSubs,
            show_names=show_names,
            ep_counts=ep_counts,
            sorted_show_ids=sorted_show_ids,
            title=_('Missing Subtitles'),
            header=_('Missing Subtitles'),
            topmenu='manage',
            controller='manage',
            action='subtitles_missed'
        )

    def downloadSubtitleMissed(self, *args, **kwargs):
        to_download = {}

        # make a list of all shows and their associated args
        for arg in kwargs:
            indexer_id, what = arg.split('-')

            # we don't care about unchecked checkboxes
            if kwargs[arg] != 'on':
                continue

            if indexer_id not in to_download:
                to_download[indexer_id] = []

            to_download[indexer_id].append(what)

        for cur_indexer_id in to_download:
            # get a list of all the eps we want to download subtitles if they just said "all"
            if 'all' in to_download[cur_indexer_id]:
                to_download[cur_indexer_id] = ['{}x{}'.format(x.season, x.episode) for x in
                                               MainDB.TVEpisode.query.filter_by(showid=int(cur_indexer_id)).filter(
                                                   MainDB.TVEpisode.status.endswith(4), MainDB.TVEpisode.season != 0)]

            for epResult in to_download[cur_indexer_id]:
                season, episode = epResult.split('x')

                show = findCertainShow(int(cur_indexer_id))
                show.get_episode(int(season), int(episode)).download_subtitles()

        return self.redirect('/manage/subtitleMissed/')

    def backlogShow(self, indexer_id):
        show_obj = findCertainShow(int(indexer_id))

        if show_obj:
            sickrage.app.backlog_searcher.search_backlog([show_obj])

        return self.redirect("/manage/backlogOverview/")

    def backlogOverview(self):
        showCounts = {}
        showCats = {}
        showResults = {}

        for curShow in sickrage.app.showlist:
            if curShow.paused:
                continue

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

            showResults[curShow.indexerid] = []

            for curResult in MainDB.TVEpisode.query.filter_by(showid=curShow.indexerid).order_by(
                    MainDB.TVEpisode.season.desc(),
                    MainDB.TVEpisode.episode.desc()):
                curEpCat = curShow.get_overview(int(curResult.status or -1))
                if curEpCat:
                    epCats["{}x{}".format(curResult.season, curResult.episode)] = curEpCat
                    epCounts[curEpCat] += 1

                showResults[curShow.indexerid] += [curResult]

            showCounts[curShow.indexerid] = epCounts
            showCats[curShow.indexerid] = epCats

        return self.render(
            "/manage/backlog_overview.mako",
            showCounts=showCounts,
            showCats=showCats,
            showResults=showResults,
            title=_('Backlog Overview'),
            header=_('Backlog Overview'),
            topmenu='manage',
            controller='manage',
            action='backlog_overview'
        )

    def massEdit(self, toEdit=None):
        if not toEdit:
            return self.redirect("/manage/")

        showIDs = toEdit.split("|")
        showList = []
        showNames = []
        for curID in showIDs:
            curID = int(curID)
            showObj = findCertainShow(curID)
            if showObj:
                showList.append(showObj)
                showNames.append(showObj.name)

        skip_downloaded_all_same = True
        last_skip_downloaded = None

        flatten_folders_all_same = True
        last_flatten_folders = None

        paused_all_same = True
        last_paused = None

        default_ep_status_all_same = True
        last_default_ep_status = None

        anime_all_same = True
        last_anime = None

        sports_all_same = True
        last_sports = None

        quality_all_same = True
        last_quality = None

        subtitles_all_same = True
        last_subtitles = None

        scene_all_same = True
        last_scene = None

        air_by_date_all_same = True
        last_air_by_date = None

        root_dir_list = []

        for curShow in showList:

            cur_root_dir = os.path.dirname(curShow.location)
            if cur_root_dir not in root_dir_list:
                root_dir_list.append(cur_root_dir)

            if skip_downloaded_all_same:
                # if we had a value already and this value is different then they're not all the same
                if last_skip_downloaded not in (None, curShow.skip_downloaded):
                    skip_downloaded_all_same = False
                else:
                    last_skip_downloaded = curShow.skip_downloaded

            # if we know they're not all the same then no point even bothering
            if paused_all_same:
                # if we had a value already and this value is different then they're not all the same
                if last_paused not in (None, curShow.paused):
                    paused_all_same = False
                else:
                    last_paused = curShow.paused

            if default_ep_status_all_same:
                if last_default_ep_status not in (None, curShow.default_ep_status):
                    default_ep_status_all_same = False
                else:
                    last_default_ep_status = curShow.default_ep_status

            if anime_all_same:
                # if we had a value already and this value is different then they're not all the same
                if last_anime not in (None, curShow.is_anime):
                    anime_all_same = False
                else:
                    last_anime = curShow.anime

            if flatten_folders_all_same:
                if last_flatten_folders not in (None, curShow.flatten_folders):
                    flatten_folders_all_same = False
                else:
                    last_flatten_folders = curShow.flatten_folders

            if quality_all_same:
                if last_quality not in (None, curShow.quality):
                    quality_all_same = False
                else:
                    last_quality = curShow.quality

            if subtitles_all_same:
                if last_subtitles not in (None, curShow.subtitles):
                    subtitles_all_same = False
                else:
                    last_subtitles = curShow.subtitles

            if scene_all_same:
                if last_scene not in (None, curShow.scene):
                    scene_all_same = False
                else:
                    last_scene = curShow.scene

            if sports_all_same:
                if last_sports not in (None, curShow.sports):
                    sports_all_same = False
                else:
                    last_sports = curShow.sports

            if air_by_date_all_same:
                if last_air_by_date not in (None, curShow.air_by_date):
                    air_by_date_all_same = False
                else:
                    last_air_by_date = curShow.air_by_date

        skip_downloaded_value = last_skip_downloaded if skip_downloaded_all_same else None
        default_ep_status_value = last_default_ep_status if default_ep_status_all_same else None
        paused_value = last_paused if paused_all_same else None
        anime_value = last_anime if anime_all_same else None
        flatten_folders_value = last_flatten_folders if flatten_folders_all_same else None
        quality_value = last_quality if quality_all_same else None
        subtitles_value = last_subtitles if subtitles_all_same else None
        scene_value = last_scene if scene_all_same else None
        sports_value = last_sports if sports_all_same else None
        air_by_date_value = last_air_by_date if air_by_date_all_same else None
        root_dir_list = root_dir_list

        return self.render(
            "/manage/mass_edit.mako",
            showList=toEdit,
            showNames=showNames,
            skip_downloaded_value=skip_downloaded_value,
            default_ep_status_value=default_ep_status_value,
            paused_value=paused_value,
            anime_value=anime_value,
            flatten_folders_value=flatten_folders_value,
            quality_value=quality_value,
            subtitles_value=subtitles_value,
            scene_value=scene_value,
            sports_value=sports_value,
            air_by_date_value=air_by_date_value,
            root_dir_list=root_dir_list,
            title=_('Mass Edit'),
            header=_('Mass Edit'),
            topmenu='manage',
            controller='manage',
            action='mass_edit'
        )

    def massEditSubmit(self, skip_downloaded=None, paused=None, default_ep_status=None,
                       anime=None, sports=None, scene=None, flatten_folders=None, quality_preset=None,
                       subtitles=None, air_by_date=None, anyQualities=None, bestQualities=None, toEdit=None, **kwargs):
        if bestQualities is None:
            bestQualities = []
        if anyQualities is None:
            anyQualities = []
        dir_map = {}
        for cur_arg in kwargs:
            if not cur_arg.startswith('orig_root_dir_'):
                continue
            which_index = cur_arg.replace('orig_root_dir_', '')
            end_dir = kwargs['new_root_dir_' + which_index]
            dir_map[kwargs[cur_arg]] = end_dir

        showIDs = toEdit.split("|")
        errors = []
        for curShow in showIDs:
            curErrors = []
            showObj = findCertainShow(int(curShow))
            if not showObj:
                continue

            cur_root_dir = os.path.dirname(showObj.location)
            cur_show_dir = os.path.basename(showObj.location)
            if cur_root_dir in dir_map and cur_root_dir != dir_map[cur_root_dir]:
                new_show_dir = os.path.join(dir_map[cur_root_dir], cur_show_dir)
                sickrage.app.log.info(
                    "For show " + showObj.name + " changing dir from " + showObj.location + " to " + new_show_dir)
            else:
                new_show_dir = showObj.location

            if skip_downloaded == 'keep':
                new_skip_downloaded = showObj.skip_downloaded
            else:
                new_skip_downloaded = True if skip_downloaded == 'enable' else False
            new_skip_downloaded = 'on' if new_skip_downloaded else 'off'

            if paused == 'keep':
                new_paused = showObj.paused
            else:
                new_paused = True if paused == 'enable' else False
            new_paused = 'on' if new_paused else 'off'

            if default_ep_status == 'keep':
                new_default_ep_status = showObj.default_ep_status
            else:
                new_default_ep_status = default_ep_status

            if anime == 'keep':
                new_anime = showObj.anime
            else:
                new_anime = True if anime == 'enable' else False
            new_anime = 'on' if new_anime else 'off'

            if sports == 'keep':
                new_sports = showObj.sports
            else:
                new_sports = True if sports == 'enable' else False
            new_sports = 'on' if new_sports else 'off'

            if scene == 'keep':
                new_scene = showObj.is_scene
            else:
                new_scene = True if scene == 'enable' else False
            new_scene = 'on' if new_scene else 'off'

            if air_by_date == 'keep':
                new_air_by_date = showObj.air_by_date
            else:
                new_air_by_date = True if air_by_date == 'enable' else False
            new_air_by_date = 'on' if new_air_by_date else 'off'

            if flatten_folders == 'keep':
                new_flatten_folders = showObj.flatten_folders
            else:
                new_flatten_folders = True if flatten_folders == 'enable' else False
            new_flatten_folders = 'on' if new_flatten_folders else 'off'

            if subtitles == 'keep':
                new_subtitles = showObj.subtitles
            else:
                new_subtitles = True if subtitles == 'enable' else False

            new_subtitles = 'on' if new_subtitles else 'off'

            if quality_preset == 'keep':
                anyQualities, bestQualities = Quality.split_quality(showObj.quality)
            elif try_int(quality_preset, None):
                bestQualities = []

            exceptions_list = []

            curErrors += [self.editShow(curShow, new_show_dir, anyQualities,
                                        bestQualities, exceptions_list,
                                        defaultEpStatus=new_default_ep_status,
                                        skip_downloaded=new_skip_downloaded,
                                        flatten_folders=new_flatten_folders,
                                        paused=new_paused, sports=new_sports,
                                        subtitles=new_subtitles, anime=new_anime,
                                        scene=new_scene, air_by_date=new_air_by_date,
                                        directCall=True)]

            if curErrors:
                sickrage.app.log.error("Errors: " + str(curErrors))
                errors.append('<b>%s:</b>\n<ul>' % showObj.name + ' '.join(
                    ['<li>%s</li>' % error for error in curErrors]) + "</ul>")

        if len(errors) > 0:
            sickrage.app.alerts.error(
                _('{num_errors:d} error{plural} while saving changes:').format(num_errors=len(errors),
                                                                               plural="" if len(errors) == 1 else "s"),
                " ".join(errors))

        return self.redirect("/manage/")

    def massUpdate(self, toUpdate=None, toRefresh=None, toRename=None, toDelete=None, toRemove=None, toMetadata=None,
                   toSubtitle=None):

        if toUpdate is not None:
            toUpdate = toUpdate.split('|')
        else:
            toUpdate = []

        if toRefresh is not None:
            toRefresh = toRefresh.split('|')
        else:
            toRefresh = []

        if toRename is not None:
            toRename = toRename.split('|')
        else:
            toRename = []

        if toSubtitle is not None:
            toSubtitle = toSubtitle.split('|')
        else:
            toSubtitle = []

        if toDelete is not None:
            toDelete = toDelete.split('|')
        else:
            toDelete = []

        if toRemove is not None:
            toRemove = toRemove.split('|')
        else:
            toRemove = []

        if toMetadata is not None:
            toMetadata = toMetadata.split('|')
        else:
            toMetadata = []

        errors = []
        refreshes = []
        updates = []
        renames = []
        subtitles = []

        for curShowID in set(toUpdate + toRefresh + toRename + toSubtitle + toDelete + toRemove + toMetadata):

            if curShowID == '':
                continue

            showObj = findCertainShow(int(curShowID))

            if showObj is None:
                continue

            if curShowID in toDelete:
                sickrage.app.show_queue.removeShow(showObj, True)
                # don't do anything else if it's being deleted
                continue

            if curShowID in toRemove:
                sickrage.app.show_queue.removeShow(showObj)
                # don't do anything else if it's being remove
                continue

            if curShowID in toUpdate:
                try:
                    sickrage.app.show_queue.updateShow(showObj, force=True)
                    updates.append(showObj.name)
                except CantUpdateShowException as e:
                    errors.append(_("Unable to update show: {}").format(e))

            # don't bother refreshing shows that were updated anyway
            if curShowID in toRefresh and curShowID not in toUpdate:
                try:
                    sickrage.app.show_queue.refreshShow(showObj, True)
                    refreshes.append(showObj.name)
                except CantRefreshShowException as e:
                    errors.append(_("Unable to refresh show ") + showObj.name + ": {}".format(e))

            if curShowID in toRename:
                sickrage.app.show_queue.renameShowEpisodes(showObj)
                renames.append(showObj.name)

            if curShowID in toSubtitle:
                sickrage.app.show_queue.download_subtitles(showObj)
                subtitles.append(showObj.name)

        if errors:
            sickrage.app.alerts.error(_("Errors encountered"),
                                      '<br >\n'.join(errors))

        messageDetail = ""

        if updates:
            messageDetail += _("<br><b>Updates</b><br><ul><li>")
            messageDetail += "</li><li>".join(updates)
            messageDetail += "</li></ul>"

        if refreshes:
            messageDetail += _("<br><b>Refreshes</b><br><ul><li>")
            messageDetail += "</li><li>".join(refreshes)
            messageDetail += "</li></ul>"

        if renames:
            messageDetail += _("<br><b>Renames</b><br><ul><li>")
            messageDetail += "</li><li>".join(renames)
            messageDetail += "</li></ul>"

        if subtitles:
            messageDetail += _("<br><b>Subtitles</b><br><ul><li>")
            messageDetail += "</li><li>".join(subtitles)
            messageDetail += "</li></ul>"

        if updates + refreshes + renames + subtitles:
            sickrage.app.alerts.message(_("The following actions were queued:"),
                                        messageDetail)

        return self.render(
            '/manage/mass_update.mako',
            title=_('Mass Update'),
            header=_('Mass Update'),
            topmenu='manage',
            controller='manage',
            action='mass_update'
        )

    def failedDownloads(self, limit=100, toRemove=None):
        if int(limit) == 0:
            dbData = MainDB.FailedSnatch.query.all()
        else:
            dbData = MainDB.FailedSnatch.query.limit(int(limit))

        toRemove = toRemove.split("|") if toRemove is not None else []
        if toRemove:
            sickrage.app.main_db.delete(MainDB.FailedSnatch, MainDB.FailedSnatch.release.in_(toRemove))
            return self.redirect('/manage/failedDownloads/')

        return self.render(
            "/manage/failed_downloads.mako",
            limit=int(limit),
            failedResults=dbData,
            title=_('Failed Downloads'),
            header=_('Failed Downloads'),
            topmenu='manage',
            controller='manage',
            action='failed_downloads'
        )
