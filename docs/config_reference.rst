================
Config reference
================


Core
====

``core`` (dict)
---------------
*\- (no description).*

:``affinity`` (string):
 *\- specify cpu core(s) to bind tank process to,  http://linuxhowtos.org/manpages/1/taskset.htm. Default:* ``""``
:``api_jobno`` (string):
 *\- tankapi job id, also used as test\'s directory name \- determined by tank.*
:``artifacts_base_dir`` (string):
 *\- base directory to store tests\' artifacts directories. Default:* ``./logs``
:``artifacts_dir`` (string):
 *\- directory inside base directory to store test\'s artifacts, defaults to api_jobno if null.*
:``cmdline`` (string):
 *\- (no description).*
:``exitcode`` (integer):
 *\- (no description).*
:``flush_config_to`` (string):
 *\- path to store config.*
:``ignore_lock`` (boolean):
 *\- if tank is locked ( *.lock file(s) presented in lock_dir), shoot nevertheless. Default:* ``False``
:``lock_dir`` (string):
 *\- directory to store *.lock files. Default:* ``/var/lock/``
:``message`` (string):
 *\- (no description).*
:``operator`` (string):
 *\- your username.*
:``pid`` (integer):
 *\- (no description).*
:``taskset_path`` (string):
 *\- (no description). Default:* ``taskset``
:``uuid`` (string):
 *\- (no description).*

:allow_unknown:
 False

``version`` (string)
--------------------
*\- (no description).*

ShootExec
=========

``cmd`` (string)
----------------
*\- command that produces test results and stats in Phantom format.* **Required.**

``output_path`` (string)
------------------------
*\- path to test results.* **Required.**

``stats_path`` (string)
-----------------------
*\- path to tests stats. Default:* ``None``

:nullable:
 True

InfluxUploader
==============

``address`` (string)
--------------------
*\- (no description). Default:* ``localhost``

``chunk_size`` (integer)
------------------------
*\- (no description). Default:* ``500000``

``custom_tags`` (dict)
----------------------
*\- (no description). Default:* ``{}``

``database`` (string)
---------------------
*\- (no description). Default:* ``mydb``

``histograms`` (boolean)
------------------------
*\- (no description). Default:* ``False``

``labeled`` (boolean)
---------------------
*\- (no description). Default:* ``False``

``password`` (string)
---------------------
*\- (no description). Default:* ``root``

``port`` (integer)
------------------
*\- (no description). Default:* ``8086``

``prefix_measurement`` (string)
-------------------------------
*\- (no description). Default:* ``""``

``tank_tag`` (string)
---------------------
*\- (no description). Default:* ``unknown``

``username`` (string)
---------------------
*\- (no description). Default:* ``root``

Telegraf
========

``config_contents`` (string)
----------------------------
*\- used to repeat tests from Overload, not for manual editing.*

``config`` (string)
-------------------
*\- Path to monitoring config file. Default:* ``auto``

:one of:
 :``<path/to/file.xml>``: path to telegraf configuration file
 :``auto``: collect default metrics from default_target host
 :``none``: disable monitoring

``default_target`` (string)
---------------------------
*\- host to collect default metrics from (if "config: auto" specified). Default:* ``localhost``

``disguise_hostnames`` (boolean)
--------------------------------
*\- Disguise real host names \- use this if you upload results to Overload and dont want others to see your hostnames. Default:* ``True``

``kill_old`` (boolean)
----------------------
*\- kill old hanging agents on target(s). Default:* ``False``

``ssh_timeout`` (string)
------------------------
*\- timeout of ssh connection to target(s). Default:* ``5s``

:examples:
 ``10s``
  10 seconds
 ``2m``
  2 minutes

Autostop
========

``autostop`` (list of string)
-----------------------------
*\- list of autostop constraints. Default:* ``[]``

:[list_element] (string):
 *\- autostop constraint.*
 
 :examples:
  ``http(4xx,50%,5)``
   stop when rate of 4xx http codes is 50% or more during 5 seconds

:examples:
 ``[quantile(50,100,20), http(4xx,50%,5)]``
  stop when either quantile 50% or 4xx http codes exceeds specified levels

``report_file`` (string)
------------------------
*\- path to file to store autostop report. Default:* ``autostop_report.txt``

JMeter
======

``affinity`` (string)
---------------------
*\- Use to set CPU affinity. Default:* ``""``

:nullable:
 True

``args`` (string)
-----------------
*\- additional commandline arguments for JMeter. Default:* ``""``

``buffer_size`` (integer)
-------------------------
*\- jmeter buffer size. Default:* ``None``

:nullable:
 True

``buffered_seconds`` (integer)
------------------------------
*\- Aggregator delay \- to be sure that everything were read from jmeter results file. Default:* ``3``

``exclude_markers`` (list of string)
------------------------------------
*\- (no description). Default:* ``[]``

:[list_element] (string):
 *\- (no description).*
 
 :empty:
  False

``ext_log`` (string)
--------------------
*\- additional log, jmeter xml format. Saved in test dir as jmeter_ext_XXXX.jtl. Default:* ``none``

:one of: [``none``, ``errors``, ``all``]

``extended_log`` (string)
-------------------------
*\- additional log, jmeter xml format. Saved in test dir as jmeter_ext_XXXX.jtl. Default:* ``none``

:one of: [``none``, ``errors``, ``all``]

``jmeter_path`` (string)
------------------------
*\- Path to JMeter. Default:* ``jmeter``

``jmeter_ver`` (float)
----------------------
*\- Which JMeter version tank should expect. Affects the way connection time is logged. Default:* ``3.0``

``jmx`` (string)
----------------
*\- Testplan for execution.*

``shutdown_timeout`` (integer)
------------------------------
*\- timeout for automatic test shutdown. Default:* ``10``

``variables`` (dict)
--------------------
*\- variables for jmx testplan. Default:* ``{}``

Pandora
=======

``affinity`` (string)
---------------------
*\- Use to set CPU affinity. Default:* ``""``

:nullable:
 True

``buffered_seconds`` (integer)
------------------------------
*\- (no description). Default:* ``2``

``config_content`` (dict)
-------------------------
*\- Pandora config contents. Default:* ``{}``

``config_file`` (string)
------------------------
*\- Pandora config file path. Default:* ``""``

``expvar`` (boolean)
--------------------
*\- (no description). Default:* ``False``

``pandora_cmd`` (string)
------------------------
*\- Pandora executable path or link to it. Default:* ``pandora``

``report_file`` (string)
------------------------
*\- Pandora phout path (normally will be taken from pandora config). Default:* ``None``

:nullable:
 True

``resource`` (dict)
-------------------
*\- dict with attributes for additional resources.*

``resources`` (list)
--------------------
*\- additional resources you need to download before test. Default:* ``[]``

Android
=======

``volta_options`` (dict)
------------------------
*\- (no description).*

ResourceCheck
=============

``disk_limit`` (integer)
------------------------
*\- (no description). Default:* ``2048``

``interval`` (string)
---------------------
*\- (no description). Default:* ``10s``

``mem_limit`` (integer)
-----------------------
*\- (no description). Default:* ``512``

Bfg
===

``address`` (string)
--------------------
*\- Address of target. Format: [host]:port, [ipv4]:port, [ipv6]:port. Port is optional. Tank checks each test if port is available.*

:examples:
 ``127.0.0.1:8080``
  
 ``www.w3c.org``

``ammo_limit`` (integer)
------------------------
*\- Upper limit for the total number of requests. Default:* ``-1``

``ammo_type`` (string)
----------------------
*\- Ammo format. Default:* ``caseline``

``ammofile`` (string)
---------------------
*\- Path to ammo file. Default:* ``""``

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/core_and_modules.html#bfg

``autocases`` (integer or string)
---------------------------------
*\- Use to automatically tag requests. Requests might be grouped by tag for later analysis. Default:* ``0``

:one of:
 :``<N>``: use N first uri parts to tag request, slashes are replaced with underscores
 :``uniq``: tag each request with unique uid
 :``uri``: tag each request with its uri path, slashes are replaced with underscores

:examples:
 ``2``
  /example/search/hello/help/us?param1=50 -> _example_search
 ``3``
  /example/search/hello/help/us?param1=50 -> _example_search_hello
 ``uniq``
  /example/search/hello/help/us?param1=50 -> c98b0520bb6a451c8bc924ed1fd72553
 ``uri``
  /example/search/hello/help/us?param1=50 -> _example_search_hello_help_us

``cache_dir`` (string)
----------------------
*\- stpd\-file cache directory. If not specified, defaults to base artifacts directory. Default:* ``None``

:nullable:
 True

``cached_stpd`` (boolean)
-------------------------
*\- Use cached stpd file. Default:* ``False``

``chosen_cases`` (string)
-------------------------
*\- Use only selected cases. Default:* ``""``

``enum_ammo`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

``file_cache`` (integer)
------------------------
*\- (no description). Default:* ``8192``

``force_stepping`` (integer)
----------------------------
*\- Ignore cached stpd files, force stepping. Default:* ``0``

``green_threads_per_instance`` (integer)
----------------------------------------
*\- Number of green threads every worker process will execute. For "green" worker type only. Default:* ``1000``

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/core_and_modules.html#bfg

``gun_config`` (dict)
---------------------
*\- Options for your load scripts.*

:``base_address`` (string):
 *\- base target address.*
:``class_name`` (string):
 *\- class that contains load scripts. Default:* ``LoadTest``
:``init_param`` (string):
 *\- parameter that's passed to "setup" method. Default:* ``""``
:``module_name`` (string):
 *\- name of module that contains load scripts.*
:``module_path`` (string):
 *\- directory of python module that contains load scripts. Default:* ``""``

:allow_unknown:
 True
:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/core_and_modules.html#bfg

``gun_type`` (string)
---------------------
*\- Type of gun BFG should use.* **Required.**

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/core_and_modules.html#bfg-options

:one of: [``custom``, ``http``, ``scenario``, ``ultimate``]

``header_http`` (string)
------------------------
*\- HTTP version. Default:* ``1.0``

:one of:
 :``1.0``: http 1.0
 :``1.1``: http 1.1

``headers`` (list of string)
----------------------------
*\- HTTP headers. Default:* ``[]``

:[list_element] (string):
 *\- Format: "Header: Value".*
 
 :examples:
  ``accept: text/html``

``instances`` (integer)
-----------------------
*\- number of processes (simultaneously working clients). Default:* ``1000``

``load_profile`` (dict)
-----------------------
*\- Configure your load setting the number of RPS or instances (clients) as a function of time, or using a prearranged schedule.* **Required.**

:``load_type`` (string):
 *\- Choose control parameter.* **Required.**
 
 :one of:
  :``instances``: control the number of instances
  :``rps``: control the rps rate
  :``stpd_file``: use prearranged schedule file
:``schedule`` (string):
 *\- load schedule or path to stpd file.* **Required.**
 
 :examples:
  ``const(200,90s)``
   constant load of 200 instances/rps during 90s
  ``line(100,200,10m)``
   linear growth from 100 to 200 instances/rps during 10 minutes
  ``test_dir/test_backend.stpd``
   path to ready schedule file

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/tutorial.html#tutorials

``loop`` (integer)
------------------
*\- Loop over ammo file for the given amount of times. Default:* ``-1``

``pip`` (string)
----------------
*\- pip modules to install before the test. Use multiline to install multiple modules. Default:* ``""``

``uris`` (list of string)
-------------------------
*\- URI list. Default:* ``[]``

:[list_element] (string):
 *\- URI path string.*
 
 :examples:
  ``["/example/search", "/example/search/hello", "/example/search/hello/help"]``

``use_caching`` (boolean)
-------------------------
*\- Enable stpd\-file caching. Default:* ``True``

``worker_type`` (string)
------------------------
*\- (no description). Default:* ``""``

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/core_and_modules.html#bfg-worker-type

RCAssert
========

``fail_code`` (integer)
-----------------------
*\- (no description). Default:* ``10``

``pass`` (string)
-----------------
*\- (no description). Default:* ``""``

ShellExec
=========

``catch_out`` (boolean)
-----------------------
*\- show commands stdout. Default:* ``False``

``end`` (string)
----------------
*\- shell command to execute after test end. Default:* ``""``

``poll`` (string)
-----------------
*\- shell command to execute every second while test is running. Default:* ``""``

``post_process`` (string)
-------------------------
*\- shell command to execute on post process stage. Default:* ``""``

``prepare`` (string)
--------------------
*\- shell command to execute on prepare stage. Default:* ``""``

``start`` (string)
------------------
*\- shell command to execute on start. Default:* ``""``

JsonReport
==========

``monitoring_log`` (string)
---------------------------
*\- file name for monitoring log. Default:* ``monitoring.log``

``test_data_log`` (string)
--------------------------
*\- file name for test data log. Default:* ``test_data.log``

DataUploader
============

``api_address`` (string)
------------------------
*\- api base address. Default:* ``https://overload.yandex.net/``

``api_attempts`` (integer)
--------------------------
*\- number of retries in case of api fault. Default:* ``60``

``api_timeout`` (integer)
-------------------------
*\- delay between retries in case of api fault. Default:* ``10``

``chunk_size`` (integer)
------------------------
*\- max amount of data to be sent in single requests. Default:* ``500000``

``component`` (string)
----------------------
*\- component of your software. Default:* ``""``

``connection_timeout`` (integer)
--------------------------------
*\- tcp connection timeout. Default:* ``30``

``ignore_target_lock`` (boolean)
--------------------------------
*\- start test even if target is locked. Default:* ``False``

``job_dsc`` (string)
--------------------
*\- job description. Default:* ``""``

``job_name`` (string)
---------------------
*\- job name. Default:* ``none``

``jobno_file`` (string)
-----------------------
*\- file to save job number to. Default:* ``jobno_file.txt``

``jobno`` (string)
------------------
*\- number of an existing job. Use to upload data to an existing job. Requres upload token.*

:dependencies:
 upload_token

``lock_targets`` (list or string)
---------------------------------
*\- targets to lock. Default:* ``auto``

:one of:
 :``auto``: automatically identify target host
 :``list_of_targets``: list of targets to lock

:tutorial_link:
 http://yandextank.readthedocs.io

``log_data_requests`` (boolean)
-------------------------------
*\- log POSTs of test data for debugging. Tank should be launched in debug mode (\-\-debug). Default:* ``False``

``log_monitoring_requests`` (boolean)
-------------------------------------
*\- log POSTs of monitoring data for debugging. Tank should be launched in debug mode (\-\-debug). Default:* ``False``

``log_other_requests`` (boolean)
--------------------------------
*\- log other api requests for debugging. Tank should be launched in debug mode (\-\-debug). Default:* ``False``

``log_status_requests`` (boolean)
---------------------------------
*\- log status api requests for debugging. Tank should be launched in debug mode (\-\-debug). Default:* ``False``

``maintenance_attempts`` (integer)
----------------------------------
*\- number of retries in case of api maintanance downtime. Default:* ``10``

``maintenance_timeout`` (integer)
---------------------------------
*\- delay between retries in case of api maintanance downtime. Default:* ``60``

``meta`` (dict)
---------------
*\- additional meta information.*

``network_attempts`` (integer)
------------------------------
*\- number of retries in case of network fault. Default:* ``60``

``network_timeout`` (integer)
-----------------------------
*\- delay between retries in case of network fault. Default:* ``10``

``notify`` (list of string)
---------------------------
*\- users to notify. Default:* ``[]``

``operator`` (string)
---------------------
*\- user who started the test. Default:* ``None``

:nullable:
 True

``send_status_period`` (integer)
--------------------------------
*\- delay between status notifications. Default:* ``10``

``strict_lock`` (boolean)
-------------------------
*\- set true to abort the test if the the target's lock check is failed. Default:* ``False``

``target_lock_duration`` (string)
---------------------------------
*\- how long should the target be locked. In most cases this should be long enough for the test to run. Target will be unlocked automatically right after the test is finished. Default:* ``30m``

``task`` (string)
-----------------
*\- task title. Default:* ``""``

``threads_timeout`` (integer)
-----------------------------
*\- (no description). Default:* ``60``

``token_file`` (string)
-----------------------
*\- API token.*

``upload_token`` (string)
-------------------------
*\- Job's token. Use to upload data to an existing job. Requres jobno.*

:dependencies:
 jobno

``ver`` (string)
----------------
*\- version of the software tested. Default:* ``""``

``writer_endpoint`` (string)
----------------------------
*\- writer api endpoint. Default:* ``""``

Phantom
=======

``additional_libs`` (list of string)
------------------------------------
*\- Libs for Phantom, to be added to phantom config file in section "module_setup". Default:* ``[]``

``address`` (string)
--------------------
*\- Address of target. Format: [host]:port, [ipv4]:port, [ipv6]:port. Port is optional. Tank checks each test if port is available.* **Required.**

:empty:
 False
:examples:
 ``127.0.0.1:8080``
  
 ``www.w3c.org``

``affinity`` (string)
---------------------
*\- Use to set CPU affinity. Default:* ``""``

:examples:
 ``0,1,2,16,17,18``
  enable 6 specified cores
 ``0-3``
  enable first 4 cores

``ammo_limit`` (integer)
------------------------
*\- Sets the upper limit for the total number of requests. Default:* ``-1``

``ammo_type`` (string)
----------------------
*\- Ammo format. Don't forget to change ammo_type option if you switch the format of your ammo, otherwise you might get errors. Default:* ``phantom``

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/tutorial.html#preparing-requests

:one of:
 :``access``: Use access.log from your web server as a source of requests
 :``phantom``: Use Request-style file. Most versatile, HTTP as is. See tutorial for details
 :``uri``: Use URIs listed in file with headers. Simple but allows for GET requests only. See tutorial for details
 :``uripost``: Use URI-POST file. Allows POST requests with bodies. See tutorial for details

``ammofile`` (string)
---------------------
*\- Path to ammo file. Ammo file contains requests to be sent to a server. Can be gzipped. Default:* ``""``

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/tutorial.html#preparing-requests

``autocases`` (integer or string)
---------------------------------
*\- Use to automatically tag requests. Requests might be grouped by tag for later analysis. Default:* ``0``

:one of:
 :``<N>``: use N first uri parts to tag request, slashes are replaced with underscores
 :``uniq``: tag each request with unique uid
 :``uri``: tag each request with its uri path, slashes are replaced with underscores

:examples:
 ``2``
  /example/search/hello/help/us?param1=50 -> _example_search
 ``3``
  /example/search/hello/help/us?param1=50 -> _example_search_hello
 ``uniq``
  /example/search/hello/help/us?param1=50 -> c98b0520bb6a451c8bc924ed1fd72553
 ``uri``
  /example/search/hello/help/us?param1=50 -> _example_search_hello_help_us

``buffered_seconds`` (integer)
------------------------------
*\- Aggregator latency. Default:* ``2``

``cache_dir`` (string)
----------------------
*\- stpd\-file cache directory. Default:* ``None``

:nullable:
 True

``chosen_cases`` (string)
-------------------------
*\- Use only selected cases. Default:* ``""``

``client_certificate`` (string)
-------------------------------
*\- Path to client SSL certificate. Default:* ``""``

``client_cipher_suites`` (string)
---------------------------------
*\- Cipher list, consists of one or more cipher strings separated by colons (see man ciphers). Default:* ``""``

``client_key`` (string)
-----------------------
*\- Path to client's certificate's private key. Default:* ``""``

``config`` (string)
-------------------
*\- Use ready phantom config instead of generated. Default:* ``""``

``connection_test`` (boolean)
-----------------------------
*\- Test TCP socket connection before starting the test. Default:* ``True``

``enum_ammo`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

``file_cache`` (integer)
------------------------
*\- (no description). Default:* ``8192``

``force_stepping`` (integer)
----------------------------
*\- Ignore cached stpd files, force stepping. Default:* ``0``

``gatling_ip`` (string)
-----------------------
*\- (no description). Default:* ``""``

``header_http`` (string)
------------------------
*\- HTTP version. Default:* ``1.0``

:one of:
 :``1.0``: http 1.0
 :``1.1``: http 1.1

``headers`` (list of string)
----------------------------
*\- HTTP headers. Default:* ``[]``

:[list_element] (string):
 *\- Format: "Header: Value".*
 
 :examples:
  ``accept: text/html``

``instances`` (integer)
-----------------------
*\- Max number of concurrent clients. Default:* ``1000``

``load_profile`` (dict)
-----------------------
*\- Configure your load setting the number of RPS or instances (clients) as a function of time,or using a prearranged schedule.* **Required.**

:``load_type`` (string):
 *\- Choose control parameter.* **Required.**
 
 :one of:
  :``instances``: control the number of instances
  :``rps``: control the rps rate
  :``stpd_file``: use prearranged schedule file
:``schedule`` (string):
 *\- load schedule or path to stpd file.* **Required.**
 
 :examples:
  ``const(200,90s)``
   constant load of 200 instances/rps during 90s
  ``line(100,200,10m)``
   linear growth from 100 to 200 instances/rps during 10 minutes
  ``test_dir/test_backend.stpd``
   path to ready schedule file

:tutorial_link:
 http://yandextank.readthedocs.io/en/latest/tutorial.html#tutorials

``loop`` (integer)
------------------
*\- Loop over ammo file for the given amount of times. Default:* ``-1``

``method_options`` (string)
---------------------------
*\- Additional options for method objects. It is used for Elliptics etc. Default:* ``""``

``method_prefix`` (string)
--------------------------
*\- Object's type, that has a functionality to create test requests. Default:* ``method_stream``

``multi`` (list of dict)
------------------------
*\- List of configs for multi\-test. All of the options from main config supported. All of them not required and inherited from main config if not specified. Default:* ``[]``

``name`` (string)
-----------------
*\- Name of a part in multi config.* **Required.**

``phantom_http_entity`` (string)
--------------------------------
*\- Limits the amount of bytes Phantom reads from response. Default:* ``8M``

``phantom_http_field_num`` (integer)
------------------------------------
*\- Max number of headers. Default:* ``128``

``phantom_http_field`` (string)
-------------------------------
*\- Header size. Default:* ``8K``

``phantom_http_line`` (string)
------------------------------
*\- First line length. Default:* ``1K``

``phantom_modules_path`` (string)
---------------------------------
*\- Phantom modules path. Default:* ``/usr/lib/phantom``

``phantom_path`` (string)
-------------------------
*\- Path to Phantom binary. Default:* ``phantom``

``phout_file`` (string)
-----------------------
*\- deprecated. Default:* ``""``

``port`` (string)
-----------------
*\- Explicit target port, overwrites port defined with address. Default:* ``""``

:regex:
 \d{0,5}

``source_log_prefix`` (string)
------------------------------
*\- Prefix added to class name that reads source data. Default:* ``""``

``ssl`` (boolean)
-----------------
*\- Enable ssl. Default:* ``False``

``tank_type`` (string)
----------------------
*\- Choose between http and pure tcp guns. Default:* ``http``

:one of:
 :``http``: HTTP gun
 :``none``: TCP gun

``threads`` (integer)
---------------------
*\- Phantom thread count. When not specified, defaults to <processor cores count> / 2 + 1. Default:* ``None``

:nullable:
 True

``timeout`` (string)
--------------------
*\- Response timeout. Default:* ``11s``

``uris`` (list of string)
-------------------------
*\- URI list. Default:* ``[]``

:[list_element] (string):
 *\- URI path string.*

:examples:
 ``["/example/search", "/example/search/hello", "/example/search/hello/help"]``

``use_caching`` (boolean)
-------------------------
*\- Enable stpd\-file caching for similar tests. Set false to reload ammo file and generate new stpd. Default:* ``True``

``writelog`` (string)
---------------------
*\- Enable verbose request/response logging. Default:* ``0``

:one of:
 :``0``: disable
 :``all``: all messages
 :``proto_error``: 5xx+network errors
 :``proto_warning``: 4xx+5xx+network errors

Console
=======

``cases_max_spark`` (integer)
-----------------------------
*\- length of sparkline for each case, 0 to disable. Default:* ``120``

``cases_sort_by`` (string)
--------------------------
*\- field for cases data sort. Default:* ``count``

:one of: [``count``, ``net_err``, ``http_err``]

``disable_all_colors`` (boolean)
--------------------------------
*\- disable colors in full output. Default:* ``False``

``disable_colors`` (string)
---------------------------
*\- (no description). Default:* ``""``

``info_panel_width`` (integer)
------------------------------
*\- width of right panel. Default:* ``33``

``max_case_len`` (integer)
--------------------------
*\- max lenght of case name, longer names will be cut in console output. Default:* ``32``

``short_only`` (boolean)
------------------------
*\- do not draw full console screen, write short info for each second. Default:* ``False``

``sizes_max_spark`` (integer)
-----------------------------
*\- max length of sparkline for request/response sizes, 0 to disable. Default:* ``120``

``times_max_spark`` (integer)
-----------------------------
*\- max length of sparkline for fractions of request time, 0 to disable. Default:* ``120``