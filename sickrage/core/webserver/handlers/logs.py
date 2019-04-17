import os
import re

import sickrage
from sickrage.core.classes import ErrorViewer, WarningViewer
from sickrage.core.helpers import readFileBuffered
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/logs(/?.*)')
class LogsHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(LogsHandler, self).__init__(*args, **kwargs)

    def LogsMenu(self):
        menu = [
            {'title': _('Clear All'), 'path': '/logs/clearAll/',
             'requires': self.haveErrors() or self.haveWarnings(),
             'icon': 'fas fa-trash'},
        ]

        return menu

    def index(self, level=None):
        level = int(level or sickrage.app.log.ERROR)
        return self.render(
            "/logs/errors.mako",
            header="Logs &amp; Errors",
            title="Logs &amp; Errors",
            topmenu="system",
            submenu=self.LogsMenu(),
            logLevel=level,
            controller='logs',
            action='errors'
        )

    @staticmethod
    def haveErrors():
        if len(ErrorViewer.errors) > 0:
            return True

    @staticmethod
    def haveWarnings():
        if len(WarningViewer.errors) > 0:
            return True

    def clearAll(self):
        WarningViewer.clear()
        ErrorViewer.clear()

        return self.redirect("/logs/viewlog/")

    def viewlog(self, minLevel=None, logFilter='', logSearch='', maxLines=500):
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

    def submit_errors(self):
        # submitter_result, issue_id = logging.submit_errors()
        # LOGGER.warning(submitter_result, [issue_id is None])
        # submitter_notification = notifications.error if issue_id is None else notifications.message
        # submitter_notification(submitter_result)

        return self.redirect("/logs/")