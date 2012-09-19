# -*- coding: utf-8 -*-

import logging

from subprocess import Popen, PIPE
EMPTY = ''
class Mem(object):
    """
    Memory statistics
    """

    def __init__(self):
        self.name = 'advanced memory usage'
        self.nick = ('used', 'buff', 'cach', 'free', 'dirty')
        self.vars = ('MemUsed', 'Buffers', 'Cached', 'MemFree', 'Dirty', 'MemTotal')
#        self.open('/proc/meminfo')

    def columns(self):
        columns = ['Memory_total', 'Memory_used', 'Memory_free', 'Memory_shared', 'Memory_buff', 'Memory_cached']
        logging.info("Start. Columns: %s" % columns)
        return columns

    def check(self):
        result = []
        try:
            output = Popen('cat /proc/meminfo', shell=True, stdout=PIPE, stderr=PIPE)
        except Exception, e:
            logging.error("%s: %s" % (e.__class__, str(e)))
            result.append([EMPTY] * 9)
        else:
            err = output.stderr.read()
            if err:
                result.extend([EMPTY] * 9)
                logging.error(err.rstrip())
            else:
                info = output.stdout.read()
                
                data = {}
                for name in self.vars:
                    data[name] = 0
                
                for l in info.splitlines():
                    if len(l) < 2: continue
                    [name, raw_value] = l.split(':')
#                    print "name: %s " % name
                    if name in self.vars:
#                       print name, raw_value
                        data.update({name: long(raw_value.split()[0]) / 1024.0})
#                print data
                data['MemUsed'] = data['MemTotal'] - data['MemFree'] - data['Buffers'] - data['Cached']
            result = [data['MemTotal'], data['MemUsed'], data['MemFree'], 0, data['Buffers'], data['Cached']]
            return map(str, result)
