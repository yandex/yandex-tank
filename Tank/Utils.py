'''
Commonly used utilities contained here
'''

import errno
import itertools
import logging
import os
import re
import select
import subprocess
import time

def log_stdout_stderr(log, stdout, stderr, comment=""):
    '''
    This function polls stdout and stderr streams and writes their contents to log
    '''
    readable = select.select([stdout], [], [] , 0)[0]
    if stderr:
        exceptional = select.select([stderr], [], [] , 0)[0]
    else:
        exceptional = []
    
    log.debug("Selected: %s, %s", readable, exceptional)

    for handle in readable:
        line = handle.read()
        readable.remove(handle)
        if line:
            log.debug("%s stdout: %s", comment, line.strip())

    for handle in exceptional:
        line = handle.read()
        exceptional.remove(handle)
        if line:
            log.warn("%s stderr: %s", comment, line.strip())


def expand_to_milliseconds(str_time):
    '''
    converts 1d2s into milliseconds
    '''
    return expand_time(str_time, 'ms', 1000)

def expand_to_seconds(str_time):
    '''
    converts 1d2s into seconds
    '''
    return expand_time(str_time, 's', 1)

def expand_time(str_time, default_unit='s', multiplier=1):
    '''
    helper for above functions
    '''
    parser = re.compile('(\d+)([a-zA-Z]*)')
    parts = parser.findall(str_time)
    result = 0.0
    for value, unit in parts:
        value = int(value)
        unit = unit.lower()
        if unit == '': 
            unit = default_unit 
        
        if   unit == 'ms': 
            result += value * 0.001 
            continue
        elif unit == 's':  
            result += value
            continue
        elif unit == 'm':  
            result += value * 60
            continue
        elif unit == 'h':  
            result += value * 60 * 60
            continue
        elif unit == 'd':  
            result += value * 60 * 60 * 24
            continue
        elif unit == 'w':  
            result += value * 60 * 60 * 24 * 7
            continue
        else: 
            raise ValueError("String contains unsupported unit %s: %s", unit, str_time)
    return int(result * multiplier)

def pid_exists(pid):
    """Check whether pid exists in the current process table."""
    if pid < 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError, exc:
        return exc.errno == errno.EPERM
    else:
        return True

def execute(cmd, shell=False, poll_period=1, catch_out=False):
    '''
    Wrapper for Popen
    '''
    log = logging.getLogger(__name__)
    log.debug("Starting: %s", cmd)

    if catch_out:
        process = subprocess.Popen(cmd, shell=shell, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    else:
        process = subprocess.Popen(cmd, shell=shell)
        
    while process.poll() == None:
        log.debug("Waiting for process to finish: %s", process)
        time.sleep(poll_period)
    
    if catch_out:
        for line in process.stderr.readlines():
            log.warn(line.strip())
        for line in process.stdout.readlines():
            log.debug(line.strip())
    
    retcode = process.poll()
    log.debug("Process exit code: %s", retcode)
    return retcode

def splitstring(string):
    """
    >>> string = 'apple orange "banana tree" green'
    >>> splitstring(string)
    ['apple', 'orange', 'green', '"banana tree"']
    """
    patt = re.compile(r'"[\w ]+"')
    if patt.search(string):
        quoted_item = patt.search(string).group()
        newstring = patt.sub('', string)
        return newstring.split() + [quoted_item]
    else:
        return string.split()


def pairs(lst):
    '''
    Iterate over pairs in the list
    '''
    return itertools.izip(lst[::2], lst[1::2])

