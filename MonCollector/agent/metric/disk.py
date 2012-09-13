# -*- coding: utf-8 -*-

from subprocess import Popen, PIPE
import logging

class Disk(object):
    def __init__(self):
        self.read = 0
        self.write = 0

    def columns(self,):
        return ['Disk_read', 'Disk_write']

    def check(self,):
        # cluster size
        size = 512

        # Current data
        read, write = 0, 0
    
        try:
            stat = Popen(["cat /proc/diskstats | awk '{print $3, $7, $11}'"],
                            stdout=PIPE, stderr=PIPE, shell=True)
        except Exception, e:
            logging.error("%s: %s" % (e.__class__, str(e)))
            result = ['', '']
        else: 
            err = stat.stderr.read()
            if err:
                logging.error(err.rstrip())
                result = ['', '']
            else:
                for el in stat.stdout:
                    data = el.split()
                    read += int(data[1])
                    try:
                        write += int(data[2])
                    except:
                        pass
                if self.read:
                    result = [str(size * (read - self.read)), str(size * (write - self.write))]
                else:
                    result = ['', '']
        self.read, self.write = read, write
        return result
