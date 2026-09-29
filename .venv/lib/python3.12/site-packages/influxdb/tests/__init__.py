# -*- coding: utf-8 -*-
"""Configure the tests package for InfluxDBClient."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os

import unittest

using_pypy = hasattr(sys, "pypy_version_info")
skip_if_pypy = unittest.skipIf(using_pypy, "Skipping this test on pypy.")

_skip_server_tests = os.environ.get(
    'INFLUXDB_PYTHON_SKIP_SERVER_TESTS',
    None) == 'True'
skip_server_tests = unittest.skipIf(_skip_server_tests,
                                    "Skipping server tests...")
