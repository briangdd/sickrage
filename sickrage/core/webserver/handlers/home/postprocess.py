import sickrage
from sickrage.core.helpers import argToBool
from sickrage.core.webserver.handlers.base import BaseHandler


@Route('/home/postprocess(/?.*)')
class HomePostProcess(BaseHandler):
    def __init__(self, *args, **kwargs):
        super(HomePostProcess, self).__init__(*args, **kwargs)

    def index(self):
        return self.render(
            "/home/postprocess.mako",
            title=_('Post Processing'),
            header=_('Post Processing'),
            topmenu='home',
            controller='home',
            action='postprocess'
        )

    def processEpisode(self, *args, **kwargs):
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
