=========
Tutorials
=========

So, you've installed Yandex.Tank to a proper machine, it is close to target,
access is permitted and server is tuned. How to make a test?

.. note::

  This guide is for ``phantom`` load generator.

Create a file on a server with Yandex.Tank: **load.yaml**

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80 # [Target's address]:[target's port]
    uris:
      - /
    load_profile:
      load_type: rps # schedule load by defining requests per second
      schedule: line(1, 10, 10m) # starting from 1rps growing linearly to 10rps during 10 minutes
  console:
    enabled: true # enable console output
  telegraf:
    enabled: false # let's disable telegraf monitoring for the first time

And run:
``$ yandex-tank -c load.yaml``

------------

``phantom`` have 3 primitives for describing load scheme:

 1. ``step (a,b,step,dur)`` makes stepped load, where a,b are start/end load values, step - increment value, dur - step duration.

  Examples:
   * ``step(25, 5, 5, 60)`` - stepped load from 25 to 5 rps, with 5 rps steps, step duration 60s.
   * ``step(5, 25, 5, 60)`` - stepped load from 5 to 25 rps, with 5 rps steps, step duration 60s

 2. ``line (a,b,dur)`` makes linear load, where ``a,b`` are start/end load, ``dur`` - the time for linear load increase from a to b.

  Examples:
   * ``line(10, 1, 10m)`` - linear load from 10 to 1 rps, duration - 10 minutes
   * ``line(1, 10, 10m)`` - linear load from 1 to 10 rps, duration - 10 minutes

 3. ``const (load,dur)`` makes constant load. ``load`` - rps amount, ``dur`` - load duration.

  Examples:
   * ``const(10,10m)`` - constant load for 10 rps for 10 minutes.
   * ``const(0, 10)`` - 0 rps for 10 seconds, in fact 10s pause in a test.

.. note::
 You can set fractional load like this:
  ``line(1.1, 2.5, 10)`` - from 1.1rps to 2.5 for 10 seconds.

.. note::
 ``step`` and ``line`` could be used with increasing and decreasing intensity:


You can specify complex load schemes using those primitives.

Example:
  ``schedule: line(1, 10, 10m) const(10,10m)``
  
  linear load from 1 to 10rps during 10 minutes, then 10 minutes of 10rps constant load.

Time duration could be defined in seconds, minutes (m) and hours (h).
For example: ``27h103m645``

For a test with constant load at 10rps for 10 minutes, ``load.yaml`` should
have following lines:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80 # [Target's address]:[target's port]
    uris:
      - /uri1
      - /uri2
    load_profile:
      load_type: rps # schedule load by defining requests per second
      schedule: const(10, 10m) # starting from 1rps growing linearly to 10rps during 10 minutes
  console:
    enabled: true # enable console output
  telegraf:
    enabled: false # let's disable telegraf monitoring for the first time


Preparing requests
==================

There are several ways to set up requests: 
 * Access mode 
 * URI-style
 * URI+POST
 * request-style. 

.. note:: 
  Request-style is default ammo type.

.. note::
  Regardless of the chosen format, resulted file with requests could be gzipped - tank supports archived ammo files.

To specify external ammo file use ``ammofile`` option. 

.. note::
  You can specify URL to ammofile, http(s). Small ammofiles (~<100MB) will be downloaded as is,
  to directory ``/tmp/<hash>``, large files will be read from stream.

.. note::

  If ammo type is uri-style or request-style, tank will try to guess it.
  Use ``ammo_type`` option to explicitly specify ammo format. Don't forget to change ``ammo_type`` option
  if you switch format of your ammo, otherwise you might get errors.

  Example:
  ::
      
    phantom:
      address: 203.0.113.1:80
      ammofile: https://yourhost.tld/path/to/ammofile.txt


URI-style, URIs in load.yaml
----------------------------

YAML-file configuration: Don't specify ``ammo_type`` explicitly for this type of ammo.

Update configuration file with HTTP headers and URIs:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: rps
      schedule: line(1, 10, 10m)
    header_http: "1.1"
    headers:
      - "[Host: www.target.example.com]"
      - "[Connection: close]"
    uris:
      - "/uri1"
      - "/buy"
      - "/sdfg?sdf=rwerf"
      - "/sdfbv/swdfvs/ssfsf"
  console:
    enabled: true
  telegraf:
    enabled: false

Parameter ``uris`` contains uri, which should be used for requests generation.

.. note::

  Pay attention to the sample above, because whitespaces in multiline ``uris`` and ``headers`` options are important.

URI-style, URIs in file
-----------------------

YAML-file configuration: ``ammo_type: uri``

Create a file with declared requests: ``ammo.txt``

::

  [Connection: close] 
  [Host: target.example.com] 
  [Cookie: None] 
  /?drg tag1
  / 
  /buy tag2 
  [Cookie: test]
  /buy/?rt=0&station_to=7&station_from=9

File consists of list of URIs and headers to be added to every request defined below.
Every URI must begin from a new line, with leading ``/``.
Each line that begins from ``[`` is considered as a header.
Headers could be (re)defined in the middle of URIs, as in sample above. 

Example:
  Request ``/buy/?rt=0&station_to=7&station_from=9`` will be sent with ``Cookie: test``, not ``Cookie: None``. 

Request may be marked by tag, you can specify it with whitespace following URI.

URI+POST-style
--------------

YAML-file configuration: ``ammo_type: uripost``

Create a file with declared requests: ``ammo.txt``

::

  [Host: example.org]
  [Connection: close] 
  [User-Agent: Tank]  
  5 /route/?rll=50.262025%2C53.276083~50.056015%2C53.495561&origin=1&simplify=1
  class
  10 /route/?rll=50.262025%2C53.276083~50.056015%2C53.495561&origin=1&simplify=1
  hello!clas
  7 /route/?rll=37.565147%2C55.695758~37.412796%2C55.691454&origin=1&simplify=1
  uripost

File begins with optional lines [...], that contain headers which will
be added to every request. After that section there is a list of URIs and POST bodies.
Each URI line begins with a number which is the size of the following POST body.


Request-style
-------------

YAML-file configuration: ``ammo_type: phantom``

Full requests listed in a separate file. For more complex
requests, like POST, you'll have to create a special file. File format
is:

::

  [size_of_request] [tag]\n
  [request_headers]
  [body_of_request]\r\n
  [size_of_request2] [tag2]\n
  [request2_headers]
  [body_of_request2]\r\n


where ``size_of_request`` – request size in bytes. '\r\n' symbols after
``body`` are ignored and not sent anywhere, but it is required to
include them in a file after each request. Pay attention to the sample above
because '\r' symbols are strictly required. 

.. note:: 

  Parameter ``ammo_type`` is unnecessary, request-style is default ammo type.

=======

**sample GET requests (null body)**

::
  
  73 good
  GET / HTTP/1.0
  Host: xxx.tanks.example.com
  User-Agent: xxx (shell 1)
  
  77 bad
  GET /abra HTTP/1.0
  Host: xxx.tanks.example.com
  User-Agent: xxx (shell 1)
  
  78 unknown
  GET /ab ra HTTP/1.0
  Host: xxx.tanks.example.com
  User-Agent: xxx (shell 1)

------------


**sample POST requests (binary data)**

::

  904
  POST /upload/2 HTTP/1.0
  Content-Length: 801
  Host: xxxxxxxxx.dev.example.com
  User-Agent: xxx (shell 1)

  ^.^........W.j^1^.^.^.²..^^.i.^B.P..-!(.l/Y..V^.      ...L?...S'NR.^^vm...3Gg@s...d'.\^.5N.$NF^,.Z^.aTE^.
  ._.[..k#L^ƨ`\RE.J.<.!,.q5.F^՚iΔĬq..^6..P..тH.`..i2
  .".uuzs^^F2...Rh.&.U.^^..J.P@.A......x..lǝy^?.u.p{4..g...m.,..R^.^.^......].^^.^J...p.ifTF0<.s.9V.o5<..%!6ļS.ƐǢ..㱋....C^&.....^.^y...v]^YT.1.#K.ibc...^.26...   ..7.
  b.$...j6.٨f...W.R7.^1.3....K`%.&^..d..{{      l0..^\..^X.g.^.r.(!.^^...4.1.$\ .%.8$(.n&..^^q.,.Q..^.D^.].^.R9.kE.^.$^.I..<..B^..^.h^^C.^E.|....3o^.@..Z.^.s.$[v.
  527
  POST /upload/3 HTTP/1.0
  Content-Length: 424
  Host: xxxxxxxxx.dev.example.com
  User-Agent: xxx (shell 1)

  ^.^........QMO.0^.++^zJw.ر^$^.^Ѣ.^V.J....vM.8r&.T+...{@pk%~C.G../z顲^.7....l...-.^W"cR..... .&^?u.U^^.^.....{^.^..8.^.^.I.EĂ.p...'^.3.Tq..@R8....RAiBU..1.Bd*".7+.
  .Ol.j=^.3..n....wp..,Wg.y^.T..~^..

------------

**sample POST multipart:**

::

  533
  POST /updateShopStatus? HTTP/1.0
  User-Agent: xxx/1.2.3
  Host: xxxxxxxxx.dev.example.com
  Keep-Alive: 300
  Content-Type: multipart/form-data; boundary=AGHTUNG
  Content-Length:334
  Connection: Close
  
  --AGHTUNG
  Content-Disposition: form-data; name="host"
  
  load-test-shop-updatestatus.ru
  --AGHTUNG
  Content-Disposition: form-data; name="user_id"
  
  1
  --AGHTUNG
  Content-Disposition: form-data; name="wsw-fields"
  
  <wsw-fields><wsw-field name="moderate-code"><wsw-value>disable</wsw-value></wsw-field></wsw-fields>
  --AGHTUNG--

sample ammo generators you may find on the :doc:`ammo_generators` page.
  


Run Test!
=========

1. Request specs in load.yaml -- run as ``yandex-tank -c load.yaml``
2. Request specs in ammo.txt -- run as ``yandex-tank -c load.yaml ammo.txt``

Yandex.Tank detects requests format and generates ultimate requests
versions.

``yandex-tank`` here is an executable file name of Yandex.Tank.

If Yandex.Tank has been installed properly and configuration file is
correct, the load will be given in next few seconds.

Results
=======

During test execution you'll see HTTP and net errors, answer times
distribution, progressbar and other interesting data. At the same time
file ``phout.txt`` is being written, which could be analyzed later.

If you need more human-readable report, you can try Report plugin,
You can found it `here <https://github.com/yandex-load/yatank-online>`_

If you need to upload results to an external storage, such as Graphite or InfluxDB, you can use one of existing artifacts uploading modules :doc:`core_and_modules`

Tags
====

Requests could be grouped and marked by some tag. 

Example:
::

  73 good 
  GET / HTTP/1.0 
  Host: xxx.tanks.example.com 
  User-Agent: xxx (shell 1)
  
  77 bad 
  GET /abra HTTP/1.0 
  Host: xxx.tanks.example.com 
  User-Agent: xxx (shell 1)
  
  75 unknown 
  GET /ab HTTP/1.0 
  Host: xxx.tanks.example.com 
  User-Agent: xxx (shell 1)

``good``, ``bad`` and ``unknown`` here are the tags.

.. note::

  **RESTRICTION: utf-8 symbols only**

SSL
===

To activate SSL add ``phantom: {ssl: true}`` to ``load.yaml``. 
Now, our basic config looks like that:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:443
      load_profile:
        load_type: rps
        schedule: line(1, 10, 10m)
    ssl: true

.. note::

  Do not forget to specify ssl port to `address`. Otherwise, you might get 'protocol errors'.

Autostop 
========

Autostop is an ability to automatically halt test execution
if some conditions are reached. 

HTTP and Net codes conditions 
-----------------------------

There is an option to define specific codes (404,503,100) as well as code
groups (3xx, 5xx, xx). Also you can define relative threshold (percent
from the whole amount of answer per second) or absolute (amount of
answers with specified code per second). 

Examples:

  ``autostop: http(4xx,25%,10)`` – stop test, if amount of 4xx http codes in every second of last 10s period exceeds 25% of answers (relative threshold).

  ``autostop: net(101,25,10)`` – stop test, if amount of 101 net-codes in every second of last 10s period is more than 25 (absolute threshold).

  ``autostop: net(xx,25,10)`` – stop test, if amount of non-zero net-codes in every second of last 10s period is more than 25 (absolute threshold).

Average time conditions
-----------------------

Example: 
  ``autostop: time(1500,15)`` – stops test, if average answer time exceeds 1500ms.

So, if we want to stop test when all answers in 1 second period are 5xx plus some network and timing factors - add autostop line to load.yaml:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: rps
      schedule: line(1, 10, 10m)
  autostop:
    autostop:
      - time(1s,10s)
      - http(5xx,100%,1s)
      - net(xx,1,30)

Logging
=======

Looking into target's answers is quite useful in debugging. For doing
that use parameter `writelog <http://yandextank.readthedocs.io/en/latest/config_reference.html#writelog-string>`_, e.g. add ``phantom: {writelog: all}`` to ``load.yaml`` to log all messages.

.. note::
  Writing answers on high load leads to intensive disk i/o 
  usage and can affect test accuracy.** 

Log format: 

::

  <metrics> 
  <body_request>
  <body_answer>

Where metrics are:

``size_in size_out response_time(interval_real) interval_event net_code``
(request size, answer size, response time, time to wait for response
from the server, answer network code) 

Example: 

::

  user@tank:~$ head answ_*.txt 
  553 572 8056 8043 0
  GET /create-issue HTTP/1.1
  Host: target.yandex.net
  User-Agent: tank
  Accept: */*
  Connection: close
  
  
  HTTP/1.1 200 OK
  Content-Type: application/javascript;charset=UTF-8

For ``load.yaml`` like this:
  
.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: rps
      schedule: line(1, 10, 10m)
    writelog: all
  autostop:
    autostop:
      - time(1,10)
      - http(5xx,100%,1s)
      - net(xx,1,30)

Results in phout
================

phout.txt - is a per-request log. It could be used for service behaviour
analysis (Excel/gnuplot/etc) It has following fields:
``time, tag, interval_real, connect_time, send_time, latency, receive_time, interval_event, size_out, size_in, net_code proto_code``

Phout example:

::

  1326453006.582          1510    934     52      384     140     1249    37      478     0       404
  1326453006.582   others       1301    674     58      499     70      1116    37      478     0       404
  1326453006.587   heavy       377     76      33      178     90      180     37      478     0       404
  1326453006.587          294     47      27      146     74      147     37      478     0       404
  1326453006.588          345     75      29      166     75      169     37      478     0       404
  1326453006.590          276     72      28      119     57      121     53      476     0       404
  1326453006.593          255     62      27      131     35      134     37      478     0       404
  1326453006.594          304     50      30      147     77      149     37      478     0       404
  1326453006.596          317     53      33      158     73      161     37      478     0       404
  1326453006.598          257     58      32      106     61      110     37      478     0       404
  1326453006.602          315     59      27      160     69      161     37      478     0       404
  1326453006.603          256     59      33      107     57      110     53      476     0       404
  1326453006.605          241     53      26      130     32      131     37      478     0       404

.. note::
  contents of phout depends on phantom version installed on your Yandex.Tank system.

net codes are system codes from errno.h, on most Debian-based systems those are:

::

  1 EPERM	Operation not permitted
  2	ENOENT	No such file or directory
  3	ESRCH	No such process
  4	EINTR	Interrupted system call
  5	EIO	Input/output error
  6	ENXIO	No such device or address
  7	E2BIG	Argument list too long
  8	ENOEXEC	Exec format error
  9	EBADF	Bad file descriptor
  10	ECHILD	No child processes
  11	EAGAIN	Resource temporarily unavailable
  12	ENOMEM	Cannot allocate memory
  13	EACCES	Permission denied
  14	EFAULT	Bad address
  15	ENOTBLK	Block device required
  16	EBUSY	Device or resource busy
  17	EEXIST	File exists
  18	EXDEV	Invalid cross-device link
  19	ENODEV	No such device
  20	ENOTDIR	Not a directory
  21	EISDIR	Is a directory
  22	EINVAL	Invalid argument
  23	ENFILE	Too many open files in system
  24	EMFILE	Too many open files
  25	ENOTTY	Inappropriate ioctl for device
  26	ETXTBSY	Text file busy
  27	EFBIG	File too large
  28	ENOSPC	No space left on device
  29	ESPIPE	Illegal seek
  30	EROFS	Read-only file system
  31	EMLINK	Too many links
  32	EPIPE	Broken pipe
  33	EDOM	Numerical argument out of domain
  34	ERANGE	Numerical result out of range
  35	EDEADLOCK	Resource deadlock avoided
  36	ENAMETOOLONG	File name too long
  37	ENOLCK	No locks available
  38	ENOSYS	Function not implemented
  39	ENOTEMPTY	Directory not empty
  40	ELOOP	Too many levels of symbolic links
  42	ENOMSG	No message of desired type
  43	EIDRM	Identifier removed
  44	ECHRNG	Channel number out of range
  45	EL2NSYNC	Level 2 not synchronized
  46	EL3HLT	Level 3 halted
  47	EL3RST	Level 3 reset
  48	ELNRNG	Link number out of range
  49	EUNATCH	Protocol driver not attached
  50	ENOCSI	No CSI structure available
  51	EL2HLT	Level 2 halted
  52	EBADE	Invalid exchange
  53	EBADR	Invalid request descriptor
  54	EXFULL	Exchange full
  55	ENOANO	No anode
  56	EBADRQC	Invalid request code
  57	EBADSLT	Invalid slot
  59	EBFONT	Bad font file format
  60	ENOSTR	Device not a stream
  61	ENODATA	No data available
  62	ETIME	Timer expired
  63	ENOSR	Out of streams resources
  64	ENONET	Machine is not on the network
  65	ENOPKG	Package not installed
  66	EREMOTE	Object is remote
  67	ENOLINK	Link has been severed
  68	EADV	Advertise error
  69	ESRMNT	Srmount error
  70	ECOMM	Communication error on send
  71	EPROTO	Protocol error
  72	EMULTIHOP	Multihop attempted
  73	EDOTDOT	RFS specific error
  74	EBADMSG	Bad message
  75	EOVERFLOW	Value too large for defined data type
  76	ENOTUNIQ	Name not unique on network
  77	EBADFD	File descriptor in bad state
  78	EREMCHG	Remote address changed
  79	ELIBACC	Can not access a needed shared library
  80	ELIBBAD	Accessing a corrupted shared library
  81	ELIBSCN	.lib section in a.out corrupted
  82	ELIBMAX	Attempting to link in too many shared libraries
  83	ELIBEXEC	Cannot exec a shared library directly
  84	EILSEQ	Invalid or incomplete multibyte or wide character
  85	ERESTART	Interrupted system call should be restarted
  86	ESTRPIPE	Streams pipe error
  87	EUSERS	Too many users
  88	ENOTSOCK	Socket operation on non-socket
  89	EDESTADDRREQ	Destination address required
  90	EMSGSIZE	Message too long
  91	EPROTOTYPE	Protocol wrong type for socket
  92	ENOPROTOOPT	Protocol not available
  93	EPROTONOSUPPORT	Protocol not supported
  94	ESOCKTNOSUPPORT	Socket type not supported
  95	ENOTSUP	Operation not supported
  96	EPFNOSUPPORT	Protocol family not supported
  97	EAFNOSUPPORT	Address family not supported by protocol
  98	EADDRINUSE	Address already in use
  99	EADDRNOTAVAIL	Cannot assign requested address
  100	ENETDOWN	Network is down
  101	ENETUNREACH	Network is unreachable
  102	ENETRESET	Network dropped connection on reset
  103	ECONNABORTED	Software caused connection abort
  104	ECONNRESET	Connection reset by peer
  105	ENOBUFS	No buffer space available
  106	EISCONN	Transport endpoint is already connected
  107	ENOTCONN	Transport endpoint is not connected
  108	ESHUTDOWN	Cannot send after transport endpoint shutdown
  109	ETOOMANYREFS	Too many references: cannot splice
  110	ETIMEDOUT	Connection timed out
  111	ECONNREFUSED	Connection refused
  112	EHOSTDOWN	Host is down
  113	EHOSTUNREACH	No route to host
  114	EALREADY	Operation already in progress
  115	EINPROGRESS	Operation now in progress
  116	ESTALE	Stale file handle
  117	EUCLEAN	Structure needs cleaning
  118	ENOTNAM	Not a XENIX named type file
  119	ENAVAIL	No XENIX semaphores available
  120	EISNAM	Is a named type file
  121	EREMOTEIO	Remote I/O error
  122	EDQUOT	Disk quota exceeded

Graph and statistics
====================

Use `Report plugin <https://github.com/yandex-load/yatank-online>`_ 
OR
use your favorite stats packet, R, for example.


Thread limit
============

``instances: N`` in ``load.yaml`` limits number of simultanious
connections (threads). 

Example with 10 threads limit:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: rps
      schedule: line(1, 10, 10m)
    instances: 10

Dynamic thread limit
====================

You can specify ``load_type: instances`` instead of 'rps' to schedule a number of active instances
which generate as much rps as they manage to.
Bear in mind that active instances number cannot be decreased
and final number of them must be equal to ``instances`` parameter value.

Example:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: instances
      schedule: line(1,10,10m)
    instances: 10
    loop: 10000 # don't stop when the end of ammo is reached but loop it 10000 times

.. note::
  When using ``load_type: instances`` you should specify how many loops of
  ammo you want to generate because tank can't find out from the schedule
  how many ammo do you need

Custom stateless protocol
=========================

In necessity of testing stateless HTTP-like protocol, Yandex.Tank's HTTP
parser could be switched off, providing ability to generate load with
any data, receiving any answer in return. To do that use
`tank_type <http://yandextank.readthedocs.io/en/latest/config_reference.html#tank-type-string>`_ parameter:

.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: rps
      schedule: line(1, 10, 10m)
    instances: 10
    tank_type: none

.. note::

  **Indispensable condition: Connection close must be initiated by remote side**

Gatling 
=======

If server with Yandex.Tank have several IPs, they may be
used to avoid outcome port shortage. Use ``gatling_ip`` parameter for
that. load.yaml:


.. code-block:: yaml

  phantom:
    address: 203.0.113.1:80
    load_profile:
      load_type: rps
      schedule: line(1, 10, 10m)
    instances: 10
    gatling_ip: IP1 IP2
