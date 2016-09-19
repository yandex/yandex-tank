==================
Advanced usage
==================

Command line options
============================

Yandex.Tank has an obviously named executable ``yandex-tank``. 
Here are available command line options: 

:-h, --help:
  show command line options

:-c CONFIG, --config=CONFIG:
  Read options from INI file. 
  It is possible to set multiple INI files by specifying the option serveral times.

  Default: ``./load.ini``

:-i, --ignore-lock:
  Ignore lock files.

:-f, --fail-lock:
  Don't wait for lock file, quit if it's busy.

  Default behaviour is to wait for lock file to become free

:-l LOG, --log=LOG:
  Main log file location.

  Default: ``./tank.log``

:-m, --manual-start:
  Tank will prepare for test and wait for Enter key to start the test. 

:-n, --no-rc:
  Don't read ``/etc/yandex-tank/*.ini`` and ``~/.yandex-tank``

:-o OPTION, --option=OPTION:
  Set an option from command line. 
  Options set in cmd line override those have been set in configuration files. Multiple times for multiple options. 

  Format: ``<section>.<option>=value`` 

  Example: ``yandex-tank -o "console.short_only=1" --option="phantom.force_stepping=1"``

:-s SCHEDULED_START, --scheduled-start=SCHEDULED_START:
  Run test on specified time, date format YYYY-MM-DD hh:mm:ss or hh:mm:ss

:-q, --quiet:
  Only print WARNINGs and ERRORs to console.

:-v, --verbose:
  Print ALL, including DEBUG, messages to console. Chatty mode.


Add an ammo file name as a nameless parameter, e.g.:
``yandex-tank ammo.txt`` or ``yandex-tank ammo.gz``

Advanced configuration
============================

Configuration files organized as standard INI files. Those are files
partitioned into named sections that contain 'name=value' records. 

Example:
::

  [phantom] 
  address=example.com:80
  rps_schedule=const(100,60s)
  
  [autostop] 
  autostop=instances(80%,10)

.. note:: 
  A common rule: options with the
  same name override those set before them (in the same file or not).

Default configuration files
--------------------------------

If no ``--no-rc`` option passed, Yandex.Tank reads all ``*.ini`` from
``/etc/yandex-tank`` directory, then a personal config file ``~/.yandex-tank``. 
So you can easily put your favourite settings in ``~/.yandex-tank``

Example: ``tank.artifacts_base_dir``, ``phantom.cache_dir``, ``console.info_panel_width``

The ``DEFAULT`` section
--------------------------------

One can use a **magic** ``DEFAULT`` section, that contains global
options. Those options are in charge for every section: 

::

    [autostop] 
    autostop=time(1,10)
    
    [console] 
    short_only=1
    
    [meta] 
    job_name=ask 

is an equivalent for:

::

    [DEFAULT]
    autostop=time(1,10) 
    short_only=1 
    job_name=ask
    
.. note::
  Don't use global options wich have same name in different sections.


Multiline options
--------------------------------

Use indent to show that a line is a continuation of a previous one:

:: 

    [autostop]
    autostop=time(1,10)
      http(404,1%,5s)
      net(xx,1,30)

.. note::

  Ask Yandex.Tank developers to add multiline capability for options
  where you need it!*

Referencing one option to another
-----------------------------------

``%(optname)s`` gives you ability to reference from option to another. It helps to reduce duplication. 

Example:

::

    [DEFAULT]
    host=target12.load.net  
    
    [phantom]
    address=%(host)s
    port=8080
    
    [monitoring]
    default_target=%(host)s
    
    [shellexec]
    prepare=echo Target is %(host)s

Time units
--------------------------------

*Default* : milliseconds. 

Example:

::

  ``30000 == 30s`` 
  ``time(30000,120)`` is an equivalent to ``time(30s,2m)``

Time units encoding is as following: 

============= =======
Abbreviation  Meaning
============= =======
ms            millisecons
s             seconds
m             minutes
h             hours
============= =======

.. note::
  You can also  mix them: ``1h30m15s`` or ``2s15ms``. 

Shell-options
---------------------

Option value with backquotes is evaluated in shell.

Example:

::

  [meta]
  job_name=`pwd`

Artifacts
================

As a result Yandex.Tank produces some files (logs, results, configs
etc). Those files are placed with care to the **artifact directory**. An
option for that is ``artifacts_base_dir`` in the ``tank`` section. It is
recommended to set it to a convenient place, for example,
``~/yandex-tank-artifacts``; it would be easier to manage the artifacts
there.

Sources
================

Yandex.Tank sources are `here <https://github.com/yandex-load/yandex-tank>`_.

load.ini example
================

::

    ;Yandex.Tank config file
    [phantom]
    ;Target's address and port
    address=fe80::200:f8ff:fe21:67cf
    port=8080 
    instances=1000
    ;Load scheme
    rps_schedule=const(1,30) line(1,1000,2m) const(1000,5m) 
    ;  Headers and URIs for GET requests
    header_http = 1.1
    uris=/
        /test
        /test2
    headers=[Host: www.ya.ru]
            [Connection: close]
    [autostop] autostop = http(5xx,10%,5s)

    
