# -*- coding: utf-8 -*-
"""Define the misc handler for InfluxDBClient test."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import socket


def get_free_ports(num_ports, ip='127.0.0.1'):
    """Determine free ports on provided interface.

    Get `num_ports` free/available ports on the interface linked to the `ip`
    :param int num_ports: The number of free ports to get
    :param str ip: The ip on which the ports have to be taken
    :return: a set of ports number
    """
    sock_ports = []
    ports = set()
    try:
        for _ in range(num_ports):
            sock = socket.socket()
            cur = [sock, -1]
            # append the socket directly,
            # so that it'll be also closed (no leaked resource)
            # in the finally here after.
            sock_ports.append(cur)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((ip, 0))
            cur[1] = sock.getsockname()[1]
    finally:
        for sock, port in sock_ports:
            sock.close()
            ports.add(port)
    assert num_ports == len(ports)
    return ports


def is_port_open(port, ip='127.0.0.1'):
    """Check if given TCP port is open for connection."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex((ip, port))
        if not result:
            sock.shutdown(socket.SHUT_RDWR)
        return result == 0
    finally:
        sock.close()
