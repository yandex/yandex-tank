# -*- coding: utf-8 -*-
"""Unit tests for checking the InfluxDB server.

The good/expected interaction between:

+ the python client.. (obviously)
+ and a *_real_* server instance running.

This basically duplicates what's in client_test.py
but without mocking around every call.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from functools import partial
import os
import time
import unittest
import warnings

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError

from influxdb.tests import skip_if_pypy, using_pypy, skip_server_tests
from influxdb.tests.server_tests.base import ManyTestCasesWithServerMixin
from influxdb.tests.server_tests.base import SingleTestCaseWithServerMixin
from influxdb.tests.server_tests.base import ManyTestCasesWithServerGzipMixin
from influxdb.tests.server_tests.base import SingleTestCaseWithServerGzipMixin

# By default, raise exceptions on warnings
warnings.simplefilter('error', FutureWarning)

if not using_pypy:
    import pandas as pd
    from pandas.util.testing import assert_frame_equal


THIS_DIR = os.path.abspath(os.path.dirname(__file__))


def point(series_name, timestamp=None, tags=None, **fields):
    """Define what a point looks like."""
    res = {'measurement': series_name}

    if timestamp:
        res['time'] = timestamp

    if tags:
        res['tags'] = tags

    res['fields'] = fields
    return res


dummy_point = [  # some dummy points
    {
        "measurement": "cpu_load_short",
        "tags": {
            "host": "server01",
            "region": "us-west"
        },
        "time": "2009-11-10T23:00:00Z",
        "fields": {
            "value": 0.64
        }
    }
]

dummy_points = [  # some dummy points
    dummy_point[0],
    {
        "measurement": "memory",
        "tags": {
            "host": "server01",
            "region": "us-west"
        },
        "time": "2009-11-10T23:01:35Z",
        "fields": {
            "value": 33.0
        }
    }
]

if not using_pypy:
    dummy_point_df = {
        "measurement": "cpu_load_short",
        "tags": {"host": "server01",
                 "region": "us-west"},
        "dataframe": pd.DataFrame(
            [[0.64]], columns=['value'],
            index=pd.to_datetime(["2009-11-10T23:00:00Z"]))
    }
    dummy_points_df = [{
        "measurement": "cpu_load_short",
        "tags": {"host": "server01", "region": "us-west"},
        "dataframe": pd.DataFrame(
            [[0.64]], columns=['value'],
            index=pd.to_datetime(["2009-11-10T23:00:00Z"])),
    }, {
        "measurement": "memory",
        "tags": {"host": "server01", "region": "us-west"},
        "dataframe": pd.DataFrame(
            [[33]], columns=['value'],
            index=pd.to_datetime(["2009-11-10T23:01:35Z"])
        )
    }]


dummy_point_without_timestamp = [
    {
        "measurement": "cpu_load_short",
        "tags": {
            "host": "server02",
            "region": "us-west"
        },
        "fields": {
            "value": 0.64
        }
    }
]


@skip_server_tests
class SimpleTests(SingleTestCaseWithServerMixin, unittest.TestCase):
    """Define the class of simple tests."""

    influxdb_template_conf = os.path.join(THIS_DIR, 'influxdb.conf.template')

    def test_fresh_server_no_db(self):
        """Test a fresh server without database."""
        self.assertEqual([], self.cli.get_list_database())

    def test_create_database(self):
        """Test create a database."""
        self.assertIsNone(self.cli.create_database('new_db_1'))
        self.assertIsNone(self.cli.create_database('new_db_2'))
        self.assertEqual(
            self.cli.get_list_database(),
            [{'name': 'new_db_1'}, {'name': 'new_db_2'}]
        )

    def test_drop_database(self):
        """Test drop a database."""
        self.test_create_database()
        self.assertIsNone(self.cli.drop_database('new_db_1'))
        self.assertEqual([{'name': 'new_db_2'}], self.cli.get_list_database())

    def test_query_fail(self):
        """Test that a query failed."""
        with self.assertRaises(InfluxDBClientError) as ctx:
            self.cli.query('select column_one from foo')
        self.assertIn('database not found: db',
                      ctx.exception.content)

    def test_query_fail_ignore_errors(self):
        """Test query failed but ignore errors."""
        result = self.cli.query('select column_one from foo',
                                raise_errors=False)
        self.assertEqual(result.error, 'database not found: db')

    def test_create_user(self):
        """Test create user."""
        self.cli.create_user('test_user', 'secret_password')
        rsp = list(self.cli.query("SHOW USERS")['results'])
        self.assertIn({'user': 'test_user', 'admin': False},
                      rsp)

    def test_create_user_admin(self):
        """Test create admin user."""
        self.cli.create_user('test_user', 'secret_password', True)
        rsp = list(self.cli.query("SHOW USERS")['results'])
        self.assertIn({'user': 'test_user', 'admin': True},
                      rsp)

    def test_create_user_blank_password(self):
        """Test create user with a blank pass."""
        self.cli.create_user('test_user', '')
        rsp = list(self.cli.query("SHOW USERS")['results'])
        self.assertIn({'user': 'test_user', 'admin': False},
                      rsp)

    def test_get_list_users_empty(self):
        """Test get list of users, but empty."""
        rsp = self.cli.get_list_users()
        self.assertEqual([], rsp)

    def test_get_list_users(self):
        """Test get list of users."""
        self.cli.query("CREATE USER test WITH PASSWORD 'test'")
        rsp = self.cli.get_list_users()

        self.assertEqual(
            [{'user': 'test', 'admin': False}],
            rsp
        )

    def test_create_user_blank_username(self):
        """Test create blank username."""
        with self.assertRaises(InfluxDBClientError) as ctx:
            self.cli.create_user('', 'secret_password')
        self.assertIn('username required',
                      ctx.exception.content)
        rsp = list(self.cli.query("SHOW USERS")['results'])
        self.assertEqual(rsp, [])

    def test_drop_user(self):
        """Test drop a user."""
        self.cli.query("CREATE USER test WITH PASSWORD 'test'")
        self.cli.drop_user('test')
        users = list(self.cli.query("SHOW USERS")['results'])
        self.assertEqual(users, [])

    def test_drop_user_nonexisting(self):
        """Test dropping a nonexistent user."""
        with self.assertRaises(InfluxDBClientError) as ctx:
            self.cli.drop_user('test')
        self.assertIn('user not found',
                      ctx.exception.content)

    @unittest.skip("Broken as of 0.9.0")
    def test_revoke_admin_privileges(self):
        """Test revoking admin privs, deprecated as of v0.9.0."""
        self.cli.create_user('test', 'test', admin=True)
        self.assertEqual([{'user': 'test', 'admin': True}],
                         self.cli.get_list_users())
        self.cli.revoke_admin_privileges('test')
        self.assertEqual([{'user': 'test', 'admin': False}],
                         self.cli.get_list_users())

    def test_grant_privilege(self):
        """Test grant privs to user."""
        self.cli.create_user('test', 'test')
        self.cli.create_database('testdb')
        self.cli.grant_privilege('all', 'testdb', 'test')
        # TODO: when supported by InfluxDB, check if privileges are granted

    def test_grant_privilege_invalid(self):
        """Test grant invalid privs to user."""
        self.cli.create_user('test', 'test')
        self.cli.create_database('testdb')
        with self.assertRaises(InfluxDBClientError) as ctx:
            self.cli.grant_privilege('', 'testdb', 'test')
        self.assertEqual(400, ctx.exception.code)
        self.assertIn('{"error":"error parsing query: ',
                      ctx.exception.content)

    def test_revoke_privilege(self):
        """Test revoke privs from user."""
        self.cli.create_user('test', 'test')
        self.cli.create_database('testdb')
        self.cli.revoke_privilege('all', 'testdb', 'test')
        # TODO: when supported by InfluxDB, check if privileges are revoked

    def test_revoke_privilege_invalid(self):
        """Test revoke invalid privs from user."""
        self.cli.create_user('test', 'test')
        self.cli.create_database('testdb')
        with self.assertRaises(InfluxDBClientError) as ctx:
            self.cli.revoke_privilege('', 'testdb', 'test')
        self.assertEqual(400, ctx.exception.code)
        self.assertIn('{"error":"error parsing query: ',
                      ctx.exception.content)

    def test_invalid_port_fails(self):
        """Test invalid port access fails."""
        with self.assertRaises(ValueError):
            InfluxDBClient('host', '80/redir', 'username', 'password')


@skip_server_tests
class CommonTests(ManyTestCasesWithServerMixin, unittest.TestCase):
    """Define a class to handle common tests for the server."""

    influxdb_template_conf = os.path.join(THIS_DIR, 'influxdb.conf.template')

    def test_write(self):
        """Test write to the server."""
        self.assertIs(True, self.cli.write(
            {'points': dummy_point},
            params={'db': 'db'},
        ))

    def test_write_check_read(self):
        """Test write and check read of data to server."""
        self.test_write()
        time.sleep(1)
        rsp = self.cli.query('SELECT * FROM cpu_load_short', database='db')
        self.assertListEqual([{'value': 0.64, 'time': '2009-11-10T23:00:00Z',
                               "host": "server01", "region": "us-west"}],
                             list(rsp.get_points()))

    def test_write_points(self):
        """Test writing points to the server."""
        self.assertIs(True, self.cli.write_points(dummy_point))

    @skip_if_pypy
    def test_write_points_DF(self):
        """Test writing points with dataframe."""
        self.assertIs(
            True,
            self.cliDF.write_points(
                dummy_point_df['dataframe'],
                dummy_point_df['measurement'],
                dummy_point_df['tags']
            )
        )

    def test_write_points_check_read(self):
        """Test writing points and check read back."""
        self.test_write_points()
        time.sleep(1)  # same as test_write_check_read()
        rsp = self.cli.query('SELECT * FROM cpu_load_short')

        self.assertEqual(
            list(rsp),
            [[
                {'value': 0.64,
                 'time': '2009-11-10T23:00:00Z',
                 "host": "server01",
                 "region": "us-west"}
            ]]
        )

        rsp2 = list(rsp.get_points())
        self.assertEqual(len(rsp2), 1)
        pt = rsp2[0]

        self.assertEqual(
            pt,
            {'time': '2009-11-10T23:00:00Z',
             'value': 0.64,
             "host": "server01",
             "region": "us-west"}
        )

    @unittest.skip("Broken as of 0.9.0")
    def test_write_points_check_read_DF(self):
        """Test write points and check back with dataframe."""
        self.test_write_points_DF()
        time.sleep(1)  # same as test_write_check_read()

        rsp = self.cliDF.query('SELECT * FROM cpu_load_short')
        assert_frame_equal(
            rsp['cpu_load_short'],
            dummy_point_df['dataframe']
        )

        # Query with Tags
        rsp = self.cliDF.query(
            "SELECT * FROM cpu_load_short GROUP BY *")
        assert_frame_equal(
            rsp[('cpu_load_short',
                 (('host', 'server01'), ('region', 'us-west')))],
            dummy_point_df['dataframe']
        )

    def test_write_multiple_points_different_series(self):
        """Test write multiple points to different series."""
        self.assertIs(True, self.cli.write_points(dummy_points))
        time.sleep(1)
        rsp = self.cli.query('SELECT * FROM cpu_load_short')
        lrsp = list(rsp)

        self.assertEqual(
            [[
                {'value': 0.64,
                 'time': '2009-11-10T23:00:00Z',
                 "host": "server01",
                 "region": "us-west"}
            ]],
            lrsp
        )

        rsp = list(self.cli.query('SELECT * FROM memory'))

        self.assertEqual(
            rsp,
            [[
                {'value': 33,
                 'time': '2009-11-10T23:01:35Z',
                 "host": "server01",
                 "region": "us-west"}
            ]]
        )

    def test_select_into_as_post(self):
        """Test SELECT INTO is POSTed."""
        self.assertIs(True, self.cli.write_points(dummy_points))
        time.sleep(1)
        rsp = self.cli.query('SELECT * INTO "newmeas" FROM "memory"')
        rsp = self.cli.query('SELECT * FROM "newmeas"')
        lrsp = list(rsp)

        self.assertEqual(
            lrsp,
            [[
                {'value': 33,
                 'time': '2009-11-10T23:01:35Z',
                 "host": "server01",
                 "region": "us-west"}
            ]]
        )

    @unittest.skip("Broken as of 0.9.0")
    def test_write_multiple_points_different_series_DF(self):
        """Test write multiple points using dataframe to different series."""
        for i in range(2):
            self.assertIs(
                True, self.cliDF.write_points(
                    dummy_points_df[i]['dataframe'],
                    dummy_points_df[i]['measurement'],
                    dummy_points_df[i]['tags']))
        time.sleep(1)
        rsp = self.cliDF.query('SELECT * FROM cpu_load_short')

        assert_frame_equal(
            rsp['cpu_load_short'],
            dummy_points_df[0]['dataframe']
        )

        rsp = self.cliDF.query('SELECT * FROM memory')
        assert_frame_equal(
            rsp['memory'],
            dummy_points_df[1]['dataframe']
        )

    def test_write_points_batch(self):
        """Test writing points in a batch."""
        dummy_points = [
            {"measurement": "cpu_usage", "tags": {"unit": "percent"},
             "time": "2009-11-10T23:00:00Z", "fields": {"value": 12.34}},
            {"measurement": "network", "tags": {"direction": "in"},
             "time": "2009-11-10T23:00:00Z", "fields": {"value": 123.00}},
            {"measurement": "network", "tags": {"direction": "out"},
             "time": "2009-11-10T23:00:00Z", "fields": {"value": 12.00}}
        ]
        self.cli.write_points(points=dummy_points,
                              tags={"host": "server01",
                                    "region": "us-west"},
                              batch_size=2)
        time.sleep(5)
        net_in = self.cli.query("SELECT value FROM network "
                                "WHERE direction=$dir",
                                bind_params={'dir': 'in'}
                                ).raw
        net_out = self.cli.query("SELECT value FROM network "
                                 "WHERE direction='out'").raw
        cpu = self.cli.query("SELECT value FROM cpu_usage").raw
        self.assertIn(123, net_in['series'][0]['values'][0])
        self.assertIn(12, net_out['series'][0]['values'][0])
        self.assertIn(12.34, cpu['series'][0]['values'][0])

    def test_write_points_batch_generator(self):
        """Test writing points in a batch from a generator."""
        dummy_points = [
            {"measurement": "cpu_usage", "tags": {"unit": "percent"},
                "time": "2009-11-10T23:00:00Z", "fields": {"value": 12.34}},
            {"measurement": "network", "tags": {"direction": "in"},
                "time": "2009-11-10T23:00:00Z", "fields": {"value": 123.00}},
            {"measurement": "network", "tags": {"direction": "out"},
                "time": "2009-11-10T23:00:00Z", "fields": {"value": 12.00}}
        ]
        dummy_points_generator = (point for point in dummy_points)
        self.cli.write_points(points=dummy_points_generator,
                              tags={"host": "server01",
                                    "region": "us-west"},
                              batch_size=2)
        time.sleep(5)
        net_in = self.cli.query("SELECT value FROM network "
                                "WHERE direction=$dir",
                                bind_params={'dir': 'in'}
                                ).raw
        net_out = self.cli.query("SELECT value FROM network "
                                 "WHERE direction='out'").raw
        cpu = self.cli.query("SELECT value FROM cpu_usage").raw
        self.assertIn(123, net_in['series'][0]['values'][0])
        self.assertIn(12, net_out['series'][0]['values'][0])
        self.assertIn(12.34, cpu['series'][0]['values'][0])

    def test_query(self):
        """Test querying data back from server."""
        self.assertIs(True, self.cli.write_points(dummy_point))

    @unittest.skip('Not implemented for 0.9')
    def test_query_chunked(self):
        """Test query for chunked response from server."""
        cli = InfluxDBClient(database='db')
        example_object = {
            'points': [
                [1415206250119, 40001, 667],
                [1415206244555, 30001, 7],
                [1415206228241, 20001, 788],
                [1415206212980, 10001, 555],
                [1415197271586, 10001, 23]
            ],
            'name': 'foo',
            'columns': [
                'time',
                'sequence_number',
                'val'
            ]
        }
        del cli
        del example_object
        # TODO ?

    def test_delete_series_invalid(self):
        """Test delete invalid series."""
        with self.assertRaises(InfluxDBClientError):
            self.cli.delete_series()

    def test_default_retention_policy(self):
        """Test add default retention policy."""
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'name': 'autogen',
                 'duration': '0s',
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'default': True}
            ],
            rsp
        )

    def test_create_retention_policy_default(self):
        """Test create a new default retention policy."""
        self.cli.create_retention_policy('somename', '1d', 1, default=True)
        self.cli.create_retention_policy('another', '2d', 1, default=False)
        rsp = self.cli.get_list_retention_policies()

        self.assertEqual(
            [
                {'duration': '0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '24h0m0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'1h0m0s',
                 'name': 'somename'},
                {'duration': '48h0m0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'24h0m0s',
                 'name': 'another'}
            ],
            rsp
        )

    def test_create_retention_policy(self):
        """Test creating a new retention policy, not default."""
        self.cli.create_retention_policy('somename', '1d', 1)
        # NB: creating a retention policy without specifying
        # shard group duration
        #     leads to a shard group duration of 1 hour
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '24h0m0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'1h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

        self.cli.drop_retention_policy('somename', 'db')
        # recreate the RP
        self.cli.create_retention_policy('somename', '1w', 1,
                                         shard_duration='1h')

        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '168h0m0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'1h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

        self.cli.drop_retention_policy('somename', 'db')
        # recreate the RP
        self.cli.create_retention_policy('somename', '1w', 1)

        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '168h0m0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'24h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

    def test_alter_retention_policy(self):
        """Test alter a retention policy, not default."""
        self.cli.create_retention_policy('somename', '1d', 1)

        # Test alter duration
        self.cli.alter_retention_policy('somename', 'db',
                                        duration='4d',
                                        shard_duration='2h')
        # NB: altering retention policy doesn't change shard group duration
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '96h0m0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'2h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

        # Test alter replication
        self.cli.alter_retention_policy('somename', 'db',
                                        replication=4)

        # NB: altering retention policy doesn't change shard group duration
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '96h0m0s',
                 'default': False,
                 'replicaN': 4,
                 'shardGroupDuration': u'2h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

        # Test alter default
        self.cli.alter_retention_policy('somename', 'db',
                                        default=True)
        # NB: altering retention policy doesn't change shard group duration
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '96h0m0s',
                 'default': True,
                 'replicaN': 4,
                 'shardGroupDuration': u'2h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

        # Test alter shard_duration
        self.cli.alter_retention_policy('somename', 'db',
                                        shard_duration='4h')

        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '96h0m0s',
                 'default': True,
                 'replicaN': 4,
                 'shardGroupDuration': u'4h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

    def test_alter_retention_policy_invalid(self):
        """Test invalid alter retention policy."""
        self.cli.create_retention_policy('somename', '1d', 1)
        with self.assertRaises(InfluxDBClientError) as ctx:
            self.cli.alter_retention_policy('somename', 'db')
        self.assertEqual(400, ctx.exception.code)
        self.assertIn('{"error":"error parsing query: ',
                      ctx.exception.content)
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'},
                {'duration': '24h0m0s',
                 'default': False,
                 'replicaN': 1,
                 'shardGroupDuration': u'1h0m0s',
                 'name': 'somename'}
            ],
            rsp
        )

    def test_drop_retention_policy(self):
        """Test drop a retention policy."""
        self.cli.create_retention_policy('somename', '1d', 1)

        # Test drop retention
        self.cli.drop_retention_policy('somename', 'db')
        rsp = self.cli.get_list_retention_policies()
        self.assertEqual(
            [
                {'duration': '0s',
                 'default': True,
                 'replicaN': 1,
                 'shardGroupDuration': u'168h0m0s',
                 'name': 'autogen'}
            ],
            rsp
        )

    def test_create_continuous_query(self):
        """Test continuous query creation."""
        self.cli.create_retention_policy('some_rp', '1d', 1)
        query = 'select count("value") into "some_rp"."events" from ' \
                '"events" group by time(10m)'
        self.cli.create_continuous_query('test_cq', query, 'db')
        cqs = self.cli.get_list_continuous_queries()
        expected_cqs = [
            {
                'db': [
                    {
                        'name': 'test_cq',
                        'query': 'CREATE CONTINUOUS QUERY test_cq ON db '
                                 'BEGIN SELECT count(value) INTO '
                                 'db.some_rp.events FROM db.autogen.events '
                                 'GROUP BY time(10m) END'
                    }
                ]
            }
        ]
        self.assertEqual(cqs, expected_cqs)

    def test_drop_continuous_query(self):
        """Test continuous query drop."""
        self.test_create_continuous_query()
        self.cli.drop_continuous_query('test_cq', 'db')
        cqs = self.cli.get_list_continuous_queries()
        expected_cqs = [{'db': []}]
        self.assertEqual(cqs, expected_cqs)

    def test_issue_143(self):
        """Test for PR#143 from repo."""
        pt = partial(point, 'a_series_name', timestamp='2015-03-30T16:16:37Z')
        pts = [
            pt(value=15),
            pt(tags={'tag_1': 'value1'}, value=5),
            pt(tags={'tag_1': 'value2'}, value=10),
        ]
        self.cli.write_points(pts)
        time.sleep(1)
        rsp = list(self.cli.query('SELECT * FROM a_series_name \
GROUP BY tag_1').get_points())

        self.assertEqual(
            [
                {'time': '2015-03-30T16:16:37Z', 'value': 15},
                {'time': '2015-03-30T16:16:37Z', 'value': 5},
                {'time': '2015-03-30T16:16:37Z', 'value': 10}
            ],
            rsp
        )

        # a slightly more complex one with 2 tags values:
        pt = partial(point, 'series2', timestamp='2015-03-30T16:16:37Z')
        pts = [
            pt(tags={'tag1': 'value1', 'tag2': 'v1'}, value=0),
            pt(tags={'tag1': 'value1', 'tag2': 'v2'}, value=5),
            pt(tags={'tag1': 'value2', 'tag2': 'v1'}, value=10),
        ]
        self.cli.write_points(pts)
        time.sleep(1)
        rsp = self.cli.query('SELECT * FROM series2 GROUP BY tag1,tag2')

        self.assertEqual(
            [
                {'value': 0, 'time': '2015-03-30T16:16:37Z'},
                {'value': 5, 'time': '2015-03-30T16:16:37Z'},
                {'value': 10, 'time': '2015-03-30T16:16:37Z'}
            ],
            list(rsp['series2'])
        )

        all_tag2_equal_v1 = list(rsp.get_points(tags={'tag2': 'v1'}))

        self.assertEqual(
            [{'value': 0, 'time': '2015-03-30T16:16:37Z'},
             {'value': 10, 'time': '2015-03-30T16:16:37Z'}],
            all_tag2_equal_v1,
        )

    def test_query_multiple_series(self):
        """Test query for multiple series."""
        pt = partial(point, 'series1', timestamp='2015-03-30T16:16:37Z')
        pts = [
            pt(tags={'tag1': 'value1', 'tag2': 'v1'}, value=0),
        ]
        self.cli.write_points(pts)

        pt = partial(point, 'series2', timestamp='1970-03-30T16:16:37Z')
        pts = [
            pt(tags={'tag1': 'value1', 'tag2': 'v1'},
               value=0, data1=33, data2="bla"),
        ]
        self.cli.write_points(pts)

    def test_get_list_series(self):
        """Test get a list of series from the database."""
        dummy_points = [
            {
                "measurement": "cpu_load_short",
                "tags": {
                    "host": "server01",
                    "region": "us-west"
                },
                "time": "2009-11-10T23:00:00.123456Z",
                "fields": {
                    "value": 0.64
                }
            }
        ]

        dummy_points_2 = [
            {
                "measurement": "memory_usage",
                "tags": {
                    "host": "server02",
                    "region": "us-east"
                },
                "time": "2009-11-10T23:00:00.123456Z",
                "fields": {
                    "value": 80
                }
            }
        ]

        self.cli.write_points(dummy_points)
        self.cli.write_points(dummy_points_2)

        self.assertEquals(
            self.cli.get_list_series(),
            ['cpu_load_short,host=server01,region=us-west',
             'memory_usage,host=server02,region=us-east']
        )

        self.assertEquals(
            self.cli.get_list_series(measurement='memory_usage'),
            ['memory_usage,host=server02,region=us-east']
        )

        self.assertEquals(
            self.cli.get_list_series(measurement='memory_usage'),
            ['memory_usage,host=server02,region=us-east']
        )

        self.assertEquals(
            self.cli.get_list_series(tags={'host': 'server02'}),
            ['memory_usage,host=server02,region=us-east'])

        self.assertEquals(
            self.cli.get_list_series(
                measurement='cpu_load_short', tags={'host': 'server02'}),
            [])


@skip_server_tests
class UdpTests(ManyTestCasesWithServerMixin, unittest.TestCase):
    """Define a class to test UDP series."""

    influxdb_udp_enabled = True
    influxdb_template_conf = os.path.join(THIS_DIR,
                                          'influxdb.conf.template')

    def test_write_points_udp(self):
        """Test write points UDP."""
        cli = InfluxDBClient(
            'localhost',
            self.influxd_inst.http_port,
            'root',
            '',
            database='db',
            use_udp=True,
            udp_port=self.influxd_inst.udp_port
        )
        cli.write_points(dummy_point)

        # The points are not immediately available after write_points.
        # This is to be expected because we are using udp (no response !).
        # So we have to wait some time,
        time.sleep(3)  # 3 sec seems to be a good choice.
        rsp = self.cli.query('SELECT * FROM cpu_load_short')

        self.assertEqual(
            # this is dummy_points :
            [
                {'value': 0.64,
                 'time': '2009-11-10T23:00:00Z',
                 "host": "server01",
                 "region": "us-west"}
            ],
            list(rsp['cpu_load_short'])
        )


# Run the tests again, but with gzip enabled this time
@skip_server_tests
class GzipSimpleTests(SimpleTests, SingleTestCaseWithServerGzipMixin):
    """Repeat the simple tests with InfluxDBClient where gzip=True."""

    pass


@skip_server_tests
class GzipCommonTests(CommonTests, ManyTestCasesWithServerGzipMixin):
    """Repeat the common tests with InfluxDBClient where gzip=True."""

    pass


@skip_server_tests
class GzipUdpTests(UdpTests, ManyTestCasesWithServerGzipMixin):
    """Repeat the UDP tests with InfluxDBClient where gzip=True."""

    pass
