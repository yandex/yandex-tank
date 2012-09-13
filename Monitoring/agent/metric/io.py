# -*- coding: utf-8 -*-

import commands


class Io(object):
    ''' Get no virtual block device names and count theys r/rw sectors '''
    def __init__(self,):
        self.check_prev = None
        self.check_last = None

    def columns(self,):
        columns = []
        self.block_devs = commands.getoutput('ls -l /sys/block/ | grep -v "virtual" | awk \'{print $8}\' | grep -v "^$"').split('\n')
        for dev_name in self.block_devs:
            columns.extend([dev_name + '-rsec', dev_name + '-wsec'])
        return columns

    def fetch(self, ):
        tmp_data = []
        result = {}
        for dev_name in self.block_devs:
            tmp_data = map(int, commands.getoutput('cat /proc/diskstats | grep " ' + dev_name + ' "').split()[5:])
            result[dev_name] = tmp_data[0], tmp_data[4]
        return result

    def check(self, ):
        if self.check_prev is not None:
            self.check_last = self.fetch()
            delta = []
            for dev_name in self.block_devs:
                delta.extend([str(self.check_last[dev_name][0] - self.check_prev[dev_name][0]),
                                str(self.check_last[dev_name][1] - self.check_prev[dev_name][1])])
            self.check_prev = self.check_last
            return delta
        else:
            # first check
            self.check_prev = self.fetch()
            return ['0', '0', '0', '0', ]
