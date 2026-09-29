# -*- coding: utf-8 -*-
"""Client unit tests."""

import json
import socket
import sys
import unittest
import random
import warnings

import mock
import requests
import requests.exceptions
import requests_mock

from nose.tools import raises
from mock import patch

from influxdb.influxdb08 import InfluxDBClient
from influxdb.influxdb08.client import session

if sys.version < '3':
    import codecs

    def u(x):
        """Test codec."""
        return codecs.unicode_escape_decode(x)[0]
else:
    def u(x):
        """Test codec."""
        return x


def _build_response_object(status_code=200, content=""):
    resp = requests.Response()
    resp.status_code = status_code
    resp._content = content.encode("utf8")
    return resp


def _mocked_session(method="GET", status_code=200, content=""):
    method = method.upper()

    def request(*args, **kwargs):
        """Define a request for the _mocked_session."""
        c = content

        # Check method
        assert method == kwargs.get('method', 'GET')

        if method == 'POST':
            data = kwargs.get('data', None)

            if data is not None:
                # Data must be a string
                assert isinstance(data, str)

                # Data must be a JSON string
                assert c == json.loads(data, strict=True)

                c = data

        # Anyway, Content must be a JSON string (or empty string)
        if not isinstance(c, str):
            c = json.dumps(c)

        return _build_response_object(status_code=status_code, content=c)

    mocked = patch.object(
        session,
        'request',
        side_effect=request
    )

    return mocked


class TestInfluxDBClient(unittest.TestCase):
    """Define a TestInfluxDBClient object."""

    def setUp(self):
        """Set up a TestInfluxDBClient object."""
        # By default, raise exceptions on warnings
        warnings.simplefilter('error', FutureWarning)

        self.dummy_points = [
            {
                "points": [
                    ["1", 1, 1.0],
                    ["2", 2, 2.0]
                ],
                "name": "foo",
                "columns": ["column_one", "column_two", "column_three"]
            }
        ]

        self.dsn_string = 'influxdb://uSr:pWd@host:1886/db'

    def test_scheme(self):
        """Test database scheme for TestInfluxDBClient object."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'database')
        self.assertEqual(cli._baseurl, 'http://host:8086')

        cli = InfluxDBClient(
            'host', 8086, 'username', 'password', 'database', ssl=True
        )
        self.assertEqual(cli._baseurl, 'https://host:8086')

    def test_dsn(self):
        """Test datasource name for TestInfluxDBClient object."""
        cli = InfluxDBClient.from_dsn(self.dsn_string)
        self.assertEqual('http://host:1886', cli._baseurl)
        self.assertEqual('uSr', cli._username)
        self.assertEqual('pWd', cli._password)
        self.assertEqual('db', cli._database)
        self.assertFalse(cli._use_udp)

        cli = InfluxDBClient.from_dsn('udp+' + self.dsn_string)
        self.assertTrue(cli._use_udp)

        cli = InfluxDBClient.from_dsn('https+' + self.dsn_string)
        self.assertEqual('https://host:1886', cli._baseurl)

        cli = InfluxDBClient.from_dsn('https+' + self.dsn_string,
                                      **{'ssl': False})
        self.assertEqual('http://host:1886', cli._baseurl)

    def test_switch_database(self):
        """Test switch database for TestInfluxDBClient object."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'database')
        cli.switch_database('another_database')
        self.assertEqual(cli._database, 'another_database')

    @raises(FutureWarning)
    def test_switch_db_deprecated(self):
        """Test deprecated switch database for TestInfluxDBClient object."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'database')
        cli.switch_db('another_database')
        self.assertEqual(cli._database, 'another_database')

    def test_switch_user(self):
        """Test switch user for TestInfluxDBClient object."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'database')
        cli.switch_user('another_username', 'another_password')
        self.assertEqual(cli._username, 'another_username')
        self.assertEqual(cli._password, 'another_password')

    def test_write(self):
        """Test write to database for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/write"
            )
            cli = InfluxDBClient(database='db')
            cli.write(
                {"database": "mydb",
                 "retentionPolicy": "mypolicy",
                 "points": [{"name": "cpu_load_short",
                             "tags": {"host": "server01",
                                      "region": "us-west"},
                             "timestamp": "2009-11-10T23:00:00Z",
                             "values": {"value": 0.64}}]}
            )

            self.assertEqual(
                json.loads(m.last_request.body),
                {"database": "mydb",
                 "retentionPolicy": "mypolicy",
                 "points": [{"name": "cpu_load_short",
                             "tags": {"host": "server01",
                                      "region": "us-west"},
                             "timestamp": "2009-11-10T23:00:00Z",
                             "values": {"value": 0.64}}]}
            )

    def test_write_points(self):
        """Test write points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/series"
            )

            cli = InfluxDBClient(database='db')
            cli.write_points(
                self.dummy_points
            )

            self.assertListEqual(
                json.loads(m.last_request.body),
                self.dummy_points
            )

    def test_write_points_string(self):
        """Test write string points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/series"
            )

            cli = InfluxDBClient(database='db')
            cli.write_points(
                str(json.dumps(self.dummy_points))
            )

            self.assertListEqual(
                json.loads(m.last_request.body),
                self.dummy_points
            )

    def test_write_points_batch(self):
        """Test write batch points for TestInfluxDBClient object."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")
            cli = InfluxDBClient('localhost', 8086,
                                 'username', 'password', 'db')
            cli.write_points(data=self.dummy_points, batch_size=2)
        self.assertEqual(1, m.call_count)

    def test_write_points_batch_invalid_size(self):
        """Test write batch points invalid size for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")
            cli = InfluxDBClient('localhost', 8086,
                                 'username', 'password', 'db')
            cli.write_points(data=self.dummy_points, batch_size=-2)
        self.assertEqual(1, m.call_count)

    def test_write_points_batch_multiple_series(self):
        """Test write points batch multiple series."""
        dummy_points = [
            {"points": [["1", 1, 1.0], ["2", 2, 2.0], ["3", 3, 3.0],
                        ["4", 4, 4.0], ["5", 5, 5.0]],
             "name": "foo",
             "columns": ["val1", "val2", "val3"]},
            {"points": [["1", 1, 1.0], ["2", 2, 2.0], ["3", 3, 3.0],
                        ["4", 4, 4.0], ["5", 5, 5.0], ["6", 6, 6.0],
                        ["7", 7, 7.0], ["8", 8, 8.0]],
             "name": "bar",
             "columns": ["val1", "val2", "val3"]},
        ]
        expected_last_body = [{'points': [['7', 7, 7.0], ['8', 8, 8.0]],
                               'name': 'bar',
                               'columns': ['val1', 'val2', 'val3']}]
        with requests_mock.Mocker() as m:
            m.register_uri(requests_mock.POST,
                           "http://localhost:8086/db/db/series")
            cli = InfluxDBClient('localhost', 8086,
                                 'username', 'password', 'db')
            cli.write_points(data=dummy_points, batch_size=3)
        self.assertEqual(m.call_count, 5)
        self.assertEqual(expected_last_body, m.request_history[4].json())

    def test_write_points_udp(self):
        """Test write points UDP for TestInfluxDBClient object."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        port = random.randint(4000, 8000)
        s.bind(('0.0.0.0', port))

        cli = InfluxDBClient(
            'localhost', 8086, 'root', 'root',
            'test', use_udp=True, udp_port=port
        )
        cli.write_points(self.dummy_points)

        received_data, addr = s.recvfrom(1024)

        self.assertEqual(self.dummy_points,
                         json.loads(received_data.decode(), strict=True))

    def test_write_bad_precision_udp(self):
        """Test write UDP w/bad precision."""
        cli = InfluxDBClient(
            'localhost', 8086, 'root', 'root',
            'test', use_udp=True, udp_port=4444
        )

        with self.assertRaisesRegexp(
                Exception,
                "InfluxDB only supports seconds precision for udp writes"
        ):
            cli.write_points(
                self.dummy_points,
                time_precision='ms'
            )

    @raises(Exception)
    def test_write_points_fails(self):
        """Test failed write points for TestInfluxDBClient object."""
        with _mocked_session('post', 500):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.write_points([])

    def test_write_points_with_precision(self):
        """Test write points with precision."""
        with _mocked_session('post', 200, self.dummy_points):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            self.assertTrue(cli.write_points(self.dummy_points))

    def test_write_points_bad_precision(self):
        """Test write points with bad precision."""
        cli = InfluxDBClient()
        with self.assertRaisesRegexp(
            Exception,
            "Invalid time precision is given. \(use 's', 'm', 'ms' or 'u'\)"
        ):
            cli.write_points(
                self.dummy_points,
                time_precision='g'
            )

    @raises(Exception)
    def test_write_points_with_precision_fails(self):
        """Test write points where precision fails."""
        with _mocked_session('post', 500):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.write_points_with_precision([])

    def test_delete_points(self):
        """Test delete points for TestInfluxDBClient object."""
        with _mocked_session('delete', 204) as mocked:
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            self.assertTrue(cli.delete_points("foo"))

            self.assertEqual(len(mocked.call_args_list), 1)
            args, kwds = mocked.call_args_list[0]

            self.assertEqual(kwds['params'],
                             {'u': 'username', 'p': 'password'})
            self.assertEqual(kwds['url'], 'http://host:8086/db/db/series/foo')

    @raises(Exception)
    def test_delete_points_with_wrong_name(self):
        """Test delete points with wrong name."""
        with _mocked_session('delete', 400):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.delete_points("nonexist")

    @raises(NotImplementedError)
    def test_create_scheduled_delete(self):
        """Test create scheduled deletes."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.create_scheduled_delete([])

    @raises(NotImplementedError)
    def test_get_list_scheduled_delete(self):
        """Test get schedule list of deletes TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.get_list_scheduled_delete()

    @raises(NotImplementedError)
    def test_remove_scheduled_delete(self):
        """Test remove scheduled delete TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.remove_scheduled_delete(1)

    def test_query(self):
        """Test query for TestInfluxDBClient object."""
        data = [
            {
                "name": "foo",
                "columns": ["time", "sequence_number", "column_one"],
                "points": [
                    [1383876043, 16, "2"], [1383876043, 15, "1"],
                    [1383876035, 14, "2"], [1383876035, 13, "1"]
                ]
            }
        ]
        with _mocked_session('get', 200, data):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            result = cli.query('select column_one from foo;')
            self.assertEqual(len(result[0]['points']), 4)

    def test_query_chunked(self):
        """Test chunked query for TestInfluxDBClient object."""
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
        example_response = \
            json.dumps(example_object) + json.dumps(example_object)

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response
            )

            self.assertListEqual(
                cli.query('select * from foo', chunked=True),
                [example_object, example_object]
            )

    def test_query_chunked_unicode(self):
        """Test unicode chunked query for TestInfluxDBClient object."""
        cli = InfluxDBClient(database='db')
        example_object = {
            'points': [
                [1415206212980, 10001, u('unicode-\xcf\x89')],
                [1415197271586, 10001, u('more-unicode-\xcf\x90')]
            ],
            'name': 'foo',
            'columns': [
                'time',
                'sequence_number',
                'val'
            ]
        }
        example_response = \
            json.dumps(example_object) + json.dumps(example_object)

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response
            )

            self.assertListEqual(
                cli.query('select * from foo', chunked=True),
                [example_object, example_object]
            )

    @raises(Exception)
    def test_query_fail(self):
        """Test failed query for TestInfluxDBClient."""
        with _mocked_session('get', 401):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.query('select column_one from foo;')

    def test_query_bad_precision(self):
        """Test query with bad precision for TestInfluxDBClient."""
        cli = InfluxDBClient()
        with self.assertRaisesRegexp(
            Exception,
            "Invalid time precision is given. \(use 's', 'm', 'ms' or 'u'\)"
        ):
            cli.query('select column_one from foo', time_precision='g')

    def test_create_database(self):
        """Test create database for TestInfluxDBClient."""
        with _mocked_session('post', 201, {"name": "new_db"}):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            self.assertTrue(cli.create_database('new_db'))

    @raises(Exception)
    def test_create_database_fails(self):
        """Test failed create database for TestInfluxDBClient."""
        with _mocked_session('post', 401):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.create_database('new_db')

    def test_delete_database(self):
        """Test delete database for TestInfluxDBClient."""
        with _mocked_session('delete', 204):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            self.assertTrue(cli.delete_database('old_db'))

    @raises(Exception)
    def test_delete_database_fails(self):
        """Test failed delete database for TestInfluxDBClient."""
        with _mocked_session('delete', 401):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.delete_database('old_db')

    def test_get_list_database(self):
        """Test get list of databases for TestInfluxDBClient."""
        data = [
            {"name": "a_db"}
        ]
        with _mocked_session('get', 200, data):
            cli = InfluxDBClient('host', 8086, 'username', 'password')
            self.assertEqual(len(cli.get_list_database()), 1)
            self.assertEqual(cli.get_list_database()[0]['name'], 'a_db')

    @raises(Exception)
    def test_get_list_database_fails(self):
        """Test failed get list of databases for TestInfluxDBClient."""
        with _mocked_session('get', 401):
            cli = InfluxDBClient('host', 8086, 'username', 'password')
            cli.get_list_database()

    @raises(FutureWarning)
    def test_get_database_list_deprecated(self):
        """Test deprecated get database list for TestInfluxDBClient."""
        data = [
            {"name": "a_db"}
        ]
        with _mocked_session('get', 200, data):
            cli = InfluxDBClient('host', 8086, 'username', 'password')
            self.assertEqual(len(cli.get_database_list()), 1)
            self.assertEqual(cli.get_database_list()[0]['name'], 'a_db')

    def test_delete_series(self):
        """Test delete series for TestInfluxDBClient."""
        with _mocked_session('delete', 204):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.delete_series('old_series')

    @raises(Exception)
    def test_delete_series_fails(self):
        """Test failed delete series for TestInfluxDBClient."""
        with _mocked_session('delete', 401):
            cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
            cli.delete_series('old_series')

    def test_get_series_list(self):
        """Test get list of series for TestInfluxDBClient."""
        cli = InfluxDBClient(database='db')

        with requests_mock.Mocker() as m:
            example_response = \
                '[{"name":"list_series_result","columns":' \
                '["time","name"],"points":[[0,"foo"],[0,"bar"]]}]'

            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response
            )

            self.assertListEqual(
                cli.get_list_series(),
                ['foo', 'bar']
            )

    def test_get_continuous_queries(self):
        """Test get continuous queries for TestInfluxDBClient."""
        cli = InfluxDBClient(database='db')

        with requests_mock.Mocker() as m:

            # Tip: put this in a json linter!
            example_response = '[ { "name": "continuous queries", "columns"' \
                               ': [ "time", "id", "query" ], "points": [ [ ' \
                               '0, 1, "select foo(bar,95) from \\"foo_bar' \
                               's\\" group by time(5m) into response_times.' \
                               'percentiles.5m.95" ], [ 0, 2, "select perce' \
                               'ntile(value,95) from \\"response_times\\" g' \
                               'roup by time(5m) into response_times.percen' \
                               'tiles.5m.95" ] ] } ]'

            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/series",
                text=example_response
            )

            self.assertListEqual(
                cli.get_list_continuous_queries(),
                [
                    'select foo(bar,95) from "foo_bars" group '
                    'by time(5m) into response_times.percentiles.5m.95',

                    'select percentile(value,95) from "response_times" group '
                    'by time(5m) into response_times.percentiles.5m.95'
                ]
            )

    def test_get_list_cluster_admins(self):
        """Test get list of cluster admins, not implemented."""
        pass

    def test_add_cluster_admin(self):
        """Test add cluster admin for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/cluster_admins"
            )

            cli = InfluxDBClient(database='db')
            cli.add_cluster_admin(
                new_username='paul',
                new_password='laup'
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {
                    'name': 'paul',
                    'password': 'laup'
                }
            )

    def test_update_cluster_admin_password(self):
        """Test update cluster admin pass for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/cluster_admins/paul"
            )

            cli = InfluxDBClient(database='db')
            cli.update_cluster_admin_password(
                username='paul',
                new_password='laup'
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {'password': 'laup'}
            )

    def test_delete_cluster_admin(self):
        """Test delete cluster admin for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.DELETE,
                "http://localhost:8086/cluster_admins/paul",
                status_code=200,
            )

            cli = InfluxDBClient(database='db')
            cli.delete_cluster_admin(username='paul')

            self.assertIsNone(m.last_request.body)

    def test_set_database_admin(self):
        """Test set database admin for TestInfluxDBClient."""
        pass

    def test_unset_database_admin(self):
        """Test unset database admin for TestInfluxDBClient."""
        pass

    def test_alter_database_admin(self):
        """Test alter database admin for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/users/paul"
            )

            cli = InfluxDBClient(database='db')
            cli.alter_database_admin(
                username='paul',
                is_admin=False
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {
                    'admin': False
                }
            )

    @raises(NotImplementedError)
    def test_get_list_database_admins(self):
        """Test get list of database admins for TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.get_list_database_admins()

    @raises(NotImplementedError)
    def test_add_database_admin(self):
        """Test add database admins for TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.add_database_admin('admin', 'admin_secret_password')

    @raises(NotImplementedError)
    def test_update_database_admin_password(self):
        """Test update database admin pass for TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.update_database_admin_password('admin', 'admin_secret_password')

    @raises(NotImplementedError)
    def test_delete_database_admin(self):
        """Test delete database admin for TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.delete_database_admin('admin')

    def test_get_database_users(self):
        """Test get database users for TestInfluxDBClient."""
        cli = InfluxDBClient('localhost', 8086, 'username', 'password', 'db')

        example_response = \
            '[{"name":"paul","isAdmin":false,"writeTo":".*","readFrom":".*"},'\
            '{"name":"bobby","isAdmin":false,"writeTo":".*","readFrom":".*"}]'

        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.GET,
                "http://localhost:8086/db/db/users",
                text=example_response
            )
            users = cli.get_database_users()

        self.assertEqual(json.loads(example_response), users)

    def test_add_database_user(self):
        """Test add database user for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/users"
            )
            cli = InfluxDBClient(database='db')
            cli.add_database_user(
                new_username='paul',
                new_password='laup',
                permissions=('.*', '.*')
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {
                    'writeTo': '.*',
                    'password': 'laup',
                    'readFrom': '.*',
                    'name': 'paul'
                }
            )

    def test_add_database_user_bad_permissions(self):
        """Test add database user with bad perms for TestInfluxDBClient."""
        cli = InfluxDBClient()

        with self.assertRaisesRegexp(
                Exception,
                "'permissions' must be \(readFrom, writeTo\) tuple"
        ):
            cli.add_database_user(
                new_password='paul',
                new_username='paul',
                permissions=('hello', 'hello', 'hello')
            )

    def test_alter_database_user_password(self):
        """Test alter database user pass for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/users/paul"
            )

            cli = InfluxDBClient(database='db')
            cli.alter_database_user(
                username='paul',
                password='n3wp4ss!'
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {
                    'password': 'n3wp4ss!'
                }
            )

    def test_alter_database_user_permissions(self):
        """Test alter database user perms for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/users/paul"
            )

            cli = InfluxDBClient(database='db')
            cli.alter_database_user(
                username='paul',
                permissions=('^$', '.*')
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {
                    'readFrom': '^$',
                    'writeTo': '.*'
                }
            )

    def test_alter_database_user_password_and_permissions(self):
        """Test alter database user pass and perms for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/db/users/paul"
            )

            cli = InfluxDBClient(database='db')
            cli.alter_database_user(
                username='paul',
                password='n3wp4ss!',
                permissions=('^$', '.*')
            )

            self.assertDictEqual(
                json.loads(m.last_request.body),
                {
                    'password': 'n3wp4ss!',
                    'readFrom': '^$',
                    'writeTo': '.*'
                }
            )

    def test_update_database_user_password_current_user(self):
        """Test update database user pass for TestInfluxDBClient."""
        cli = InfluxDBClient(
            username='root',
            password='hello',
            database='database'
        )
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.POST,
                "http://localhost:8086/db/database/users/root"
            )

            cli.update_database_user_password(
                username='root',
                new_password='bye'
            )

            self.assertEqual(cli._password, 'bye')

    def test_delete_database_user(self):
        """Test delete database user for TestInfluxDBClient."""
        with requests_mock.Mocker() as m:
            m.register_uri(
                requests_mock.DELETE,
                "http://localhost:8086/db/db/users/paul"
            )

            cli = InfluxDBClient(database='db')
            cli.delete_database_user(username='paul')

            self.assertIsNone(m.last_request.body)

    @raises(NotImplementedError)
    def test_update_permission(self):
        """Test update permission for TestInfluxDBClient."""
        cli = InfluxDBClient('host', 8086, 'username', 'password', 'db')
        cli.update_permission('admin', [])

    @mock.patch('requests.Session.request')
    def test_request_retry(self, mock_request):
        """Test that two connection errors will be handled."""
        class CustomMock(object):
            """Define CustomMock object."""

            def __init__(self):
                self.i = 0

            def connection_error(self, *args, **kwargs):
                """Test connection error in CustomMock."""
                self.i += 1

                if self.i < 3:
                    raise requests.exceptions.ConnectionError
                else:
                    r = requests.Response()
                    r.status_code = 200
                    return r

        mock_request.side_effect = CustomMock().connection_error

        cli = InfluxDBClient(database='db')
        cli.write_points(
            self.dummy_points
        )

    @mock.patch('requests.Session.request')
    def test_request_retry_raises(self, mock_request):
        """Test that three connection errors will not be handled."""
        class CustomMock(object):
            """Define CustomMock object."""

            def __init__(self):
                """Initialize the object."""
                self.i = 0

            def connection_error(self, *args, **kwargs):
                """Test the connection error for CustomMock."""
                self.i += 1

                if self.i < 4:
                    raise requests.exceptions.ConnectionError
                else:
                    r = requests.Response()
                    r.status_code = 200
                    return r

        mock_request.side_effect = CustomMock().connection_error

        cli = InfluxDBClient(database='db')

        with self.assertRaises(requests.exceptions.ConnectionError):
            cli.write_points(self.dummy_points)
