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
import re

import sickrage
from sickrage.core.classes import ErrorViewer, WarningViewer
from sickrage.core.helpers import readFileBuffered
from sickrage.core.webserver.handlers.base import BaseHandler


class LogsHandler(BaseHandler):
    def initialize(self):
        self.logs_menu = [
            {'title': _('Clear All'), 'path': '/logs/clearAll/',
             'requires': self.haveErrors() or self.haveWarnings(),
             'icon': 'fas fa-trash'},
        ]

    def get(self, level=None):
        level = int(level or sickrage.app.log.ERROR)
        return self.render(
            "/logs/errors.mako",
            header="Logs &amp; Errors",
            title="Logs &amp; Errors",
            topmenu="system",
            submenu=self.logs_menu,
            logLevel=level,
            controller='logs',
            action='errors'
        )

    def haveErrors(self):
        if len(ErrorViewer.errors) > 0:
            return True

    def haveWarnings(self):
        if len(WarningViewer.errors) > 0:
            return True


class LogsClearAllHanlder(BaseHandler):
    def get(self):
        WarningViewer.clear()
        ErrorViewer.clear()
        self.redirect("/logs/view/")


class LogsViewHandler(BaseHandler):
    def get(self, minLevel=None, logFilter='', logSearch='', maxLines=500):
        logNameFilters = {
            '': 'No Filter',
            'DAILYSEARCHER': _('Daily Searcher'),
            'BACKLOG': _('Backlog'),
            'SHOWUPDATER': _('Show Updater'),
            'VERSIONUPDATER': _('Check Version'),
            'SHOWQUEUE': _('Show Queue'),
            'SEARCHQUEUE': _('Search Queue'),
            'FINDPROPERS': _('Find Propers'),
            'POSTPROCESSOR': _('Postprocessor'),
            'SUBTITLESEARCHER': _('Find Subtitles'),
            'TRAKTSEARCHER': _('Trakt Checker'),
            'EVENT': _('Event'),
            'ERROR': _('Error'),
            'TORNADO': _('Tornado'),
            'Thread': _('Thread'),
            'MAIN': _('Main'),
        }

        minLevel = minLevel or sickrage.app.log.INFO

        logFiles = [sickrage.app.log.logFile] + \
                   ["{}.{}".format(sickrage.app.log.logFile, x) for x in
                    range(int(sickrage.app.log.logNr))]

        levelsFiltered = '|'.join(
            [x for x in sickrage.app.log.logLevels.keys() if
             sickrage.app.log.logLevels[x] >= int(minLevel)])

        logRegex = re.compile(
            r"(?P<entry>^\d+\-\d+\-\d+\s+\d+\:\d+\:\d+\s+(?:{})[\s\S]+?(?:{})[\s\S]+?$)".format(levelsFiltered,
                                                                                                logFilter),
            re.S + re.M)

        data = []
        try:
            for logFile in [x for x in logFiles if os.path.isfile(x)]:
                data += list(reversed(re.findall("((?:^.+?{}.+?$))".format(logSearch),
                                                 "\n".join(next(readFileBuffered(logFile, reverse=True)).splitlines()),
                                                 re.M + re.I)))
                maxLines -= len(data)
                if len(data) == maxLines:
                    raise StopIteration

        except StopIteration:
            pass

        return self.render(
            "/logs/view.mako",
            header="Log File",
            title="Logs",
            topmenu="system",
            logLines="\n".join(logRegex.findall("\n".join(data))),
            minLevel=int(minLevel),
            logNameFilters=logNameFilters,
            logFilter=logFilter,
            logSearch=logSearch,
            controller='logs',
            action='view'
        )