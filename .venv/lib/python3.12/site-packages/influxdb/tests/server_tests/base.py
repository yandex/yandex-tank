# -*- coding: utf-8 -*-
"""Define the base module for server test."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

from influxdb.tests import using_pypy
from influxdb.tests.server_tests.influxdb_instance import InfluxDbInstance

from influxdb.client import InfluxDBClient

if not using_pypy:
    from influxdb.dataframe_client import DataFrameClient


def _setup_influxdb_server(inst):
    inst.influxd_inst = InfluxDbInstance(
        inst.influxdb_template_conf,
        udp_enabled=getattr(inst, 'influxdb_udp_enabled', False),
    )

    inst.cli = InfluxDBClient('localhost',
                              inst.influxd_inst.http_port,
                              'root',
                              '',
                              database='db')
    if not using_pypy:
        inst.cliDF = DataFrameClient('localhost',
                                     inst.influxd_inst.http_port,
                                     'root',
                                     '',
                                     database='db')


def _setup_gzip_client(inst):
    inst.cli = InfluxDBClient('localhost',
                              inst.influxd_inst.http_port,
                              'root',
                              '',
                              database='db',
                              gzip=True)


def _teardown_influxdb_server(inst):
    remove_tree = sys.exc_info() == (None, None, None)
    inst.influxd_inst.close(remove_tree=remove_tree)


class SingleTestCaseWithServerMixin(object):
    """Define the single testcase with server mixin.

    A mixin for unittest.TestCase to start an influxdb server instance
    in a temporary directory **for each test function/case**
    """

    # 'influxdb_template_conf' attribute must be set
    # on the TestCase class or instance.

    @classmethod
    def setUp(cls):
        """Set up an instance of the SingleTestCaseWithServerMixin."""
        _setup_influxdb_server(cls)

    @classmethod
    def tearDown(cls):
        """Tear down an instance of the SingleTestCaseWithServerMixin."""
        _teardown_influxdb_server(cls)


class ManyTestCasesWithServerMixin(object):
    """Define the many testcase with server mixin.

    Same as the SingleTestCaseWithServerMixin but this module creates
    a single instance for the whole class. Also pre-creates a fresh
    database: 'db'.
    """

    # 'influxdb_template_conf' attribute must be set on the class itself !

    @classmethod
    def setUpClass(cls):
        """Set up an instance of the ManyTestCasesWithServerMixin."""
        _setup_influxdb_server(cls)

    def setUp(self):
        """Set up an instance of the ManyTestCasesWithServerMixin."""
        self.cli.create_database('db')

    @classmethod
    def tearDownClass(cls):
        """Deconstruct an instance of ManyTestCasesWithServerMixin."""
        _teardown_influxdb_server(cls)

    def tearDown(self):
        """Deconstruct an instance of ManyTestCasesWithServerMixin."""
        self.cli.drop_database('db')


class SingleTestCaseWithServerGzipMixin(object):
    """Define the single testcase with server with gzip client mixin.

    Same as the SingleTestCaseWithServerGzipMixin but the InfluxDBClient has
    gzip=True
    """

    @classmethod
    def setUp(cls):
        """Set up an instance of the SingleTestCaseWithServerGzipMixin."""
        _setup_influxdb_server(cls)
        _setup_gzip_client(cls)

    @classmethod
    def tearDown(cls):
        """Tear down an instance of the SingleTestCaseWithServerMixin."""
        _teardown_influxdb_server(cls)


class ManyTestCasesWithServerGzipMixin(object):
    """Define the many testcase with server with gzip client mixin.

    Same as the ManyTestCasesWithServerMixin but the InfluxDBClient has
    gzip=True.
    """

    @classmethod
    def setUpClass(cls):
        """Set up an instance of the ManyTestCasesWithServerGzipMixin."""
        _setup_influxdb_server(cls)
        _setup_gzip_client(cls)

    @classmethod
    def tearDown(cls):
        """Tear down an instance of the SingleTestCaseWithServerMixin."""
        _teardown_influxdb_server(cls)
