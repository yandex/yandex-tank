Installation and Configuration
------------------------------

Installation
~~~~~~~~~~~~

You should add proper repositories on Debian-based environment.

For instance, add following repos to ``sources.list`` :

.. code-block:: bash

	deb http://ppa.launchpad.net/yandex-load/main/ubuntu precise main  
	deb-src http://ppa.launchpad.net/yandex-load/main/ubuntu precise main

or this way 

.. code-block:: bash
	
	apt-get install python-software-properties
	sudo add-apt-repository ppa:yandex-load/main

Then update package list and install ``yandex-load-tank-base`` package:

.. code-block:: bash

	sudo apt-get update && sudo apt-get install yandex-load-tank-base

For mild load tests (less then 1000rps) an average laptop with 64bit
Ubuntu (10.04/.../13.10) would be sufficient. The tank could be easily
used in virtual machine if queries aren't too heavy and load isn't too
big. Otherwise it is recommended to request a physical server or a more
capable virtual machine from your admin.

Firewall
~~~~~~~~

Before test execution, please, check service availability. If service is
running on server with IP x.x.x.x and listening for TCP port zz, try to
connect to it with ``telnet`` like this: ``telnet x.x.x.x zz`` If
everything OK, you'll see:

.. code-block:: bash

	$ telnet 203.0.113.1 80 
	Trying 203.0.113.1... 
	Connected to 203.0.113.1. Escape character is '^]'.

Otherwise if port is unreacheable:

.. code-block:: bash

	$ telnet 203.0.113.1 80 Trying 203.0.113.1... 
	telnet: Unable to connect to remote host: Connection timed out

(it's just an example, programs like ``nc/nmap/wget/curl`` could be used
as well, but not ping!) 

Routing
~~~~~~~~

OK, service is reachable, next thing
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

In second example you'd better find another closer located tank.

Tuning
~~~~~~

To achieve the top most performance you should tune the source server
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
	net.ipv4.tcp_max_orphans =
	65536 net.ipv4.tcp_fin_timeout = 10 
	net.ipv4.tcp_low_latency = 1
	net.ipv4.tcp_syncookies = 0
