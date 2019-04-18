import datetime
from abc import ABC

import dateutil
from tornado.web import authenticated

import sickrage
from sickrage.core.databases.main import MainDB
from sickrage.core.helpers import try_int
from sickrage.core.webserver.handlers.base import BaseHandler


class CalendarHandler(BaseHandler, ABC):
    def get(self, *args, **kwargs):
        if sickrage.app.config.calendar_unprotected:
            self.write(self.calendar())
        else:
            self.calendar_auth()

    @authenticated
    def calendar_auth(self):
        self.write(self.calendar())

    # Raw iCalendar implementation by Pedro Jose Pereira Vieito (@pvieito).
    #
    # iCalendar (iCal) - Standard RFC 5545 <http://tools.ietf.org/html/rfc5546>
    # Works with iCloud, Google Calendar and Outlook.
    def calendar(self):
        """ Provides a subscribeable URL for iCal subscriptions
        """

        utc = dateutil.tz.gettz('GMT')

        sickrage.app.log.info("Receiving iCal request from %s" % self.request.remote_ip)

        # Create a iCal string
        ical = 'BEGIN:VCALENDAR\r\n'
        ical += 'VERSION:2.0\r\n'
        ical += 'X-WR-CALNAME:SiCKRAGE\r\n'
        ical += 'X-WR-CALDESC:SiCKRAGE\r\n'
        ical += 'PRODID://SiCKRAGE Upcoming Episodes//\r\n'

        # Limit dates
        past_date = (datetime.date.today() + datetime.timedelta(weeks=-52)).toordinal()
        future_date = (datetime.date.today() + datetime.timedelta(weeks=52)).toordinal()

        # Get all the shows that are not paused and are currently on air (from kjoconnor Fork)
        for show in [x for x in sickrage.app.showlist if
                     x.status.lower() in ['continuing', 'returning series'] and x.paused != 1]:
            for dbData in MainDB.TVEpisode.query.filter_by(showid=int(show.indexerid)).filter(
                    past_date <= MainDB.TVEpisode.airdate < future_date):
                air_date_time = sickrage.app.tz_updater.parse_date_time(dbData.airdate, show.airs,
                                                                        show.network).astimezone(utc)
                air_date_time_end = air_date_time + datetime.timedelta(minutes=try_int(show.runtime, 60))

                # Create event for episode
                ical += 'BEGIN:VEVENT\r\n'
                ical += 'DTSTART:' + air_date_time.strftime("%Y%m%d") + 'T' + air_date_time.strftime("%H%M%S") + 'Z\r\n'
                ical += 'DTEND:' + air_date_time_end.strftime("%Y%m%d") + 'T' + air_date_time_end.strftime(
                    "%H%M%S") + 'Z\r\n'
                if sickrage.app.config.calendar_icons:
                    ical += 'X-GOOGLE-CALENDAR-CONTENT-ICON:https://www.sickrage.ca/favicon.ico\r\n'
                    ical += 'X-GOOGLE-CALENDAR-CONTENT-DISPLAY:CHIP\r\n'
                ical += 'SUMMARY: {0} - {1}x{2} - {3}\r\n'.format(show.name, dbData.season, dbData.episode, dbData.name)
                ical += 'UID:SiCKRAGE-' + str(datetime.date.today().isoformat()) + '-' + \
                        show.name.replace(" ", "-") + '-E' + str(dbData.episode) + \
                        'S' + str(dbData.season) + '\r\n'
                if dbData.description:
                    ical += 'DESCRIPTION: {0} on {1} \\n\\n {2}\r\n'.format(
                        (show.airs or '(Unknown airs)'),
                        (show.network or 'Unknown network'),
                        dbData.description.splitlines()[0])
                else:
                    ical += 'DESCRIPTION:' + (show.airs or '(Unknown airs)') + ' on ' + (
                            show.network or 'Unknown network') + '\r\n'

                ical += 'END:VEVENT\r\n'

        # Ending the iCal
        ical += 'END:VCALENDAR'

        return ical
