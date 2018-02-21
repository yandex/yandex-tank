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
  Read options from yaml file.
  It is possible to set multiple configuration files by specifying the option serveral times.

  Default: ``./load.yaml``

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

Configuration files organized as yaml-files. Those are files
partitioned into named sections that contain 'name: value' records. 

Example:

.. code-block:: yaml

  phantom: 
    address: example.com:80
    load_profile:
      load_type: rps
      schedule: const(100,60s)
  autostop:
    autostop:
      - instances(80%,10)
      - time(1s,10s)

.. note:: 
  A common rule: options with the
  same name override those set before them (in the same file or not).

Default configuration files
--------------------------------

.. note::

  ``--no-rc`` command line option disables this behavior

Yandex.Tank reads all ``*.yaml`` from ``/etc/yandex-tank`` directory, then a personal config file ``~/.yandex-tank``.
So you can easily put your favourite settings in ``~/.yandex-tank``

Example: ``tank.artifacts_base_dir``, ``phantom.cache_dir``, ``console.info_panel_width``


Multiline options
--------------------------------

Use indent to show that a line is a continuation of a previous one:

.. code-block:: yaml

  autostop:
    autostop:
      - time(1,10)
      - http(404,1%,5s)
      - net(xx,1,30)

.. note::

  Ask Yandex.Tank developers to add multiline capability for options where you need it!*


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

Yandex.Tank sources are `here <https://github.com/yandex/yandex-tank>`_.

load.yaml example
================

.. code-block:: yaml

  phantom:
    address: "ya.ru:80"
    instances: 1000
    load_profile:
      load_type: rps
      schedule: const(1,30) line(1,1000,2m) const(1000,5m)
    header_http: "1.1"
    uris:
      - "/"
      - "/test"
      - "/test2"
    headers:
      - "[Host: www.ya.ru]"
      - "[Connection: close]"
  autostop:
    autostop:
      - http(5xx,10%,5s)

    
