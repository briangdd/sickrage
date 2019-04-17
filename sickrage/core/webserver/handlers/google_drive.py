from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/googleDrive(/?.*)')
class GoogleDriveHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(GoogleDriveHandler, self).__init__(*args, **kwargs)

    def getProgress(self):
        return google_drive.GoogleDrive.get_progress()

    def syncRemote(self):
        self._genericMessage(_("Google Drive Sync"), _("Syncing app data to Google Drive"))
        google_drive.GoogleDrive().sync_remote()

    def syncLocal(self):
        self._genericMessage(_("Google Drive Sync"), _("Syncing app data from Google Drive"))
        google_drive.GoogleDrive().sync_local()