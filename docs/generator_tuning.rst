====================
Routing and firewall
====================

********
Firewall
********

Before test execution, please, check service availability. If service is
running on server with IP ``x.x.x.x`` and listening for TCP port ``zz``, try to
connect to it with ``telnet`` like this: ``telnet x.x.x.x zz`` If
everything OK, you'll see:

.. code-block:: bash

    $ telnet 203.0.113.1 80
    Trying 203.0.113.1...
    Connected to 203.0.113.1. Escape character is '^]'.

Otherwise if port is unreachable:

.. code-block:: bash

    $ telnet 203.0.113.1 80 Trying 203.0.113.1...
    telnet: Unable to connect to remote host: Connection timed out

.. note::
  it's just an example, programs like ``nc/nmap/wget/curl`` could be used as well, but not ping!)

*******
Routing
*******

OK, the service is reachable, next thing
you should know is how far Yandex.Tank is located from the service you'd
like to test. Heavy load can make switch to be unresponsible or to
reboot, or at least it may lead to network losses, so the test results
would be distorted. Be careful. Path estimation could be done by
execution of ``tracepath`` command or it analogs
(``tracert/traceroute``) on Yandex.Tank machine:

.. code-block:: bash

    $ tracepath 203.0.113.1
    1:  tank.example.com (203.0.113.1)            0.084ms pmtu 1450
    1:  target.load.example.com (203.0.113.1)           20.919ms reached
    1:  target.example.com (203.0.113.1)            0.128ms reached
    Resume: pmtu 1450 hops 1 back 64``
    Hops count = 1 means that tank and target are in closest location.

    $ tracepath 24.24.24.24
    1:  1.example.com (203.0.113.1)                 0.084ms pmtu 1450
    1:  2.example.com (203.0.113.1)          0.276ms
    1:  3.example.com (203.0.113.1)          0.411ms
    2:  4.example.com (203.0.113.1)                0.514ms
    3:  5.example.com (203.0.113.1)              10.690ms
    4:  6.example.com (203.0.113.1)                  0.831ms asymm  3
    5:  7.example.com (203.0.113.1)                 0.512ms
    6:  8.example.com (203.0.113.1)                 0.525ms asymm  5
    7:  no reply

In the second example you'd better find another closer located tank.

******
Tuning
******

To achieve top performance you should tune the source server
system limits:

.. code-block:: bash

    ulimit -n 30000

    net.ipv4.tcp_max_tw_buckets = 65536
    net.ipv4.tcp_tw_recycle = 1
    net.ipv4.tcp_tw_reuse = 0
    net.ipv4.tcp_max_syn_backlog = 131072
    net.ipv4.tcp_syn_retries = 3
    net.ipv4.tcp_synack_retries = 3
    net.ipv4.tcp_retries1 = 3
    net.ipv4.tcp_retries2 = 8
    net.ipv4.tcp_rmem = 16384 174760 349520
    net.ipv4.tcp_wmem = 16384 131072 262144
    net.ipv4.tcp_mem = 262144 524288 1048576
    net.ipv4.tcp_max_orphans = 65536
    net.ipv4.tcp_fin_timeout = 10
    net.ipv4.tcp_low_latency = 1
    net.ipv4.tcp_syncookies = 0
    net.netfilter.nf_conntrack_max = 1048576

.. note::
  ``tcp_tw_recycle`` has been removed as of Linux 4.12.
   
  This is because Linux now randomizes timestamps per connection and they do not monotonically increase. If you're using Linux 4.12 with machines using tcp_tw_recycle and TCP timestamps are turned on you will see dropped connections. You can of course disable it like so `echo 0 > /proc/sys/net/ipv4/tcp_timestamps` (temporarily, use sysctl.conf for permanent changes). 

  Details on 4.12 removing tcp_tw_recycle: 
  https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=4396e46187ca5070219b81773c4e65088dac50cc
