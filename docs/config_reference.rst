================
Config reference
================


Android
=======

``volta_options`` (dict)
------------------------
*\- (no description).*

Appium
======

``appium_cmd`` (string)
-----------------------
*\- (no description). Default:* ``appium``

``port`` (string)
-----------------
*\- (no description). Default:* ``4723``

``user`` (string)
-----------------
*\- (no description). Default:* ``""``

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

BatteryHistorian
================

``device_id`` (string)
----------------------
*\- (no description). Default:* ``None``

:nullable:
 True

Bfg
===

``address`` (string)
--------------------
*\- (no description).*

``ammo_limit`` (integer)
------------------------
*\- (no description). Default:* ``-1``

``ammo_type`` (string)
----------------------
*\- (no description). Default:* ``caseline``

``ammofile`` (string)
---------------------
*\- (no description). Default:* ``""``

``autocases`` (string)
----------------------
*\- (no description). Default:* ``0``

``cache_dir`` (string)
----------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``cached_stpd`` (boolean)
-------------------------
*\- (no description). Default:* ``False``

``chosen_cases`` (string)
-------------------------
*\- (no description). Default:* ``""``

``enum_ammo`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

``file_cache`` (integer)
------------------------
*\- (no description). Default:* ``8192``

``force_stepping`` (integer)
----------------------------
*\- (no description). Default:* ``0``

``green_threads_per_instance`` (integer)
----------------------------------------
*\- (no description). Default:* ``1000``

``gun_config`` (dict)
---------------------
*\- (no description).*

:``base_address`` (string):
 *\- (no description).*
:``class_name`` (string):
 *\- (no description). Default:* ``LoadTest``
:``init_param`` (string):
 *\- (no description). Default:* ``""``
:``module_name`` (string):
 *\- (no description).*
:``module_path`` (string):
 *\- (no description). Default:* ``""``

:allow_unknown:
 True

``gun_type`` (string)
---------------------
*\- (no description).* **Required.**

:one of: [``custom``, ``http``, ``scenario``, ``ultimate``]

``header_http`` (string)
------------------------
*\- (no description). Default:* ``1.0``

``headers`` (string)
--------------------
*\- (no description). Default:* ``""``

``instances`` (integer)
-----------------------
*\- (no description). Default:* ``1000``

``load_profile`` (dict)
-----------------------
*\- (no description).* **Required.**

:``load_type`` (string):
 *\- (no description).* **Required.**
 
 :regex:
  ^rps|instances|stpd_file$
:``schedule`` (string):
 *\- (no description).* **Required.**

``loop`` (integer)
------------------
*\- (no description). Default:* ``-1``

``pip`` (string)
----------------
*\- (no description). Default:* ``""``

``uris`` (string)
-----------------
*\- (no description). Default:* ``""``

``use_caching`` (boolean)
-------------------------
*\- (no description). Default:* ``True``

``worker_type`` (string)
------------------------
*\- (no description). Default:* ``""``

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

DataUploader
============

``api_address`` (string)
------------------------
*\- (no description). Default:* ``https://overload.yandex.net/``

``api_attempts`` (integer)
--------------------------
*\- (no description). Default:* ``60``

``api_timeout`` (integer)
-------------------------
*\- (no description). Default:* ``10``

``chunk_size`` (integer)
------------------------
*\- (no description). Default:* ``500000``

``component`` (string)
----------------------
*\- (no description). Default:* ``""``

``connection_timeout`` (integer)
--------------------------------
*\- (no description). Default:* ``30``

``ignore_target_lock`` (boolean)
--------------------------------
*\- (no description). Default:* ``False``

``job_dsc`` (string)
--------------------
*\- (no description). Default:* ``""``

``job_name`` (string)
---------------------
*\- (no description). Default:* ``none``

``jobno_file`` (string)
-----------------------
*\- (no description). Default:* ``jobno_file.txt``

``jobno`` (string)
------------------
*\- (no description).*

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
*\- (no description). Default:* ``False``

``log_monitoring_requests`` (boolean)
-------------------------------------
*\- (no description). Default:* ``False``

``log_other_requests`` (boolean)
--------------------------------
*\- (no description). Default:* ``False``

``log_status_requests`` (boolean)
---------------------------------
*\- (no description). Default:* ``False``

``maintenance_attempts`` (integer)
----------------------------------
*\- (no description). Default:* ``10``

``maintenance_timeout`` (integer)
---------------------------------
*\- (no description). Default:* ``60``

``meta`` (dict)
---------------
*\- (no description).*

``network_attempts`` (integer)
------------------------------
*\- (no description). Default:* ``60``

``network_timeout`` (integer)
-----------------------------
*\- (no description). Default:* ``10``

``notify`` (string)
-------------------
*\- (no description). Default:* ``""``

``operator`` (string)
---------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``regress`` (boolean)
---------------------
*\- (no description). Default:* ``False``

``send_status_period`` (integer)
--------------------------------
*\- (no description). Default:* ``10``

``strict_lock`` (boolean)
-------------------------
*\- (no description). Default:* ``False``

``target_lock_duration`` (string)
---------------------------------
*\- (no description). Default:* ``30m``

``task`` (string)
-----------------
*\- (no description). Default:* ``""``

``threads_timeout`` (integer)
-----------------------------
*\- (no description). Default:* ``60``

``token_file`` (string)
-----------------------
*\- (no description).*

``upload_token`` (string)
-------------------------
*\- (no description). Default:* ``None``

:dependencies:
 jobno
:nullable:
 True

``ver`` (string)
----------------
*\- (no description). Default:* ``""``

``writer_endpoint`` (string)
----------------------------
*\- (no description). Default:* ``""``

Influx
======

``address`` (string)
--------------------
*\- (no description). Default:* ``localhost``

``chunk_size`` (integer)
------------------------
*\- (no description). Default:* ``500000``

``database`` (string)
---------------------
*\- (no description). Default:* ``mydb``

``grafana_dashboard`` (string)
------------------------------
*\- (no description). Default:* ``tank-dashboard``

``grafana_root`` (string)
-------------------------
*\- (no description). Default:* ``http://localhost/``

``password`` (string)
---------------------
*\- (no description). Default:* ``root``

``port`` (integer)
------------------
*\- (no description). Default:* ``8086``

``tank_tag`` (string)
---------------------
*\- (no description). Default:* ``unknown``

``username`` (string)
---------------------
*\- (no description). Default:* ``root``

JMeter
======

``args`` (string)
-----------------
*\- (no description). Default:* ``""``

``buffer_size`` (integer)
-------------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``buffered_seconds`` (integer)
------------------------------
*\- (no description). Default:* ``3``

``exclude_markers`` (list of string)
------------------------------------
*\- (no description). Default:* ``[]``

:[list_element] (string):
 *\- (no description).*
 
 :empty:
  False

``ext_log`` (string)
--------------------
*\- (no description). Default:* ``none``

:one of: [``none``, ``errors``, ``all``]

``extended_log`` (string)
-------------------------
*\- (no description). Default:* ``none``

:one of: [``none``, ``errors``, ``all``]

``jmeter_path`` (string)
------------------------
*\- (no description). Default:* ``jmeter``

``jmeter_ver`` (float)
----------------------
*\- (no description). Default:* ``3.0``

``jmx`` (string)
----------------
*\- (no description).*

``shutdown_timeout`` (integer)
------------------------------
*\- (no description). Default:* ``10``

``variables`` (dict)
--------------------
*\- (no description). Default:* ``{}``

JsonReport
==========

``monitoring_log`` (string)
---------------------------
*\- (no description). Default:* ``monitoring.log``

``test_data_log`` (string)
--------------------------
*\- (no description). Default:* ``test_data.log``

Pandora
=======

``buffered_seconds`` (integer)
------------------------------
*\- (no description). Default:* ``2``

``config_content`` (dict)
-------------------------
*\- (no description). Default:* ``{}``

``config_file`` (string)
------------------------
*\- (no description). Default:* ``""``

``expvar`` (boolean)
--------------------
*\- (no description). Default:* ``True``

``pandora_cmd`` (string)
------------------------
*\- (no description). Default:* ``pandora``

Phantom
=======

``additional_libs`` (list of string)
------------------------------------
*\- Libs for Phantom, to be added to phantom config file in section "module_setup". Default:* ``[]``

:[list_element] (string):
 *\- (no description).*

``address`` (string)
--------------------
*\- Address of target. Format: [host]:port, [ipv4]:port, [ipv6]:port. Port is optional. Tank checks each test if port is available.* **Required.**

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
*\- Enable stpd\-file caching. Default:* ``True``

``writelog`` (string)
---------------------
*\- Enable verbose request/response logging. Default:* ``0``

:one of:
 :``0``: disable
 :``all``: all messages
 :``proto_error``: 5xx+network errors
 :``proto_warning``: 4xx+5xx+network errors

RCAssert
========

``fail_code`` (integer)
-----------------------
*\- (no description). Default:* ``10``

``pass`` (string)
-----------------
*\- (no description). Default:* ``""``

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

ShellExec
=========

``catch_out`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

``end`` (string)
----------------
*\- (no description). Default:* ``""``

``poll`` (string)
-----------------
*\- (no description). Default:* ``""``

``post_process`` (string)
-------------------------
*\- (no description). Default:* ``""``

``prepare`` (string)
--------------------
*\- (no description). Default:* ``""``

``start`` (string)
------------------
*\- (no description). Default:* ``""``

ShootExec
=========

``cmd`` (string)
----------------
*\- (no description).* **Required.**

``output_path`` (string)
------------------------
*\- (no description).* **Required.**

``stats_path`` (string)
-----------------------
*\- (no description). Default:* ``""``

Telegraf
========

``config_contents`` (string)
----------------------------
*\- (no description).*

``config`` (string)
-------------------
*\- (no description). Default:* ``auto``

``default_target`` (string)
---------------------------
*\- (no description). Default:* ``localhost``

``disguise_hostnames`` (boolean)
--------------------------------
*\- (no description). Default:* ``True``

``kill_old`` (boolean)
----------------------
*\- (no description). Default:* ``False``

``ssh_timeout`` (string)
------------------------
*\- (no description). Default:* ``5s``

TipsAndTricks
=============

``disable`` (boolean)
---------------------
*\- (no description). Default:* ``False``