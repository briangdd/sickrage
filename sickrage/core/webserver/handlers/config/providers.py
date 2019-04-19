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

from tornado.escape import json_encode

import sickrage
from sickrage.core.helpers import try_int, checkbox_to_value
from sickrage.core.webserver.handlers.base import BaseHandler
from sickrage.providers import NewznabProvider, TorrentRssProvider


@Route('/config/providers(/?.*)')
class ConfigProviders(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(ConfigProviders, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/config/providers.mako",
            submenu=self.ConfigMenu(),
            title=_('Config - Search Providers'),
            header=_('Search Providers'),
            topmenu='config',
            controller='config',
            action='providers'
        )

    @staticmethod
    def canAddNewznabProvider(name):
        if not name: return json_encode({'error': 'No Provider Name specified'})

        providerObj = NewznabProvider(name, '')
        if providerObj.id not in sickrage.app.search_providers.newznab():
            return json_encode({'success': providerObj.id})
        return json_encode({'error': 'Provider Name already exists as ' + name})

    @staticmethod
    def canAddTorrentRssProvider(name, url, cookies, titleTAG):
        if not name: return json_encode({'error': 'No Provider Name specified'})

        providerObj = TorrentRssProvider(name, url, cookies, titleTAG)
        if providerObj.id not in sickrage.app.search_providers.torrentrss():
            validate = providerObj.validateRSS()
            if validate['result']:
                return json_encode({'success': providerObj.id})
            return json_encode({'error': validate['message']})
        return json_encode({'error': 'Provider name already exists as {}'.format(name)})

    @staticmethod
    def getNewznabCategories(name, url, key):
        """
        Retrieves a list of possible categories with category id's
        Using the default url/api?cat
        http://yournewznaburl.com/api?t=caps&apikey=yourapikey
        """

        error = ""
        success = False
        tv_categories = []

        if not name:
            error += _("\nNo Provider Name specified")
        if not url:
            error += _("\nNo Provider Url specified")
        if not key:
            error += _("\nNo Provider Api key specified")

        if not error:
            tempProvider = NewznabProvider(name, url, key)
            success, tv_categories, error = tempProvider.get_newznab_categories()
        return json_encode({'success': success, 'tv_categories': tv_categories, 'error': error})

    def saveProviders(self, **kwargs):
        results = []

        # custom providers
        custom_providers = ''
        for curProviderStr in kwargs.get('provider_strings', '').split('!!!'):
            if not len(curProviderStr):
                continue

            custom_providers += '{}!!!'.format(curProviderStr)
            cur_type, curProviderData = curProviderStr.split('|', 1)

            if cur_type == "newznab":
                cur_name, cur_url, cur_key, cur_cat = curProviderData.split('|')

                providerObj = NewznabProvider(cur_name, cur_url, cur_key, cur_cat)
                sickrage.app.search_providers.newznab().update(**{providerObj.id: providerObj})

                kwargs[providerObj.id + '_name'] = cur_name
                kwargs[providerObj.id + '_key'] = cur_key
                kwargs[providerObj.id + '_catIDs'] = cur_cat

            elif cur_type == "torrentrss":
                cur_name, cur_url, cur_cookies, cur_title_tag = curProviderData.split('|')

                providerObj = TorrentRssProvider(cur_name, cur_url, cur_cookies, cur_title_tag)
                sickrage.app.search_providers.torrentrss().update(**{providerObj.id: providerObj})

                kwargs[providerObj.id + '_name'] = cur_name
                kwargs[providerObj.id + '_cookies'] = cur_cookies
                kwargs[providerObj.id + '_curTitleTAG'] = cur_title_tag

        sickrage.app.config.custom_providers = custom_providers

        # remove providers
        for p in list(set(sickrage.app.search_providers.provider_order).difference(
                [x.split(':')[0] for x in kwargs.get('provider_order', '').split('!!!')])):
            providerObj = sickrage.app.search_providers.all()[p]
            del sickrage.app.search_providers[providerObj.type][p]

        # enable/disable/sort providers
        sickrage.app.search_providers.provider_order = []
        for curProviderStr in kwargs.get('provider_order', '').split('!!!'):
            curProvider, curEnabled = curProviderStr.split(':')
            sickrage.app.search_providers.provider_order += [curProvider]
            if curProvider in sickrage.app.search_providers.all():
                curProvObj = sickrage.app.search_providers.all()[curProvider]
                curProvObj.enabled = bool(try_int(curEnabled))

        # dynamically load provider settings
        for providerID, providerObj in sickrage.app.search_providers.all().items():
            try:
                providerSettings = {
                    'minseed': try_int(kwargs.get(providerID + '_minseed', 0)),
                    'minleech': try_int(kwargs.get(providerID + '_minleech', 0)),
                    'ratio': str(kwargs.get(providerID + '_ratio', '')).strip(),
                    'digest': str(kwargs.get(providerID + '_digest', '')).strip(),
                    'hash': str(kwargs.get(providerID + '_hash', '')).strip(),
                    'key': str(kwargs.get(providerID + '_key', '')).strip(),
                    'api_key': str(kwargs.get(providerID + '_api_key', '')).strip(),
                    'username': str(kwargs.get(providerID + '_username', '')).strip(),
                    'password': str(kwargs.get(providerID + '_password', '')).strip(),
                    'passkey': str(kwargs.get(providerID + '_passkey', '')).strip(),
                    'pin': str(kwargs.get(providerID + '_pin', '')).strip(),
                    'confirmed': checkbox_to_value(kwargs.get(providerID + '_confirmed', 0)),
                    'ranked': checkbox_to_value(kwargs.get(providerID + '_ranked', 0)),
                    'engrelease': checkbox_to_value(kwargs.get(providerID + '_engrelease', 0)),
                    'onlyspasearch': checkbox_to_value(kwargs.get(providerID + '_onlyspasearch', 0)),
                    'sorting': str(kwargs.get(providerID + '_sorting', 'seeders')).strip(),
                    'freeleech': checkbox_to_value(kwargs.get(providerID + '_freeleech', 0)),
                    'reject_m2ts': checkbox_to_value(kwargs.get(providerID + '_reject_m2ts', 0)),
                    'search_mode': str(kwargs.get(providerID + '_search_mode', 'eponly')).strip(),
                    'search_fallback': checkbox_to_value(kwargs.get(providerID + '_search_fallback', 0)),
                    'enable_daily': checkbox_to_value(kwargs.get(providerID + '_enable_daily', 0)),
                    'enable_backlog': checkbox_to_value(kwargs.get(providerID + '_enable_backlog', 0)),
                    'cat': try_int(kwargs.get(providerID + '_cat', 0)),
                    'subtitle': checkbox_to_value(kwargs.get(providerID + '_subtitle', 0)),
                    'cookies': str(kwargs.get(providerID + '_cookies', '')).strip(),
                    'custom_url': str(kwargs.get(providerID + '_custom_url', '')).strip()
                }

                # update provider object
                [setattr(providerObj, k, v) for k, v in providerSettings.items() if hasattr(providerObj, k)]
            except Exception as e:
                continue

        # save provider settings
        sickrage.app.config.save()

        if len(results) > 0:
            [sickrage.app.log.error(x) for x in results]
            sickrage.app.alerts.error(_('Error(s) Saving Configuration'), '<br>\n'.join(results))
        else:
            sickrage.app.alerts.message(_('[PROVIDERS] Configuration Encrypted and Saved to SiCKRAGE Cloud'))

        return self.redirect("/config/providers/")