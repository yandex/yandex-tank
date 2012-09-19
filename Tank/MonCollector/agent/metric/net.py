# -*- coding: utf-8 -*-

import re
from subprocess import Popen, PIPE
import logging

class Net(object):
    def __init__(self):
        self.recv = 0
        self.send = 0
        self.rgx = re.compile('\S+\s(\d+)\s(\d+)')

    def columns(self,):
        return ['Net_recv', 'Net_send']

    def check(self,):
        # Current data
        recv, send = 0, 0

        cmd = "cat /proc/net/dev | tail -n +3 | cut -d':' -f 1,2 --output-delimiter=' ' | awk '{print $1, $2, $10}'"
        logging.debug("Starting: %s", cmd)
        try:
            stat = Popen([cmd], stdout=PIPE, stderr=PIPE, shell=True)
        except Exception, e:
            logging.error("Error getting net metrics: %s", e)
            result = ['', '']

        else:
            err = stat.stderr.read()
            if err:
                logging.error("Error output: %s", err)
                result = ['', '']
            else:
                for el in stat.stdout:
                    m = self.rgx.match(el)
                    if m:
                        recv += int(m.group(1))
                        send += int(m.group(2))
                        logging.debug("Recv/send: %s/%s", recv, send)
                    else:
                        logging.debug("Not matched: %s", el)
                if self.recv:
                    result = [str(recv - self.recv), str(send - self.send)]
                else:
                    result = ['', '']

        self.recv, self.send = recv, send
        logging.debug("Result: %s", result)
        return result

