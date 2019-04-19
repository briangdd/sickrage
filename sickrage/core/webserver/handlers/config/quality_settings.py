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

import sickrage
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/config/qualitySettings(/?.*)')
class ConfigQualitySettings(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigQualitySettings, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/config/quality_settings.mako",
            submenu=self.ConfigMenu(),
            title=_('Config - Quality Settings'),
            header=_('Quality Settings'),
            topmenu='config',
            controller='config',
            action='quality_settings'
        )

    def saveQualities(self, **kwargs):
        sickrage.app.config.quality_sizes.update(dict((int(k), int(v)) for k, v in kwargs.items()))

        sickrage.app.config.save()

        sickrage.app.alerts.message(_('[QUALITY SETTINGS] Configuration Encrypted and Saved to SiCKRAGE Cloud'))

        return self.redirect("/config/qualitySettings/")