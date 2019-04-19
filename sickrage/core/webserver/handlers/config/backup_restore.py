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