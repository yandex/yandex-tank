# -*- coding: utf-8 -*-

import commands

class NetRetrans(object):
    ''' read netstat output and
    calculate tcp segment retransmition derivative '''
    def __init__(self,):
        self.retr_second = None
        self.retr_first = None

    def columns(self,):
        return ['Net_retransmit', ]

    def check(self,):
        self.fetch = lambda: int(commands.getoutput('netstat -s | grep "segments retransmited" | awk \'{print $1}\''))
        if self.retr_second is not None:
            self.retr_first = self.fetch()
            self.delta = []
            self.delta.append(str(self.retr_first - self.retr_second))
            self.retr_second = self.retr_first
            return self.delta
        else:
            # first check
            self.retr_second = self.fetch()
            return ['0', ]

