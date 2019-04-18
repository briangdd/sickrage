import os
import re
from urllib.parse import unquote_plus, urlencode

from tornado.escape import json_encode
from tornado.httpclient import AsyncHTTPClient

import sickrage
from sickrage.core.classes import AllShowsUI
from sickrage.core.common import Quality
from sickrage.core.helpers import sanitizeFileName, findCertainShow, makeDir, chmod_as_parent, checkbox_to_value, \
    try_int
from sickrage.core.helpers.anidb import short_group_names
from sickrage.core.imdb_popular import imdbPopular
from sickrage.core.traktapi import srTraktAPI
from sickrage.core.webserver.handlers.base import BaseHandler
from sickrage.indexers import IndexerApi


def split_extra_show(extra_show):
    if not extra_show:
        return None, None, None, None
    split_vals = extra_show.split('|')
    if len(split_vals) < 4:
        indexer = split_vals[0]
        show_dir = split_vals[1]
        return indexer, show_dir, None, None
    indexer = split_vals[0]
    show_dir = split_vals[1]
    indexer_id = split_vals[2]
    show_name = '|'.join(split_vals[3:])

    return indexer, show_dir, indexer_id, show_name


class HomeAddShowsHandler(BaseHandler):
    def get(self):
        return self.render(
            "/home/add_shows.mako",
            title=_('Add Shows'),
            header=_('Add Shows'),
            topmenu='home',
            controller='home',
            action='add_shows'
        )


class SearchIndexersForShowNameHandler(BaseHandler):
    def get(search_term, lang=None, indexer=None):
        if not lang or lang == 'null':
            lang = sickrage.app.config.indexer_default_language

        results = {}
        final_results = []

        # Query Indexers for each search term and build the list of results
        for indexer in IndexerApi().indexers if not int(indexer) else [int(indexer)]:
            lINDEXER_API_PARMS = IndexerApi(indexer).api_params.copy()
            lINDEXER_API_PARMS['language'] = lang
            lINDEXER_API_PARMS['custom_ui'] = AllShowsUI
            t = IndexerApi(indexer).indexer(**lINDEXER_API_PARMS)

            sickrage.app.log.debug("Searching for Show with searchterm: %s on Indexer: %s" % (
                search_term, IndexerApi(indexer).name))

            try:
                # search via seriesname
                results.setdefault(indexer, []).extend(t[search_term])
            except Exception:
                continue

        for i, shows in results.items():
            final_results.extend([[IndexerApi(i).name, i, IndexerApi(i).config["show_url"],
                                   int(show['id']), show['seriesname'], show['firstaired'],
                                   ('', 'disabled')[bool(findCertainShow(show['id'], False))]] for show in shows])

        lang_id = IndexerApi().indexer().languages[lang] or 7
        return json_encode({'results': final_results, 'langid': lang_id})


class MassAddTableHandler(BaseHandler):
    def get(self, rootDir=None):
        if not rootDir:
            return _('No folders selected.')
        elif not isinstance(rootDir, list):
            root_dirs = [rootDir]
        else:
            root_dirs = rootDir

        root_dirs = [unquote_plus(x) for x in root_dirs]

        if sickrage.app.config.root_dirs:
            default_index = int(sickrage.app.config.root_dirs.split('|')[0])
        else:
            default_index = 0

        if len(root_dirs) > default_index:
            tmp = root_dirs[default_index]
            if tmp in root_dirs:
                root_dirs.remove(tmp)
                root_dirs = [tmp] + root_dirs

        dir_list = []

        for root_dir in root_dirs:
            try:
                file_list = os.listdir(root_dir)
            except Exception:
                continue

            for cur_file in file_list:
                try:
                    cur_path = os.path.normpath(os.path.join(root_dir, cur_file))
                    if not os.path.isdir(cur_path):
                        continue

                    # ignore Synology folders
                    if cur_file.lower() in ['#recycle', '@eadir']:
                        continue

                    cur_dir = {
                        'dir': cur_path,
                        'display_dir': '<b>{}{}</b>{}'.format(os.path.dirname(cur_path), os.sep,
                                                              os.path.basename(cur_path)),
                    }

                    # see if the folder is in database already
                    if [x for x in sickrage.app.showlist if x.location == cur_path]:
                        cur_dir['added_already'] = True
                    else:
                        cur_dir['added_already'] = False

                    dir_list.append(cur_dir)

                    showid = show_name = indexer = None
                    for cur_provider in sickrage.app.metadata_providers.values():
                        if all([showid, show_name, indexer]):
                            continue

                        (showid, show_name, indexer) = cur_provider.retrieveShowMetadata(cur_path)

                        # default to TVDB if indexer was not detected
                        if show_name and not (indexer or showid):
                            (sn, idxr, i) = IndexerApi(indexer).searchForShowID(show_name, showid)

                            # set indexer and indexer_id from found info
                            if not indexer and idxr:
                                indexer = idxr

                            if not showid and i:
                                showid = i

                    cur_dir['existing_info'] = (showid, show_name, indexer)
                    if showid and findCertainShow(showid):
                        cur_dir['added_already'] = True
                except Exception:
                    pass

        return self.render(
            "/home/mass_add_table.mako",
            dirList=dir_list,
            controller='home',
            action="mass_add_table"
        )


class NewShowHandler(BaseHandler):
    def get(self, show_to_add=None, other_shows=None, search_string=None):
        """
        Display the new show page which collects a tvdb id, folder, and extra options and
        posts them to addNewShow
        """

        indexer, show_dir, indexer_id, show_name = split_extra_show(show_to_add)

        use_provided_info = False
        if indexer_id and indexer and show_name:
            use_provided_info = True

        # use the given show_dir for the indexer search if available
        default_show_name = show_name or ''
        if not show_dir and search_string:
            default_show_name = search_string
        elif not show_name and show_dir:
            default_show_name = re.sub(r' \(\d{4}\)', '',
                                       os.path.basename(os.path.normpath(show_dir)).replace('.', ' '))

        # carry a list of other dirs if given
        if not other_shows:
            other_shows = []
        elif not isinstance(other_shows, list):
            other_shows = [other_shows]

        provided_indexer_id = int(indexer_id or 0)
        provided_indexer_name = show_name or ''
        provided_indexer = int(indexer or sickrage.app.config.indexer_default)

        return self.render(
            "/home/new_show.mako",
            enable_anime_options=True,
            use_provided_info=use_provided_info,
            default_show_name=default_show_name,
            other_shows=other_shows,
            provided_show_dir=show_dir,
            provided_indexer_id=provided_indexer_id,
            provided_indexer_name=provided_indexer_name,
            provided_indexer=provided_indexer,
            indexers=IndexerApi().indexers,
            quality=sickrage.app.config.quality_default,
            whitelist=[],
            blacklist=[],
            groups=[],
            title=_('New Show'),
            header=_('New Show'),
            topmenu='home',
            controller='home',
            action="new_show"
        )


class TraktShowsHandler(BaseHandler):
    def get(self, list='trending', limit=10):
        """
        Display the new show page which collects a tvdb id, folder, and extra options and
        posts them to addNewShow
        """

        trakt_shows, black_list = getattr(srTraktAPI()['shows'], list)(extended="full", limit=limit), False

        # filter shows
        trakt_shows = [x for x in trakt_shows if
                       'tvdb' in x.ids and not findCertainShow(int(x.ids['tvdb']))]

        return self.render("/home/trakt_shows.mako",
                           title="Trakt {} Shows".format(list.capitalize()),
                           header="Trakt {} Shows".format(list.capitalize()),
                           enable_anime_options=False,
                           black_list=black_list,
                           trakt_shows=trakt_shows,
                           trakt_list=list,
                           limit=limit,
                           controller='home',
                           action="trakt_shows")


class PopularShowsHandler(BaseHandler):
    def get(self):
        """
        Fetches data from IMDB to show a list of popular shows.
        """
        e = None

        try:
            popular_shows = imdbPopular().fetch_popular_shows()
        except Exception as e:
            popular_shows = None

        return self.render("/home/imdb_shows.mako",
                           title="IMDB Popular Shows",
                           header="IMDB Popular Shows",
                           popular_shows=popular_shows,
                           imdb_exception=e,
                           topmenu="home",
                           controller='home',
                           action="popular_shows")


class AddShowToBlacklistHandler(BaseHandler):
    def get(self, indexer_id):
        data = {'shows': [{'ids': {'tvdb': indexer_id}}]}
        srTraktAPI()["users/me/lists/{list}".format(list=sickrage.app.config.trakt_blacklist_name)].add(data)
        self.redirect('/home/addShows/trendingShows/')


class ExistingShowsHandler(BaseHandler):
    def get(self):
        """
        Prints out the page to add existing shows from a root dir
        """
        return self.render("/home/add_existing_shows.mako",
                           enable_anime_options=False,
                           quality=sickrage.app.config.quality_default,
                           title=_('Existing Show'),
                           header=_('Existing Show'),
                           topmenu="home",
                           controller='home',
                           action="add_existing_shows")


class AddShowByIDHandler(BaseHandler):
    async def get(self, indexer_id, showName):
        if re.search(r'tt\d+', indexer_id):
            lINDEXER_API_PARMS = IndexerApi(1).api_params.copy()
            t = IndexerApi(1).indexer(**lINDEXER_API_PARMS)
            indexer_id = t[indexer_id]['id']

        if findCertainShow(int(indexer_id)):
            return

        location = None
        if sickrage.app.config.root_dirs:
            root_dirs = sickrage.app.config.root_dirs.split('|')
            location = root_dirs[int(root_dirs[0]) + 1]

        if not location:
            sickrage.app.log.warning("There was an error creating the show, no root directory setting found")
            return _('No root directories setup, please go back and add one.')

        show_dir = os.path.join(location, sanitizeFileName(showName))

        post_data = {'show_to_add': '1|{show_dir}|{indexer_id}|{show_name}'.format(**{
            'show_dir': '',
            'indexer_id': indexer_id,
            'show_name': showName
        })}

        return await AsyncHTTPClient().fetch("/home/addShows/newShow", body=urlencode(post_data))


class AddNewShowHandler(BaseHandler):
    async def get(self, whichSeries=None, indexerLang=None, rootDir=None, defaultStatus=None,
                  quality_preset=None, anyQualities=None, bestQualities=None, flatten_folders=None, subtitles=None,
                  subtitles_sr_metadata=None, fullShowPath=None, other_shows=None, skipShow=None, providedIndexer=None,
                  anime=None, scene=None, blacklist=None, whitelist=None, defaultStatusAfter=None,
                  skip_downloaded=None, providedName=None, add_show_year=None):
        """
        Receive tvdb id, dir, and other options and create a show from them. If extra show dirs are
        provided then it forwards back to newShow, if not it goes to /home.
        """

        indexerLang = indexerLang or sickrage.app.config.indexer_default_language

        # grab our list of other dirs if given
        if not other_shows:
            other_shows = []
        elif not isinstance(other_shows, list):
            other_shows = [other_shows]

        def finishAddShow():
            # if there are no extra shows then go home
            if not other_shows:
                return self.redirect('/home/')

            # peel off the next one
            next_show_dir = other_shows[0]
            rest_of_show_dirs = other_shows[1:]

            # go to add the next show
            post_data = {'show_to_add': next_show_dir, 'other_shows': rest_of_show_dirs}
            return AsyncHTTPClient().fetch("/home/addShows/newShow", body=urlencode(post_data))

        # if we're skipping then behave accordingly
        if skipShow:
            return await finishAddShow()

        # sanity check on our inputs
        if not whichSeries or not any([rootDir, fullShowPath, providedName]):
            return self.redirect("/home/")

        # figure out what show we're adding and where
        series_pieces = whichSeries.split('|')
        if (whichSeries and rootDir or whichSeries and fullShowPath) and len(series_pieces) > 1:
            if len(series_pieces) < 6:
                sickrage.app.log.error(
                    'Unable to add show due to show selection. Not anough arguments: %s' % (repr(series_pieces)))
                sickrage.app.alerts.error(
                    _('Unknown error. Unable to add show due to problem with show selection.'))
                return self.redirect('/home/addShows/existingShows/')

            indexer = int(series_pieces[1])
            indexer_id = int(series_pieces[3])
            show_name = series_pieces[4]
        else:
            indexer = int(providedIndexer or sickrage.app.config.indexer_default)
            indexer_id = int(whichSeries)
            if fullShowPath:
                show_name = os.path.basename(os.path.normpath(fullShowPath))
            else:
                show_name = providedName

        # use the whole path if it's given, or else append the show name to the root dir to get the full show path
        if fullShowPath:
            show_dir = os.path.normpath(fullShowPath)
        else:
            show_dir = os.path.join(rootDir, sanitizeFileName(show_name))
            if add_show_year and not re.match(r'.*\(\d+\)$', show_dir):
                show_dir = "{} ({})".format(show_dir, re.search(r'\d{4}', series_pieces[5]).group(0))

        # blanket policy - if the dir exists you should have used "add existing show" numbnuts
        if os.path.isdir(show_dir) and not fullShowPath:
            sickrage.app.alerts.error(_("Unable to add show"),
                                      _("Folder ") + show_dir + _(" exists already"))
            return self.redirect('/home/addShows/existingShows/')

        # don't create show dir if config says not to
        if sickrage.app.config.add_shows_wo_dir:
            sickrage.app.log.info(
                "Skipping initial creation of " + show_dir + " due to sickrage.CONFIG.ini setting")
        else:
            dir_exists = makeDir(show_dir)
            if not dir_exists:
                sickrage.app.log.warning("Unable to create the folder " + show_dir + ", can't add the show")
                sickrage.app.alerts.error(_("Unable to add show"),
                                          _("Unable to create the folder " +
                                            show_dir + ", can't add the show"))

                # Don't redirect to default page because user wants to see the new show
                return self.redirect("/home/")
            else:
                chmod_as_parent(show_dir)

        # prepare the inputs for passing along
        scene = checkbox_to_value(scene)
        anime = checkbox_to_value(anime)
        flatten_folders = checkbox_to_value(flatten_folders)
        subtitles = checkbox_to_value(subtitles)
        subtitles_sr_metadata = checkbox_to_value(subtitles_sr_metadata)
        skip_downloaded = checkbox_to_value(skip_downloaded)

        if whitelist:
            whitelist = short_group_names(whitelist)
        if blacklist:
            blacklist = short_group_names(blacklist)

        if not anyQualities:
            anyQualities = []
        if not bestQualities:
            bestQualities = []
        if not isinstance(anyQualities, list):
            anyQualities = [anyQualities]
        if not isinstance(bestQualities, list):
            bestQualities = [bestQualities]

        newQuality = try_int(quality_preset, None)
        if not newQuality:
            newQuality = Quality.combine_qualities(map(int, anyQualities), map(int, bestQualities))

        # add the show
        sickrage.app.show_queue.addShow(indexer=indexer,
                                        indexer_id=indexer_id,
                                        showDir=show_dir,
                                        default_status=int(defaultStatus),
                                        quality=newQuality,
                                        flatten_folders=flatten_folders,
                                        lang=indexerLang,
                                        subtitles=subtitles,
                                        subtitles_sr_metadata=subtitles_sr_metadata,
                                        anime=anime,
                                        scene=scene,
                                        paused=None,
                                        blacklist=blacklist,
                                        whitelist=whitelist,
                                        default_status_after=int(defaultStatusAfter),
                                        skip_downloaded=skip_downloaded)

        sickrage.app.alerts.message(_('Adding Show'), _('Adding the specified show into ') + show_dir)

        return finishAddShow()


class AddExistingShowsHandler(BaseHandler):
    async def get(self, shows_to_add, promptForSettings, **kwargs):
        """
        Receives a dir list and add them. Adds the ones with given TVDB IDs first, then forwards
        along to the newShow page.
        """
        # grab a list of other shows to add, if provided
        if not shows_to_add:
            shows_to_add = []
        elif not isinstance(shows_to_add, list):
            shows_to_add = [shows_to_add]

        shows_to_add = [unquote_plus(x) for x in shows_to_add]

        promptForSettings = checkbox_to_value(promptForSettings)

        indexer_id_given = []
        dirs_only = []
        # separate all the ones with Indexer IDs
        for cur_dir in shows_to_add:
            split_vals = cur_dir.split('|')
            if split_vals:
                if len(split_vals) > 2:
                    indexer, show_dir, indexer_id, show_name = split_extra_show(cur_dir)
                    if all([show_dir, indexer_id, show_name]):
                        indexer_id_given.append((int(indexer), show_dir, int(indexer_id), show_name))
                else:
                    dirs_only.append(cur_dir)
            else:
                dirs_only.append(cur_dir)

        # if they want me to prompt for settings then I will just carry on to the newShow page
        if promptForSettings and shows_to_add:
            post_data = {'show_to_add': shows_to_add[0], 'other_shows': shows_to_add[1:]}
            return await AsyncHTTPClient().fetch("/home/addShows/newShow", body=urlencode(post_data))

        # if they don't want me to prompt for settings then I can just add all the nfo shows now
        num_added = 0
        for cur_show in indexer_id_given:
            indexer, show_dir, indexer_id, show_name = cur_show

            if indexer is not None and indexer_id is not None:
                # add the show
                sickrage.app.show_queue.addShow(indexer,
                                                indexer_id,
                                                show_dir,
                                                default_status=sickrage.app.config.status_default,
                                                quality=sickrage.app.config.quality_default,
                                                flatten_folders=sickrage.app.config.flatten_folders_default,
                                                subtitles=sickrage.app.config.subtitles_default,
                                                anime=sickrage.app.config.anime_default,
                                                scene=sickrage.app.config.scene_default,
                                                default_status_after=sickrage.app.config.status_default_after,
                                                skip_downloaded=sickrage.app.config.skip_downloaded_default)
                num_added += 1

        if num_added:
            sickrage.app.alerts.message(_("Shows Added"),
                                        _("Automatically added ") + str(
                                            num_added) + _(" from their existing metadata files"))

        # if we're done then go home
        if not dirs_only:
            return self.redirect('/home/')

        # for the remaining shows we need to prompt for each one, so forward this on to the newShow page
        post_data = {'show_to_add': dirs_only[0], 'other_shows': dirs_only[1:]}
        return await AsyncHTTPClient().fetch("/home/addShows/newShow", body=urlencode(post_data))
