import sickrage
from sickrage.core.tv.show.history import History
from sickrage.core.webserver.handlers.base import BaseHandler

@Route('/history(/?.*)')
class HistoryHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(HistoryHandler, self).__init__(*args, **kwargs)
        self.historyTool = History()

    def index(self, limit=None):

        if limit is None:
            if sickrage.app.config.history_limit:
                limit = int(sickrage.app.config.history_limit)
            else:
                limit = 100
        else:
            limit = int(limit)

        sickrage.app.config.history_limit = limit

        sickrage.app.config.save()

        compact = []
        data = self.historyTool.get(limit)

        for row in data:
            action = {
                'action': row['action'],
                'provider': row['provider'],
                'resource': row['resource'],
                'time': row['date']
            }

            if not any((history['show_id'] == row['show_id'] and
                        history['season'] == row['season'] and
                        history['episode'] == row['episode'] and
                        history['quality'] == row['quality']) for history in compact):

                history = {
                    'actions': [action],
                    'episode': row['episode'],
                    'quality': row['quality'],
                    'resource': row['resource'],
                    'season': row['season'],
                    'show_id': row['show_id'],
                    'show_name': row['show_name']
                }

                compact.append(history)
            else:
                index = [i for i, item in enumerate(compact)
                         if item['show_id'] == row['show_id'] and
                         item['season'] == row['season'] and
                         item['episode'] == row['episode'] and
                         item['quality'] == row['quality']][0]

                history = compact[index]
                history['actions'].append(action)

                history['actions'].sort(key=lambda d: d['time'], reverse=True)

        submenu = [
            {'title': _('Clear History'), 'path': '/history/clearHistory', 'icon': 'fas fa-trash',
             'class': 'clearhistory', 'confirm': True},
            {'title': _('Trim History'), 'path': '/history/trimHistory', 'icon': 'fas fa-cut',
             'class': 'trimhistory', 'confirm': True},
        ]

        return self.render(
            "/history.mako",
            historyResults=data,
            compactResults=compact,
            limit=limit,
            submenu=submenu,
            title=_('History'),
            header=_('History'),
            topmenu="history",
            controller='root',
            action='history'
        )

    def clearHistory(self):
        self.historyTool.clear()

        sickrage.app.alerts.message(_('History cleared'))

        return self.redirect("/history/")

    def trimHistory(self):
        self.historyTool.trim()

        sickrage.app.alerts.message(_('Removed history entries older than 30 days'))

        return self.redirect("/history/")