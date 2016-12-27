from __future__ import division, absolute_import

import datetime
import time

from builtins import super
from ...common.interfaces import AbstractInfoWidget

from ..Console import screen as ConsoleScreen


class MavenInfoWidget(AbstractInfoWidget):
    ''' Right panel widget '''

    def __init__(self, owner):
        # FIXME python version 2.7 does not support this syntax. super() should
        # have arguments in Python 2
        super().__init__()
        self.krutilka = ConsoleScreen.krutilka()
        self.owner = owner

    def get_index(self):
        return 0

    def on_aggregated_data(self, data, stats):
        pass

    def render(self, screen):
        text = " Maven Test %s" % next(self.krutilka)
        space = screen.right_panel_width - len(text) - 1
        left_spaces = space // 2
        right_spaces = space // 2

        dur_seconds = int(time.time()) - int(self.owner.process_start_time)
        duration = str(datetime.timedelta(seconds=dur_seconds))

        template = screen.markup.BG_BROWN + '~' * left_spaces + \
            text + ' ' + '~' * right_spaces + screen.markup.RESET + "\n"
        template += "Command Line: %s\n"
        template += "    Duration: %s"
        data = (self.owner.maven_cmd, duration)

        return template % data
