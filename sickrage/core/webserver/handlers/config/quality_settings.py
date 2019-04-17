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