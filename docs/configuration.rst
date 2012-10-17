Advanced usage
--------------

Command line options
~~~~~~~~~~~~~~~~~~~~

There are three executables in Yandex.Tank package: ``yandex-tank``,
``yandex-tank-ab`` и ``yandex-tank-jmeter``. Last two of them just use
different king of load gen utilities, ``ab`` (Apache Benchmark) and
``jmeter`` (Apache JMeter), accordingly. Command line options are common
for all three: \* **-h, --help** - show command line options \* **-c
CONFIG, --config=CONFIG** - read options from INI file. It is possible
to set multiple INI files by specifying the option serveral times.
Default: ``./load.conf`` \* **-i, --ignore-lock** - ignore lock files \*
**-f, --fail-lock** - don't wait for lock file, quit if it's busy. The
default behaviour is to wait for lock file to become free. \* **-l LOG,
--log=LOG** - main log file location. Default: ``./tank.log`` \* **-n,
--no-rc** - don't read ``/etc/yandex-tank/*.ini`` and ``~/.yandex-tank``
\* **-o OPTION, --option=OPTION** - set an option from command line.
Options set in cmd line override those have been set in configuration
files. Multiple times for multiple options. Format:
``<section>.<option>=value`` Example:
``yandex-tank -o "console.short_only=1" --option="phantom.force_stepping=1"``
\* **-q, --quiet** - only print WARNINGs and ERRORs to console \* **-v,
--verbose** - print ALL messages to console. Chatty mode

Add an ammo file name as a nameless parameter, e.g.:
``yandex-tank ammo.txt``

Advanced configuration
~~~~~~~~~~~~~~~~~~~~~~

Configuration files organized as standard INI files. Those are files
partitioned into named sections that contain 'name=value' records. For
example: \`\`\` [phantom] address=target-mulca.targetnets.yandex.ru:8080
rps\_schedule=const(100,60s)

[autostop] autostop=instances(80%,10) \`\`\` A common rule: options with
same name override those set before them (in the same file or not).

Default configuration files
^^^^^^^^^^^^^^^^^^^^^^^^^^^

If no ``--no-rc`` option passed, Yandex.Tank reads all ``*.ini`` from
``/etc/yandex-tank`` directory, then a personal config file
``~/.yandex-tank``. So you can easily put your favourite settings in
``~/.yandex-tank``, for example, ``tank.artifacts_base_dir``,
``phantom.cache_dir``, ``console.info_panel_width``

The ``DEFAULT`` section
^^^^^^^^^^^^^^^^^^^^^^^

One can use a **magic** ``DEFAULT`` section, that contains global
options. Those options are in charge for every section: \`\`\`
[autostop] autostop=time(1,10)

[console] short\_only=1

[aggregator] time\_periods=10 20 30 100

[meta] job\_name=ask ``is an equivalent for:`` [DEFAULT]
autostop=time(1,10) short\_only=1 time\_periods=10 20 30 100
job\_name=ask \`\`\` !!! Don't use global options wich have same name in
different sections.

Multiline options
^^^^^^^^^^^^^^^^^

Use indent to show that a line is a continuation of a previous one:
``[autostop] autostop=time(1,10)   http(404,1%,5s)   net(xx,1,30)``
**Ask Yandex.Tank developers to add multiline capability for options
where you need it!**

Time units
^^^^^^^^^^

Time units encoding is as following: \* ``ms`` = millisecons \* ``s`` =
seconds \* ``m`` = minutes \* ``h`` = hours Default time unit is a
millisecond. For example, ``30000 == 30s``

``time(30000,120)`` is an equivalent to ``time(30s,2m)`` You can also
mix them: ``1h30m15s`` or ``2s15ms``

Artifacts
~~~~~~~~~

As a result Yandex.Tank produces some files (logs, results, configs
etc). Those files are placed with care to the **artifact directory**. An
option for that is ``artifacts_base_dir`` in the ``tank`` section. It is
recommended to set it to a convinient place, for example,
``~/yandex-tank-artifacts``, it would be easier to manage the artifacts
there.

Modules
~~~~~~~

Phantom
^^^^^^^

Load generator module that uses phantom utility.

Options
'''''''

INI file section: **[phantom]**

Basic options: \* **ammofile** - ammo file path (ammo file is a file
containing requests that are to be sent to a server) \*
**rps\_schedule** - load schedule in terms of RPS \* **instances** - max
number of instances (concurrent requests) \* **instances\_schedule** -
load schedule in terms of number of instances \* **loop** - number of
times requests from ammo file are repeated in loop \* **autocases** -
enable marking requests automatically (1 -- enable, 0 -- disable)

Additional options: \* **writelog** - enable verbose request/response
logging. Available options: 0 - disable, all - all messages,
proto\_warning - 4хх+5хх+network errors, proto\_error - 5хх+network
errors. Default: 0 \* **ssl** - enable SSL, 1 - enable, 0 - disable,
default: 0 \* **address** - address of service to test. May contain port
divided by colon for IPv4 or DN. For DN, DNS request is performed, and
then reverse-DNS request to verify the correctness of name. Default:
``127.0.0.1`` \* **port** - port of service to test. Default: ``80`` \*
**gatling\_ip** - use multiple source addresses. List, divided by
spaces. \* **tank\_type** - protocol type: http, none (raw TCP).
Default: ``http``

URI-style options: \* **uris** - URI list, multiline option. \*
**headers** - HTTP headers list in the following form:
``[Header: value]``, multiline option. \* **header\_http** - HTTP
version, default: ``1.1``

stpd-file cache options: \* **use\_caching** - enable cache, default:
``1`` \* **cache\_dir** - cache files directory, default: base artifacts
directory. \* **force\_stepping** - force stpd file generation, default:
``0``

Advanced options: \* **phantom\_path** - phantom utility path, default:
``phantom`` \* **phantom\_modules\_path** - phantom modules path,
default:``/usr/lib/phantom`` \* **config** - use given (in this option)
config file for phantom instead of generated. \* **phout\_file** -
import this phout instead of launching phantom (import phantom results)
\* **stpd\_file** - use this stpd-file instead of generated \*
**threads** - phantom thread count, default:
``<processor cores count>/2 + 1``

http-module tuning options: \* **phantom\_http\_line** \*
**phantom\_http\_field\_num** \* **phantom\_http\_field** \*
**phantom\_http\_entity**

Artifacts
'''''''''

-  **phantom\_*.conf*\* - generated configuration files
-  **phout\_*.log*\* - raw results file
-  **phantom\_stat\_*.log*\* - phantom statistics, aggregated by seconds
-  **answ\_*.log*\* - detailed request/response log
-  **phantom\_*.log*\* - internal phantom log

Auto-stop
^^^^^^^^^

The Auto-stop module gets the data from the aggregator and passes them
to the criteria-objects that decide if we should stop the test.

INI file section: **[autostop]**

Options
'''''''

-  **autostop** - criteria list divided by spaces, in following format:
   ``type(parameters)``

Available criteria types: \* **time** - stop the test if average
response time is higher then specified for as long as the time period
specified. E.g.: ``time(1s500ms, 30s) time(50,15)`` \* **http** - stop
the test if the count of responses in last time period (specified) with
HTTP codes fitting the mask is larger then the specified absolute or
relative value. Examples: ``http(404,10,15) http(5xx, 10%, 1m)`` \*
**net** - like ``http``, but for network codes. Use ``xx`` for all
non-zero codes. \* **quantile** - stop the test if the specified
percentile is larger then specified level for as long as the time period
specified. Available percentile values: 25, 50, 75, 80, 90, 95, 98, 99,
100. Example: ``quantile (95,100ms,10s)`` \* **instances** - available
when phantom module is included. Stop the test if instance count is
larger then specified value. Example:
``instances(80%, 30) instances(50,1m)`` \* **total\_time** — like
``time``, but accumulate for all time period (responses that fit may not
be one-after-another, but only lay into specified time period). Example:
``total_time(300ms, 70%, 3s)`` \* **total\_http** — like ``http``, but
accumulated. See ``total_time``. Example:
``total_http(5xx,10%,10s) total_http(3xx,40%,10s)`` \* **total\_net** —
like ``net``, but accumulated. See ``total_time``. Example:
``total_net(79,10%,10s) total_net(11x,50%,15s)`` \* **negative\_http** —
``http``, inversed. Stop if there are not enough responses that fit the
specified mask. Use to be shure that server responds 200. Example:
``negative_http(2xx,10%,10s)``

Console on-line screen
^^^^^^^^^^^^^^^^^^^^^^

Shows usefull information in console while running the test

INI file section: **[console]**

Options
'''''''

-  **short\_only** - show only one-line summary instead of full-screen
   (usefull for scripting), default: 0 (disable)
-  **info\_panel\_width** - relative right-panel width in percents,
   default: 33

Aggregator
^^^^^^^^^^

The aggregator module is responsible for aggregation of data received
from different kind of modules and transmitting that aggregated data to
consumer modules (Console screen module is an example of such kind). INI
file section: **[aggregator]** ##### options: \* **time\_periods** -
time intervals list divided by zero. Default:
``1ms 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s 1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s``

ShellExec
^^^^^^^^^

The ShellExec module executes the shell-scripts (hooks) on different
stages of test, for example, you could start/stop some services just
before/after the test. Every hook must return 0 as an exit code or the
test is terminated. Hook's stdout will be written to DEBUG, stderr will
be WARNINGs.

INI file section: **[shellexec]**

Options:
''''''''

-  **prepare** - the script to run on prepare stage
-  **start** - the script to run on start stage
-  **poll** - the script to run every second while the test is running
-  **end** - the script to run on end stage
-  **postprocess** - the script to run on postprocess stage

JMeter
^^^^^^

JMeter load generator module.

INI file section: **[jmeter]**

Options
'''''''

-  !!mandatory option!! **jmx** - test plan file
-  **args** - JMeter command line parameters
-  **jmeter\_path** - JMeter path, default: ``jmeter``

Artifacts
'''''''''

-  **\_original\_jmx.jmx>** - original test plan file
-  **modified\_*.jmx*\* - modified test plan with results output section
-  **jmeter\_*.jtl*\* - JMeter results
-  **jmeter\_*.log*\* - JMeter log

AB
^^

Apache Benchmark load generator module. As the ab utility writes results
to file only after the test is finished, Yandex.Tank is unable to show
the on-line statistics for the tests with ab. The data are reviewed
after the test.

INI file section: **[ab]** ##### Options \* **url** - requested URL,
default: ``http:**localhost/`` \* **requests** - total request count,
default: 100 \* **concurrency** - number of concurrent requests: 1 \*
**options** - ab command line options

Artifacts
'''''''''

-  **ab\_*.log*\* - request log with response times

Tips&Tricks
^^^^^^^^^^^

Shows tips and tricks in fullscreen console. **If you have any
tips&tricks, tell the developers about them**

INI-file section: **[tips]** ##### Options \* **disable** - disable tips
and tricks, default: don't (0)

Sources
~~~~~~~

Yandex.Tank sources ((https://github.com/yandex-load/yandex-tank here)).

load.conf.example
~~~~~~~~~~~~~~~~~

::

    # Yandex.Tank config file
    address=23.23.23.23:443 #Target's address and port
    load = const (10,10m) #Load scheme
    #  Headers and URIs for GET requests
    header_http = 1.1
    header = [Host: www.target.example.com]
    header = [Connection: close]
    uri = /
    #ssl=1
    #autostop = http(5xx,100%,1)
    #instances=10
    #writelog=1
    #time_periods = 10 45 50 100 150 300 500 1s 1500 2s 3s 10s # the last value - 10s is considered as connect timeout.
    #instances_schedule = line (1,1000,10m)
    #tank_type=2
    #gatling_ip = 141.8.153.82 141.8.153.81

