# -*- coding: utf-8 -*-

import base64
import logging
from subprocess import Popen, PIPE

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class Custom(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)
            self.diff_values = {}

    def columns(self,):
        cols = []
        for el in self.tail:
            cols.append("Custom:" + el)
        for el in self.call:
            cols.append("Custom:" + el)
        return cols

    def check(self,):
        res = []
        for el in self.tail:
            cmd = base64.b64decode(el.split(':')[1])
            output = Popen(['tail', '-n', '1', cmd], stdout=PIPE).communicate()[0]
            res.append(self.diff_value(output.strip()))
        for el in self.call:
            cmd = base64.b64decode(el.split(':')[1])
            output = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE).stdout.read()
            res.append(self.diff_value(el, output.strip()))
        return res

    def diff_value(self, config_line, value):
        if not is_number(value):
            #logging.warning("Non-numeric result string, defaulting value to 0: %s", value)
            value = 0
        params = config_line.split(':')
        if len(params) > 2 and int(params[2]):
            if config_line in self.diff_values:
                diffvalue = float(value) - self.diff_values[config_line]
            else:
                diffvalue = 0
            self.diff_values[config_line] = float(value)
            value = diffvalue
        return str(value)
