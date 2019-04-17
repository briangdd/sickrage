import os

import sickrage
from sickrage.core.helpers import backupSR, checkbox_to_value, restoreConfigZip
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/config/backuprestore(/?.*)')
class ConfigBackupRestore(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigBackupRestore, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/config/backup_restore.mako",
            submenu=self.ConfigMenu(),
            title=_('Config - Backup/Restore'),
            header=_('Backup/Restore'),
            topmenu='config',
            controller='config',
            action='backup_restore'
        )

    @staticmethod
    def backup(backupDir=None):
        finalResult = ''

        if backupDir:
            if backupSR(backupDir):
                finalResult += _("Backup SUCCESSFUL")
            else:
                finalResult += _("Backup FAILED!")
        else:
            finalResult += _("You need to choose a folder to save your backup to first!")

        finalResult += "<br>\n"

        return finalResult

    @staticmethod
    def restore(backupFile=None, restore_database=None, restore_config=None, restore_cache=None):
        finalResult = ''

        if backupFile:
            source = backupFile
            target_dir = os.path.join(sickrage.app.data_dir, 'restore')

            restore_database = checkbox_to_value(restore_database)
            restore_config = checkbox_to_value(restore_config)
            restore_cache = checkbox_to_value(restore_cache)

            if restoreConfigZip(source, target_dir, restore_database, restore_config, restore_cache):
                finalResult += _("Successfully extracted restore files to " + target_dir)
                finalResult += _("<br>Restart sickrage to complete the restore.")
            else:
                finalResult += _("Restore FAILED")
        else:
            finalResult += _("You need to select a backup file to restore!")

        finalResult += "<br>\n"

        return finalResult

    def saveBackupRestore(self, **kwargs):
        return self.redirect("/config/backuprestore/")