Advanced usage
--------------

Command line options
~~~~~~~~~~~~~~~~~~~~

There are three executables in Yandex.Tank package: ``yandex-tank``,
``yandex-tank-ab`` and ``yandex-tank-jmeter``. Last two of them just use
different kind of load generation utilities, ``ab`` (Apache Benchmark) and
``jmeter`` (Apache JMeter), accordingly. Command line options are common
for all three.

- **-h, --help** - show command line options 
- **-c CONFIG, --config=CONFIG** - read options from INI file. It is possible to set multiple INI files by specifying the option serveral times. Default: ``./load.ini`` 
- **-i, --ignore-lock** - ignore lock files 
- **-f, --fail-lock** - don't wait for lock file, quit if it's busy. The default behaviour is to wait for lock file to become free. 
- **-l LOG, --log=LOG** - main log file location. Default: ``./tank.log``
- **-n, --no-rc** - don't read ``/etc/yandex-tank/*.ini`` and ``~/.yandex-tank``
- **-o OPTION, --option=OPTION** - set an option from command line. Options set in cmd line override those have been set in configuration files. Multiple times for multiple options. Format: ``<section>.<option>=value`` Example: ``yandex-tank -o "console.short_only=1" --option="phantom.force_stepping=1"``
- **-s SCHEDULED_START, --scheduled-start=SCHEDULED_START** - run test on specified time, date format YYYY-MM-DD hh:mm:ss or hh:mm:ss
- **-q, --quiet** - only print WARNINGs and ERRORs to console 
- **-v, --verbose** - print ALL messages to console. Chatty mode


Add an ammo file name as a nameless parameter, e.g.:
``yandex-tank ammo.txt``

Advanced configuration
~~~~~~~~~~~~~~~~~~~~~~

Configuration files organized as standard INI files. Those are files
partitioned into named sections that contain 'name=value' records. For
example: 

::

    [phantom] 
    address=example.com:80
    rps_schedule=const(100,60s)
    
    [autostop] 
    autostop=instances(80%,10)

A common rule: options with the
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
options. Those options are in charge for every section: 

::

    [autostop] 
    autostop=time(1,10)
    
    [console] 
    short_only=1
    
    [aggregator] 
    time_periods=10 20 30 100
    
    [meta] 
    job_name=ask 

is an equivalent for:

::

    [DEFAULT]
    autostop=time(1,10) 
    short_only=1 
    time_periods=10 20 30 100
    job_name=ask
    
!!! Don't use global options wich have same name in different sections.


Multiline options
^^^^^^^^^^^^^^^^^

Use indent to show that a line is a continuation of a previous one:

:: 

    [autostop]
    autostop=time(1,10)
      http(404,1%,5s)
      net(xx,1,30)
*Ask Yandex.Tank developers to add multiline capability for options
where you need it!*

Referencing one option to another
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``%(optname)s`` gives you ability to reference from option to another. It helps to reduce duplication. Example:

::

    [DEFAULT]
    host=target12.load.net  
  
    [phantom]
    address=%(host)s:8080
    
    [monitoring]
    default_target=%(host)s
    
    [shellexec]
    prepare=echo Target is %(host)s

Time units
^^^^^^^^^^

Time units encoding is as following: 

* ``ms`` = millisecons \

* ``s`` = seconds \

* ``m`` = minutes \

* ``h`` = hours 

Default time unit is a millisecond. For example, ``30000 == 30s``
``time(30000,120)`` is an equivalent to ``time(30s,2m)`` You can also
mix them: ``1h30m15s`` or ``2s15ms``. If somewhere it is not supported - report a bug, please.

Shell-options
^^^^^^^^^^

Option value with backquotes is evaluated in shell, for example

::

 [meta]
 job_name=`pwd`

Artifacts
~~~~~~~~~

As a result Yandex.Tank produces some files (logs, results, configs
etc). Those files are placed with care to the **artifact directory**. An
option for that is ``artifacts_base_dir`` in the ``tank`` section. It is
recommended to set it to a convenient place, for example,
``~/yandex-tank-artifacts``; it would be easier to manage the artifacts
there.

Modules
~~~~~~~

Phantom
^^^^^^^

Load generator module that uses phantom utility.

INI file section: **[phantom]**

Options
'''''''

Basic options: 

* **ammofile** - ammo file path (ammo file is a file containing requests that are to be sent to a server) 
* **rps_schedule** - load schedule in terms of RPS 
* **instances** - max number of instances (concurrent requests) 
* **instances_schedule** - load schedule in terms of number of instances 
* **loop** - number of times requests from ammo file are repeated in loop 
* **ammo_limit** - limit request number
* **autocases** - enable marking requests automatically (1 -- enable, 0 -- disable)
* **chosen_cases** - use only selected cases

There are 3 ways to constrain requests number: by schedule with **rps_schedule**, by requests number with **ammo_limit** or by loop number with **loop** option. Tank stops if any constrain is reached. If stop reason is reached **ammo_limit** or **loop** it will be mentioned in log file. In test without **rps_schedule** file with requests is used one time by default

Additional options: 

* **writelog** - enable verbose request/response logging. Available options: 0 - disable, all - all messages, proto_warning - 4хх+5хх+network errors, proto_error - 5хх+network errors. Default: 0 
* **ssl** - enable SSL, 1 - enable, 0 - disable, default: 0 
* **address** - address of service to test. May contain port divided by colon for IPv4 or DN. For DN, DNS request is performed, and then reverse-DNS request to verify the correctness of name. Default: ``127.0.0.1`` 
* **port** - port of service to test. Default: ``80`` 
* **gatling_ip** - use multiple source addresses. List, divided by spaces. 
* **tank_type** - protocol type: http, none (raw TCP). Default: ``http``
* **eta_file** - where to write ETA time

URI-style options: 

* **uris** - URI list, multiline option. 
* **headers** - HTTP headers list in the following form: ``[Header: value]``, multiline option. 
* **header\_http** - HTTP version, default: ``1.1``

stpd-file cache options: 

* **use_caching** - enable cache, default: ``1`` 
* **cache_dir** - cache files directory, default: base artifacts directory. 
* **force_stepping** - force stpd file generation, default: ``0``

Advanced options: 

* **phantom_path** - phantom utility path, default: ``phantom`` 
* **phantom_modules_path** - phantom modules path, default:``/usr/lib/phantom`` 
* **config** - use given (in this option) config file for phantom instead of generated. 
* **phout_file** - import this phout instead of launching phantom (import phantom results)
* **stpd_file** - use this stpd-file instead of generated 
* **threads** - phantom thread count, default: ``<processor cores count>/2 + 1``
* **buffered_seconds** - amount of seconds to which delay aggregator, to be sure that everything were read from phout
* **additional_libs** - list separated by whitespaces, will be added to phantom config file in section ``module_setup`` 
* **method_prefix** - object's type, that has a functionality to create test requests. Default: method_stream
* **source_log_prefix** - prefix, added to class name that reads source data. Default: empty
* **method_options** - additional options for method objects. It is used for Elliptics etc. Default: empty

Phantom http-module tuning options: 

* **phantom_http_line** - First line length. Default - 1K
* **phantom_http_field_num** - Headers amount. Default - 128
* **phantom_http_field** - Header size. Default - 8K
* **phantom_http_entity** - Answer size. Please, keep in mind, especially if your service has large answers, that phantom doesn't read more than defined in ``phantom_http_entity``. Default - 8M

Artifacts
'''''''''

*  **phantom_*.conf** - generated configuration files
*  **phout_*.log** - raw results file
*  **phantom_stat_*.log** - phantom statistics, aggregated by seconds
*  **answ_*.log** - detailed request/response log
*  **phantom_*.log** - internal phantom log



Multi-tests
'''''''''''
To make several simultaneous tests with phantom, add proper amount of sections with names ``phantom-_N_``. All subtests are executed in parallel. Multi-test ends as soon as one subtest stops. Example:

:: 

    [phantom]
    phantom_path=phantom
    ammofile=data/dummy.ammo
    instances=10
    instances_schedule=line(1,10,1m)
    loop=1
    use_caching=1
    
    [phantom-1]
    uris=/
            /test
            /test2
    headers=[Host: www.ya.ru]
            [Connection: close]
    rps_schedule=const(1,30) line(1,1000,2m) const(1000,5m)
    address=fe80::200:f8ff:fe21:67cf
    port=8080
    ssl=1
    instances=3
    gatling_ip=127.0.0.1 127.0.0.2
    phantom_http_line=123M
    
    [phantom-2]
    uris=/3
    rps_schedule=const(1,30) line(1,50,2m) const(50,5m)

Options that apply only for main section: buffered_seconds, writelog, phantom_modules_path, phout_file, config, eta_file, phantom_path

JMeter
^^^^^^
JMeter module uses JMeter as a load generator 

INI file section: **[jmeter]**

Options
'''''''
* **jmx** - testplan for execution
* **args** - additional commandline arguments for JMeter
* **jmeter_path** - path to JMeter, allows to use alternative JMeter installation. Default: jmeter
* **buffered_seconds** - amount of seconds to which delay aggregator, to be sure that everything were read from jmeter's results file
* **all other options in the section** - they will be passed as User Defined Variables to JMeter

Artifacts
'''''''''
* **<original jmx>** - original testplan
* **<modified jmx>** - modified test plan with results output section
* **<jmeter_*.jtl>** - JMeter's results
* **<jmeter_*.log>** - JMeter's log

BFG
^^^
(`What is BFG <http://en.wikipedia.org/wiki/BFG_(weapon)>`_)
BFG is a generic gun that is able to use different kinds of cannons to shoot. To enable it, disable phantom first, enable BFG plugin and then specify the parameters for BFG and for the cannon you select. For example, if you want to kill an SQL db:

::

    [tank]
    ; Disable phantom:
    plugin_phantom=
    ; Enable BFG instead:
    plugin_bfg=Tank/Plugins/BFG.py
            
    ; BFG config section:
    [bfg]
            
    ; gun type -- what kind of gun should BFG use:
    gun_type=sql
            
    ; what ammo parser should BFG use:
    ammo_type=slowlog
            
    ; stepper parameters (see phantom options):
    instances = 200
    ammofile=bsdb03h.sql
    rps_schedule=line(1,1000,1m)
    loop=500
            
    ; selected gun config section:
    [sql_gun]
    db = mysql://user:user@localhost/


BFG Options
'''''''''''
INI file section: **[bfg]**

* **gun_type** - what kind of gun should BFG use
* **ammo_type** - what ammo parser should BFG use, default: phantom
* other common stepper options

SQL Gun Options
'''''''''''''''
INI file section: **[sql_gun]**

* **db** - DB uri in format:  ``dialect+driver://user:password@host/dbname[?key=value..]``, where dialect is a database name such as mysql, oracle, postgresql, etc., and driver the name of a DBAPI, such as psycopg2, pyodbc, cx_oracle, etc. `details <http://docs.sqlalchemy.org/en/rel_0_8/core/engines.html#database-urls>`_

Auto-stop
^^^^^^^^^

The Auto-stop module gets the data from the aggregator and passes them
to the criteria-objects that decide if we should stop the test.

INI file section: **[autostop]**

Options
'''''''

-  **autostop** - criteria list divided by spaces, in following format:
   ``type(parameters)``

Basic criteria types: 

* **time** - stop the test if average response time is higher then allowed. E.g.: ``time(1s500ms, 30s) time(50,15)``. Exit code - 21
* **http** - stop the test if the count of responses in time period (specified) with HTTP codes fitting the mask is larger then the specified absolute or relative value. Examples: ``http(404,10,15) http(5xx, 10%, 1m)``. Exit code - 22
* **net** - like ``http``, but for network codes. Use ``xx`` for all non-zero codes. Exit code - 23
* **quantile** - stop the test if the specified percentile is larger then specified level for as long as the time period specified. Available percentile values: 25, 50, 75, 80, 90, 95, 98, 99, 100. Example: ``quantile (95,100ms,10s)`` 
* **instances** - available when phantom module is included. Stop the test if instance count is larger then specified value. Example: ``instances(80%, 30) instances(50,1m)``. Exit code - 24
* **metric_lower** and **metric_higher** - stop test if monitored metrics are lower/higher than specified for time period. Example: metric_lower(127.0.0.1,Memory_free,500,10). Exit code - 31 and 32. **Note**: metric names (except customs) are written with underline. For hostnames masks are allowed (i.e target-\*.load.net)

Basic criteria aren't aggregated, they are tested for each second in specified period. For example autostop=time(50,15) means "stop if average responce time for every second in 15s interval is higher than 50ms"

Advanced criteria types:

* **total_time** — like ``time``, but accumulate for all time period (responses that fit may not be one-after-another, but only lay into specified time period). Example: ``total_time(300ms, 70%, 3s)``. Exit code - 25
* **total_http** — like ``http``, but accumulated. See ``total_time``. Example: ``total_http(5xx,10%,10s) total_http(3xx,40%,10s)``.  Exit code - 26
* **total_net** — like ``net``, but accumulated. See ``total_time``. Example: ``total_net(79,10%,10s) total_net(11x,50%,15s)``  Exit code - 27
* **negative_http** —  inversed ``total_http``. Stop if there are not enough responses that fit the specified mask. Use to be shure that server responds 200. Example: ``negative_http(2xx,10%,10s)``. Exit code: 28
* **negative_net** — inversed ``total_net``. Stop if there are not enough responses that fit the specified mask. Example: ``negative_net(0,10%,10s)``. Exit code: 29
* **http_trend** - Stop if trend for defined http codes is negative on defined period. Example: http_trend(2xx,10s). Exit code: 30. Trend is a sum of an average coefficient for linear functions calculated for each pair points in last n seconds and standart deviation for it

Graphite
^^^^^^^^
Graphite plugin uploads data to `Graphite <http://graphite.readthedocs.org/en/0.9.12/index.html>`_ monitoring tool.

Options
'''''''

* **address** - graphite server
* **port** - graphite backend port (where to send data), default: 2003
* **web_port** - graphite frontend port, default: 8080
* **template** - template file. Default: Tank/Plugins/graphite.tpl

Loadosophia
^^^^^^^^^^^
When test has been finished, module upload to Loadosophia.org test artifacts: file with answer times and files with monitoring data. The link will be shown in console output.

INI file section: **[loadosophia]**

Options
'''''''
* **token** - account's access key, received on Upload Token page
* **project** - test will be uploaded to that project
* **test_title** - test name
* **color_flag** - color flag, assigned to test. (gray flag = "to delete")
* **file_prefix** - prefix that will be added to uploaded file's name (deprecated

Monitoring
^^^^^^^^^^
Runs metrics collection through ssh connect.

INI file section: **[monitoring]**

Options
'''''''

* **config** - path to monitoring config file. Default: ``auto`` means collect default metrics from ``default_target`` host. If ``none`` is defined, monitoring won't be executed. Also it is possible to write plain multiline XML config.
* **default_target** - an address where from collect "default" metrics. When phantom module is used, address will be obtained from it.
* **ssh_timeout** - ssh connection timeout. Default: 5s

Artifacts
'''''''''

* **agent_*.cfg** - configuration files sent to hosts to run monitoring agents.
* **agent_<host>_*.log** - monitoring agents' log files, downloaded from hosts
* **monitoring_*.data** - data collected by monitoring agents, received by ssh.
* **<monitoring config** - monitoring config file

Configuration
'''''''''''''

Net access and authentication
"""""""""""""""""""""""""""""

Monitoring requires ssh access to hosts for copy and executing agents on them. SSH session is established with current user account, so you need to copy your public keys (ssh-copy-id) and enable nonpassword authorization on hosts.
If connection establishing failed for some reason in ``ssh_timeout`` seconds, corresponding message will be written to console and monitoring log and task will proceed further. 
Tip: write to ``.ssh/config`` next lines to eliminate ``-A`` option in ``ssh`` 

:: 
    
    StrictHostKeyChecking no
    ForwardAgent yes
    
Configuration file format
"""""""""""""""""""""""""

Config is an XML file with structure:
root element ``Monitoring`` includes elements ``Host`` which contains elements-metrics
Example:

::

    <Monitoring>
      <Host address="xxx.load.net">
        <CPU measure="user,system,iowait"/>
        <System measure="csw,int"/>
        <Memory measure="free,used"/>
        <Disk measure="read,write"/>
        <Net measure="recv,send"/>
      </Host>
    </Monitoring>
    
Element ``Monitoring``
**********************
Global monitoring settings. Attributes:

* ``loglevel`` - debug level (info, debug), optional. Default: info.

Element ``Host``
****************
Contains address and role of monitored server. Attributes:

* ``address="<IP address or domain name>"`` - server adddress. Mandatory. Special string ``[target]`` could be used here, which means "get from the tank target address"
* ``port="<SSH port>"`` - server's ssh port. Optional. Default: 22
* ``python="<python path>"`` - the way to use alternative python version. Optional
* ``interval="<seconds>"`` - metrics collection interval. Optional. Default: 1 second
* ``comment="<short commentary>"`` - short notice about server's role in test. Optional. Default: empty

Example: `<Host address="localhost" comment="frontend" priority="1" interval="5" />`

Metric elements
****************

Metric elements in general are set by metrics group name and particular metrics enumeration in attribute `measure`. Example: `<CPU measure="idle,user,system" />`

List of metrics group names and particular metrics in them:

* CPU
    * idle
    * user - default 
    * system - default
    * iowait - default
    * nice
* System
    * la1 - load average 1 min
    * la5 - ...
    * la15 - ...
    * csw - context switches, default
    * int - interrupts, default
    * numproc - process amount in system
    * numthreads - threads amount in system
* Memory
    * free - default
    * used - default
    * cached
    * buff
* Disk
    * read  - default
    * write - default
* Net
    * recv - bytes received, default
    * send - bytes sent,  default
    * tx - outgoing packet rate
    * rx - incoming packet rate 
    * retransmit - retransmit amount
    * estab - number of sockets in ESTABLISHED state
    * closewait - number of sockets in CLOSEWAIT
    * timewait - number of sockets in TIMEWAIT
* Custom
    * tail - metric value is read from file's last line, file path is specified in node text. Example: `<Custom measure="tail" label="size history">/tmp/dbsize.log</Custom>`
    * call - metric value is a command or script execution output. Example: `<Custom measure="call" diff="1" label="Base size">du -hs /usr/mysql/data</Custom>`

Custom metrics have an additional attribute `diff`, that signals to obtain as metric value the difference between previous and current value. So in example above, not the file size, but the dynamic of changes in size will be written.
Also custom metrics must have attribute `label`, which defines metric short name (only latin). `Underline symbol should be avoided.` 

Monitoring default logic
****************
Default logic is applied on next levels:

1. Host level: by default target is derived from `address` in `phantom` module.
2. Metrics group level: If config contain host address only, without metrics, i.e `<Host address="somehost.yandex.ru" />`, then default metrics in groups `CPU`, `Memory`, `Disk` are collected. If host has defined any metric, then only it is collected.
3. Metric level: if metrics group is defined without attribute `measure`, then only default group metrics are collected.
   
Startup and Shutdown elements
****************
There is special non-metric elements called Startup and Shutdown. Startup shell scripts will be started before metric collection. On the normal shutdown startup scripts will be stopped and shutdown scripts will run. There may be any number of Startup and Shutdown elements.

Following example illustrates this feature:
::

    <Monitoring>
        <Host address="[target]">
            <Startup>cat /dev/urandom | hexdump | awk 'BEGIN {RS="0000"} {print length($0)}' > /tmp/urandom.txt</Startup>
            <Custom measure="tail" label="random int tail">/tmp/urandom.txt</Custom>
            <Custom measure="call" label="random int call">tail -n1 /tmp/urandom.txt</Custom>
            <Shutdown>rm /tmp/urandom.txt</Shutdown>
        </Host>
    </Monitoring>



Console on-line screen
^^^^^^^^^^^^^^^^^^^^^^

Shows usefull information in console while running the test

INI file section: **[console]**

Options
'''''''

-  **short_only** - show only one-line summary instead of full-screen
   (usefull for scripting), default: 0 (disable)
-  **info_panel_width** - relative right-panel width in percents,
   default: 33
-  disable_all_colors - switch off color scheme, 0/1, default: 0
-  disable_colors - don't use specified colors in console. List with whitespaces. Example: ``WHITE GREEN RED CYAN MAGENTA YELLOW``

Aggregator
^^^^^^^^^^

The aggregator module is responsible for aggregation of data received
from different kind of modules and transmitting that aggregated data to
consumer modules (Console screen module is an example of such kind). 

INI file section: **[aggregator]** 
 
Options:
''''''''
 
* **time_periods** - time intervals list divided by zero. Default: ``1ms 2 3 4 5 6 7 8 9 10 20 30 40 50 60 70 80 90 100 150 200 250 300 350 400 450 500 600 650 700 750 800 850 900 950 1s 1500 2s 2500 3s 3500 4s 4500 5s 5500 6s 6500 7s 7500 8s 8500 9s 9500 10s 11s``
* **precise_cumulative** - 0/1, controls the accuracy of cumulative percentile. Default: ``1``. When disabled, cumulative percentiles are calculated with ``time_periods`` precision, otherwise - up to milliseconds.

ShellExec
^^^^^^^^^

The ShellExec module executes the shell-scripts (hooks) on different
stages of test, for example, you could start/stop some services just
before/after the test. Every hook must return 0 as an exit code or the
test is terminated. Hook's stdout will be written to DEBUG, stderr will
be WARNINGs. Example: ``[shellexec] start=/bin/ls -l``. Note: command quoting is not needed. That line doesn't work: ``start="/bin/ls -l"``

INI file section: **[shellexec]**

Options:
''''''''

-  **prepare** - the script to run on prepare stage
-  **start** - the script to run on start stage
-  **poll** - the script to run every second while the test is running
-  **end** - the script to run on end stage
-  **postprocess** - the script to run on postprocess stage


AB
^^

Apache Benchmark load generator module. As the ab utility writes results
to file only after the test is finished, Yandex.Tank is unable to show
the on-line statistics for the tests with ab. The data are reviewed
after the test.

INI file section: **[ab]**

Options
'''''''

* **url** - requested URL, default: ``http:**localhost/`` 
* **requests** - total request count, default: 100 
* **concurrency** - number of concurrent requests: 1 
* **options** - ab command line options

Artifacts
'''''''''

-  **ab_*.log** - request log with response times

Resource Check
^^^^^^^^^^^^^^
Module checks free memory and disk space amount before and during test. Test stops if minimum values are reached. 

INI file section: **[rcheck]**

Options
'''''''

* **interval** - how often to check resources. Default interval: 10s
* **disk_limit** - Minimum free disk space in MB. Default: 2GB
* **mem_limit** - Minimum free memory amount in MB. Default: 512MB

RC Assert
^^^^^^^^^

Module checks test's exit code with predefined acceptable codes. If exit code matches, it is overrides as 0. Otherwise it is replaced with code from option ``fail_code``

INI file section: **[rcassert]**

Options
'''''''
* **pass** - list of acceptable codes, delimiter - whitespace. Default: empty, no check is performed.
* **fail_code** - exit code when check fails, integer number. Default: 10

Web Online
^^^^^^^^^^

Module starts local web sever that shows online graphics. Enabled by ``plugin_web=Tank/Plugins/WebOnline.py`` in ``[tank]`` section.

INI file section: **[web]**

Options
'''''''

* **port** - a port to bind to on localhost. Default: 8080
* **interval** - graphics' interval that will be shown, in seconds. Default: 60 seconds
* **redirect** - address where to redirect browser after test stop. 
* **manual_stop** - flag 0/1. If '1' then webserver will wait for key press from keyboard to exit

Yandex.Tank kernel
^^^^^^^^^^^^^^^^^^

Python-object, that loads and execs tank modules.

INI file section: **[tank]**

Options
'''''''

* **artifacts_base_dir** - base directory for artifacts storing. Temporary artifacts files are stored here. Default: current directory
* **artifacts_dir** - directory where to keep artifacts after test. Default: directory in ``artifacts_base_dir`` named in  Date/Time format.
* **flush_config_to** - dump configuration options after each tank step (`yandex.tank steps. sorry, russian only <http://clubs.ya.ru/yandex-tank/replies.xml?item_no=6>`_) to that file 

Tips&Tricks
^^^^^^^^^^^

Shows tips and tricks in fullscreen console. **If you have any
tips&tricks, tell the developers about them**

INI-file section: **[tips]**

Options
'''''''
* **disable** - disable tips and tricks, default: don't (0)

Sources
~~~~~~~

Yandex.Tank sources ((https://github.com/yandex-load/yandex-tank here)).

load.ini example
~~~~~~~~~~~~~~~~~

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

    
