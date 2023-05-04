"""Manages your test data

* create the DataSession
* specify metrics you want to save
* specify the backends
* this module will collect your data and save them to specified backends
"""

# TODO: import only specific things that we really need to export
from .manager import *  # noqa
from .common.interfaces import MetricData   # noqa
