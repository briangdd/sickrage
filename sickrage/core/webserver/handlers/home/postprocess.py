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
from sickrage.core.helpers import argToBool
from sickrage.core.webserver.handlers.base import BaseHandler


class HomePostProcessHandler(BaseHandler):
    def get(self):
        return self.render(
            "/home/postprocess.mako",
            title=_('Post Processing'),
            header=_('Post Processing'),
            topmenu='home',
            controller='home',
            action='postprocess'
        )

class HomeProcessEpisodeHandler(BaseHandler):
    def get(self, *args, **kwargs):
        pp_options = dict(
            ("proc_dir" if k.lower() == "dir" else k,
             argToBool(v)
             if k.lower() not in ['proc_dir', 'dir', 'nzbname', 'process_method', 'proc_type'] else v
             ) for k, v in kwargs.items())

        proc_dir = pp_options.pop("proc_dir", None)
        quiet = pp_options.pop("quiet", None)

        if not proc_dir:
            return self.redirect("/home/postprocess/")

        result = sickrage.app.postprocessor_queue.put(proc_dir, **pp_options)

        if quiet:
            return result

        return self._genericMessage(_("Postprocessing results"), result.replace("\n", "<br>\n"))
