# -*- coding: utf-8 -*-

class CpuLa(object):

    def columns(self,):
        return ['System_la1', 'System_la5', 'System_la15']

    def check(self,):
        loadavg_str = open('/proc/loadavg', 'r').readline().strip()
        return map(str, loadavg_str.split()[:3])
