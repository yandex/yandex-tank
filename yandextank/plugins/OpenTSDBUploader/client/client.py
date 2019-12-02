# -*- coding: utf-8 -*-
"""Python client for OpenTSDB."""

import json
import random
import requests
import requests.exceptions
import time


class OpenTSDBClient(object):
    """OpenTSDBClient primary client object to connect OpenTSDB.
    The :class:`~.OpenTSDBClient` object holds information necessary to
    connect to OpenTSDB. Requests can be made to OpenTSDB directly through
    the client.
    :param host: hostname to connect to OpenTSDB, defaults to 'localhost'
    :type host: str
    :param port: port to connect to OpenTSDB, defaults to 4242
    :type port: int
    :param username: user to connect, defaults to 'root'
    :type username: str
    :param password: password of the user, defaults to 'root'
    :type password: str
    :param pool_size: urllib3 connection pool size, defaults to 10.
    :type pool_size: int
    :param ssl: use https instead of http to connect to OpenTSDB, defaults to
        False
    :type ssl: bool
    :param verify_ssl: verify SSL certificates for HTTPS requests, defaults to
        False
    :type verify_ssl: bool
    :param timeout: number of seconds Requests will wait for your client to
        establish a connection, defaults to None
    :type timeout: int
    :param retries: number of retries your client will try before aborting,
        defaults to 3. 0 indicates try until success
    :type retries: int
    :param proxies: HTTP(S) proxy to use for Requests, defaults to {}
    :type proxies: dict
    :param cert: Path to client certificate information to use for mutual TLS
        authentication. You can specify a local cert to use
        as a single file containing the private key and the certificate, or as
        a tuple of both files’ paths, defaults to None
    :type cert: str
    :raises ValueError: if cert is provided but ssl is disabled (set to False)
    """
    def __init__(
            self,
            host='localhost',
            port=4242,
            username='root',
            password='root',
            ssl=False,
            verify_ssl=False,
            timeout=None,
            retries=3,
            proxies=None,
            pool_size=10,
            cert=None,
    ):
        """Construct a new OpenTSDBClient object."""
        self._host = host
        self._port = int(port)
        self._username = username
        self._password = password
        self._timeout = timeout
        self._retries = retries

        self._verify_ssl = verify_ssl

        self._session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=int(pool_size), pool_maxsize=int(pool_size))

        self._scheme = "http"

        if ssl is True:
            self._scheme = "https"

        self._session.mount(self._scheme + '://', adapter)

        if proxies is None:
            self._proxies = {}
        else:
            self._proxies = proxies

        if cert:
            if not ssl:
                raise ValueError(
                    "Client certificate provided but ssl is disabled.")
            else:
                self._session.cert = cert

        self._baseurl = "{0}://{1}:{2}".format(
            self._scheme, self._host, self._port)

        self._headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def write(self, data, expected_response_code=204):
        """Write data to OpenTSDB.
        :param data: the data to be written
        :param expected_response_code: the expected response code of the write
            operation, defaults to 204
        :type expected_response_code: int
        :returns: True, if the write operation is successful
        :rtype: bool
        """
        headers = self._headers
        headers['Content-Type'] = 'application/json'

        self.request(
            url="api/put",
            method='POST',
            data=data,
            expected_response_code=expected_response_code,
            headers=headers)
        return True

    def request(
            self,
            url,
            method='GET',
            params=None,
            data=None,
            expected_response_code=200,
            headers=None):
        """Make a HTTP request to the OpenTSDB API.
        :param url: the path of the HTTP request
        :type url: str
        :param method: the HTTP method for the request, defaults to GET
        :type method: str
        :param params: additional parameters for the request, defaults to None
        :type params: dict
        :param data: the data of the request, defaults to None
        :type data: str
        :param expected_response_code: the expected response code of
            the request, defaults to 200
        :type expected_response_code: int
        :param headers: headers to add to the request
        :type headers: dict
        :returns: the response from the request
        :rtype: :class:`requests.Response`
        :raises OpenTSDBServerError: if the response code is any server error
            code (5xx)
        :raises OpenTSDBClientError: if the response code is not the
            same as `expected_response_code` and is not a server error code
        """
        url = "{0}/{1}".format(self._baseurl, url)

        if headers is None:
            headers = self._headers

        if params is None:
            params = {}

        if isinstance(data, (dict, list)):
            data = json.dumps(data)

        # Try to send the request more than once by default (see #103)
        retry = True
        _try = 0
        while retry:
            try:
                response = self._session.request(
                    method=method,
                    url=url,
                    auth=(self._username, self._password),
                    params=params,
                    data=data,
                    headers=headers,
                    proxies=self._proxies,
                    verify=self._verify_ssl,
                    timeout=self._timeout)
                break
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.HTTPError, requests.exceptions.Timeout):
                _try += 1
                if self._retries != 0:
                    retry = _try < self._retries
                if method == "POST":
                    time.sleep((2**_try) * random.random() / 100.0)
                if not retry:
                    raise
        # if there's not an error, there must have been a successful response
        if 500 <= response.status_code < 600:
            raise Exception(response.content)
        elif response.status_code == expected_response_code:
            return response
        else:
            raise Exception(response.content, response.status_code)
