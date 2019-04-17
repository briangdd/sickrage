import sickrage
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/manage/manageQueues(/?.*)')
class ManageQueues(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ManageQueues, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/manage/queues.mako",
            backlogSearchPaused=sickrage.app.search_queue.is_backlog_searcher_paused(),
            dailySearchPaused=sickrage.app.search_queue.is_daily_searcher_paused(),
            backlogSearchStatus=sickrage.app.search_queue.is_backlog_in_progress(),
            dailySearchStatus=sickrage.app.search_queue.is_dailysearch_in_progress(),
            findPropersStatus=sickrage.app.proper_searcher.amActive,
            searchQueueLength=sickrage.app.search_queue.queue_length(),
            postProcessorPaused=sickrage.app.postprocessor_queue.is_paused,
            postProcessorRunning=sickrage.app.postprocessor_queue.is_in_progress,
            postProcessorQueueLength=sickrage.app.postprocessor_queue.queue_length,
            title=_('Manage Queues'),
            header=_('Manage Queues'),
            topmenu='manage',
            controller='manage',
            action='queues'
        )

    def forceBacklogSearch(self):
        # force it to run the next time it looks
        if sickrage.app.scheduler.get_job(sickrage.app.backlog_searcher.name).func(True):
            sickrage.app.log.info("Backlog search forced")
            sickrage.app.alerts.message(_('Backlog search started'))

        return self.redirect("/manage/manageQueues/")

    def forceDailySearch(self):
        # force it to run the next time it looks
        if sickrage.app.scheduler.get_job(sickrage.app.daily_searcher.name).func(True):
            sickrage.app.log.info("Daily search forced")
            sickrage.app.alerts.message(_('Daily search started'))

        self.redirect("/manage/manageQueues/")

    def forceFindPropers(self):
        # force it to run the next time it looks
        if sickrage.app.scheduler.get_job(sickrage.app.proper_searcher.name).func(True):
            sickrage.app.log.info("Find propers search forced")
            sickrage.app.alerts.message(_('Find propers search started'))

        return self.redirect("/manage/manageQueues/")

    def pauseDailySearcher(self, paused=None):
        if paused == "1":
            sickrage.app.search_queue.pause_daily_searcher()
        else:
            sickrage.app.search_queue.unpause_daily_searcher()

        return self.redirect("/manage/manageQueues/")

    def pauseBacklogSearcher(self, paused=None):
        if paused == "1":
            sickrage.app.search_queue.pause_backlog_searcher()
        else:
            sickrage.app.search_queue.unpause_backlog_searcher()

        return self.redirect("/manage/manageQueues/")

    def pausePostProcessor(self, paused=None):
        if paused == "1":
            sickrage.app.postprocessor_queue.pause()
        else:
            sickrage.app.postprocessor_queue.unpause()

        return self.redirect("/manage/manageQueues/")