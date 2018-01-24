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

``report_file`` (string)
------------------------
*\- path to file to store autostop report. Default:* ``autostop_report.txt``

``autostop`` (list of string)
-----------------------------
*\- list of autostop constraints. Default:* ``[]``

:[list_element] (string):
 *\- autostop constraint.*
 
 :examples:
  :``http(4xx,50%,5)``:
   stop when rate of 4xx http codes is 50% or more during 5 seconds

:examples:
 :``[quantile(50,100,20), http(4xx,50%,5)]``:
  stop when either quantile 50% or 4xx http codes exceeds specified levels

BatteryHistorian
================

``device_id`` (string)
----------------------
*\- (no description). Default:* ``None``

:nullable:
 True

Bfg
===

``worker_type`` (string)
------------------------
*\- (no description). Default:* ``""``

``force_stepping`` (integer)
----------------------------
*\- (no description). Default:* ``0``

``gun_type`` (string)
---------------------
*\- (no description).* **Required.**

:one of: [``custom``, ``http``, ``scenario``, ``ultimate``]

``header_http`` (string)
------------------------
*\- (no description). Default:* ``1.0``

``file_cache`` (integer)
------------------------
*\- (no description). Default:* ``8192``

``ammofile`` (string)
---------------------
*\- (no description). Default:* ``""``

``instances`` (integer)
-----------------------
*\- (no description). Default:* ``1000``

``cache_dir`` (string)
----------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``address`` (string)
--------------------
*\- (no description).*

``pip`` (string)
----------------
*\- (no description). Default:* ``""``

``chosen_cases`` (string)
-------------------------
*\- (no description). Default:* ``""``

``ammo_type`` (string)
----------------------
*\- (no description). Default:* ``caseline``

``load_profile`` (dict)
-----------------------
*\- (no description).* **Required.**

:``load_type`` (string):
 *\- (no description).* **Required.**
 
 :regex:
  ^rps|instances|stpd_file$
:``schedule`` (string):
 *\- (no description).* **Required.**

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

``autocases`` (string)
----------------------
*\- (no description). Default:* ``0``

``cached_stpd`` (boolean)
-------------------------
*\- (no description). Default:* ``False``

``ammo_limit`` (integer)
------------------------
*\- (no description). Default:* ``-1``

``headers`` (string)
--------------------
*\- (no description). Default:* ``""``

``green_threads_per_instance`` (integer)
----------------------------------------
*\- (no description). Default:* ``1000``

``use_caching`` (boolean)
-------------------------
*\- (no description). Default:* ``True``

``enum_ammo`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

``uris`` (string)
-----------------
*\- (no description). Default:* ``""``

``loop`` (integer)
------------------
*\- (no description). Default:* ``-1``

Console
=======

``max_case_len`` (integer)
--------------------------
*\- max lenght of case name, longer names will be cut in console output. Default:* ``32``

``disable_all_colors`` (boolean)
--------------------------------
*\- disable colors in full output. Default:* ``False``

``info_panel_width`` (integer)
------------------------------
*\- width of right panel. Default:* ``33``

``sizes_max_spark`` (integer)
-----------------------------
*\- max length of sparkline for request/response sizes, 0 to disable. Default:* ``120``

``disable_colors`` (string)
---------------------------
*\- (no description). Default:* ``""``

``cases_max_spark`` (integer)
-----------------------------
*\- length of sparkline for each case, 0 to disable. Default:* ``120``

``times_max_spark`` (integer)
-----------------------------
*\- max length of sparkline for fractions of request time, 0 to disable. Default:* ``120``

``short_only`` (boolean)
------------------------
*\- do not draw full console screen, write short info for each second. Default:* ``False``

``cases_sort_by`` (string)
--------------------------
*\- field for cases data sort. Default:* ``count``

:one of: [``count``, ``net_err``, ``http_err``]

DataUploader
============

``jobno_file`` (string)
-----------------------
*\- (no description). Default:* ``jobno_file.txt``

``network_timeout`` (integer)
-----------------------------
*\- (no description). Default:* ``10``

``meta`` (dict)
---------------
*\- (no description).*

``notify`` (string)
-------------------
*\- (no description). Default:* ``""``

``operator`` (string)
---------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``job_dsc`` (string)
--------------------
*\- (no description). Default:* ``""``

``ver`` (string)
----------------
*\- (no description). Default:* ``""``

``maintenance_timeout`` (integer)
---------------------------------
*\- (no description). Default:* ``60``

``network_attempts`` (integer)
------------------------------
*\- (no description). Default:* ``60``

``api_address`` (string)
------------------------
*\- (no description). Default:* ``https://overload.yandex.net/``

``log_data_requests`` (boolean)
-------------------------------
*\- (no description). Default:* ``False``

``api_attempts`` (integer)
--------------------------
*\- (no description). Default:* ``60``

``jobno`` (string)
------------------
*\- (no description).*

:dependencies:
 upload_token

``api_timeout`` (integer)
-------------------------
*\- (no description). Default:* ``10``

``component`` (string)
----------------------
*\- (no description). Default:* ``""``

``lock_targets`` (list or string)
---------------------------------
*\- targets to lock. Default:* ``auto``

:one of:
 :``auto``: automatically identify target host
 :``list_of_targets``: list of targets to lock

:tutorial_link:
 http://yandextank.readthedocs.io

``regress`` (boolean)
---------------------
*\- (no description). Default:* ``False``

``token_file`` (string)
-----------------------
*\- (no description).*

``log_monitoring_requests`` (boolean)
-------------------------------------
*\- (no description). Default:* ``False``

``chunk_size`` (integer)
------------------------
*\- (no description). Default:* ``500000``

``upload_token`` (string)
-------------------------
*\- (no description). Default:* ``None``

:dependencies:
 jobno
:nullable:
 True

``connection_timeout`` (integer)
--------------------------------
*\- (no description). Default:* ``30``

``log_other_requests`` (boolean)
--------------------------------
*\- (no description). Default:* ``False``

``send_status_period`` (integer)
--------------------------------
*\- (no description). Default:* ``10``

``task`` (string)
-----------------
*\- (no description). Default:* ``""``

``maintenance_attempts`` (integer)
----------------------------------
*\- (no description). Default:* ``10``

``strict_lock`` (boolean)
-------------------------
*\- (no description). Default:* ``False``

``writer_endpoint`` (string)
----------------------------
*\- (no description). Default:* ``""``

``job_name`` (string)
---------------------
*\- (no description). Default:* ``none``

``log_status_requests`` (boolean)
---------------------------------
*\- (no description). Default:* ``False``

``threads_timeout`` (integer)
-----------------------------
*\- (no description). Default:* ``60``

``target_lock_duration`` (string)
---------------------------------
*\- (no description). Default:* ``30m``

``ignore_target_lock`` (boolean)
--------------------------------
*\- (no description). Default:* ``False``

Influx
======

``username`` (string)
---------------------
*\- (no description). Default:* ``root``

``tank_tag`` (string)
---------------------
*\- (no description). Default:* ``unknown``

``password`` (string)
---------------------
*\- (no description). Default:* ``root``

``database`` (string)
---------------------
*\- (no description). Default:* ``mydb``

``address`` (string)
--------------------
*\- (no description). Default:* ``localhost``

``chunk_size`` (integer)
------------------------
*\- (no description). Default:* ``500000``

``grafana_dashboard`` (string)
------------------------------
*\- (no description). Default:* ``tank-dashboard``

``grafana_root`` (string)
-------------------------
*\- (no description). Default:* ``http://localhost/``

``port`` (integer)
------------------
*\- (no description). Default:* ``8086``

JMeter
======

``jmx`` (string)
----------------
*\- (no description).*

``ext_log`` (string)
--------------------
*\- (no description). Default:* ``none``

:one of: [``none``, ``errors``, ``all``]

``variables`` (dict)
--------------------
*\- (no description). Default:* ``{}``

``args`` (string)
-----------------
*\- (no description). Default:* ``""``

``extended_log`` (string)
-------------------------
*\- (no description). Default:* ``none``

:one of: [``none``, ``errors``, ``all``]

``exclude_markers`` (list of string)
------------------------------------
*\- (no description). Default:* ``[]``

:[list_element] (string):
 *\- (no description).*
 
 :empty:
  False

``jmeter_ver`` (float)
----------------------
*\- (no description). Default:* ``3.0``

``shutdown_timeout`` (integer)
------------------------------
*\- (no description). Default:* ``10``

``buffer_size`` (integer)
-------------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``buffered_seconds`` (integer)
------------------------------
*\- (no description). Default:* ``3``

``jmeter_path`` (string)
------------------------
*\- (no description). Default:* ``jmeter``

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

``config_content`` (dict)
-------------------------
*\- (no description). Default:* ``{}``

``buffered_seconds`` (integer)
------------------------------
*\- (no description). Default:* ``2``

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

``phantom_http_field_num`` (string)
-----------------------------------
*\- (no description). Default:* ``""``

``header_http`` (string)
------------------------
*\- (no description). Default:* ``1.0``

``address`` (string)
--------------------
*\- (no description).* **Required.**

``phout_file`` (string)
-----------------------
*\- (no description). Default:* ``""``

``instances`` (integer)
-----------------------
*\- (no description). Default:* ``1000``

``source_log_prefix`` (string)
------------------------------
*\- (no description). Default:* ``""``

``gatling_ip`` (string)
-----------------------
*\- (no description). Default:* ``""``

``phantom_path`` (string)
-------------------------
*\- (no description). Default:* ``phantom``

``port`` (string)
-----------------
*\- (no description). Default:* ``""``

:regex:
 \d{0,5}

``client_key`` (string)
-----------------------
*\- (no description). Default:* ``""``

``connection_test`` (boolean)
-----------------------------
*\- (no description). Default:* ``True``

``affinity`` (string)
---------------------
*\- (no description). Default:* ``""``

``config`` (string)
-------------------
*\- (no description). Default:* ``""``

``uris`` (string)
-----------------
*\- (no description). Default:* ``""``

``additional_libs`` (string)
----------------------------
*\- (no description). Default:* ``""``

``force_stepping`` (integer)
----------------------------
*\- (no description). Default:* ``0``

``phantom_http_field`` (string)
-------------------------------
*\- (no description). Default:* ``""``

``writelog`` (string)
---------------------
*\- (no description). Default:* ``none``

``phantom_modules_path`` (string)
---------------------------------
*\- (no description). Default:* ``/usr/lib/phantom``

``ammo_type`` (string)
----------------------
*\- (no description). Default:* ``phantom``

``autocases`` (string)
----------------------
*\- (no description). Default:* ``0``

``method_options`` (string)
---------------------------
*\- (no description). Default:* ``""``

``cache_dir`` (string)
----------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``threads`` (integer)
---------------------
*\- (no description). Default:* ``None``

:nullable:
 True

``method_prefix`` (string)
--------------------------
*\- (no description). Default:* ``method_stream``

``file_cache`` (integer)
------------------------
*\- (no description). Default:* ``8192``

``chosen_cases`` (string)
-------------------------
*\- (no description). Default:* ``""``

``phantom_http_entity`` (string)
--------------------------------
*\- (no description). Default:* ``""``

``ammofile`` (string)
---------------------
*\- (no description). Default:* ``""``

``load_profile`` (dict)
-----------------------
*\- (no description).* **Required.**

:``load_type`` (string):
 *\- (no description).*
 
 :one of:
  :``instances``: fix number of instances
  :``rps``: fix rps rate
  :``stpd_file``: use ready schedule file
:``schedule`` (string):
 *\- load schedule or path to stpd file.* **Required.**
 
 :examples:
  :``const(200,90s)``:
   constant load of 200 instances/rps during 90s
  :``line(100,200,10m)``:
   linear growth from 100 to 200 instances/rps during 10 minutes
  :``test_dir/test_backend.stpd``:
   path to ready schedule file

``ssl`` (boolean)
-----------------
*\- (no description). Default:* ``False``

``phantom_http_line`` (string)
------------------------------
*\- (no description). Default:* ``""``

``multi`` (list of )
--------------------
*\- (no description). Default:* ``[]``

:[list_element] ():
 *\- (no description).*
 
 :additional_libs:
  :default:
   
  :type:
   string
 :address:
  :required:
   True
  :type:
   string
 :affinity:
  :default:
   
  :type:
   string
 :ammo_limit:
  :default:
   -1
  :type:
   integer
 :ammo_type:
  :default:
   phantom
  :type:
   string
 :ammofile:
  :default:
   
  :type:
   string
 :autocases:
  :default:
   0
  :type:
   string
 :buffered_seconds:
  :default:
   2
  :type:
   integer
 :cache_dir:
  :default:
   None
  :nullable:
   True
  :type:
   string
 :chosen_cases:
  :default:
   
  :type:
   string
 :client_certificate:
  :default:
   
  :type:
   string
 :client_cipher_suites:
  :default:
   
  :type:
   string
 :client_key:
  :default:
   
  :type:
   string
 :config:
  :default:
   
  :type:
   string
 :connection_test:
  :default:
   True
  :type:
   boolean
 :enum_ammo:
  :default:
   False
  :type:
   boolean
 :file_cache:
  :default:
   8192
  :type:
   integer
 :force_stepping:
  :default:
   0
  :type:
   integer
 :gatling_ip:
  :default:
   
  :type:
   string
 :header_http:
  :default:
   1.0
  :type:
   string
 :headers:
  :default:
   
  :type:
   string
 :instances:
  :default:
   1000
  :type:
   integer
 :load_profile:
  :required:
   True
  :schema:
   :load_type:
    :allowed:
     - rps
     - instances
     - stpd_file
    :type:
     string
    :values_description:
     :instances:
      fix number of instances
     :rps:
      fix rps rate
     :stpd_file:
      use ready schedule file
   :schedule:
    :description:
     load schedule or path to stpd file
    :examples:
     :const(200,90s):
      constant load of 200 instances/rps during 90s
     :line(100,200,10m):
      linear growth from 100 to 200 instances/rps during 10 minutes
     :test_dir/test_backend.stpd:
      path to ready schedule file
    :required:
     True
    :type:
     string
  :type:
   dict
 :loop:
  :default:
   -1
  :type:
   integer
 :method_options:
  :default:
   
  :type:
   string
 :method_prefix:
  :default:
   method_stream
  :type:
   string
 :phantom_http_entity:
  :default:
   
  :type:
   string
 :phantom_http_field:
  :default:
   
  :type:
   string
 :phantom_http_field_num:
  :default:
   
  :type:
   string
 :phantom_http_line:
  :default:
   
  :type:
   string
 :phantom_modules_path:
  :default:
   /usr/lib/phantom
  :type:
   string
 :phantom_path:
  :default:
   phantom
  :type:
   string
 :phout_file:
  :default:
   
  :type:
   string
 :port:
  :default:
   
  :regex:
   \d{0,5}
  :type:
   string
 :source_log_prefix:
  :default:
   
  :type:
   string
 :ssl:
  :default:
   False
  :type:
   boolean
 :tank_type:
  :default:
   http
  :type:
   string
 :threads:
  :default:
   None
  :nullable:
   True
  :type:
   integer
 :timeout:
  :default:
   11s
  :type:
   string
 :uris:
  :default:
   
  :type:
   string
 :use_caching:
  :default:
   True
  :type:
   boolean
 :writelog:
  :default:
   none
  :type:
   string

:allow_unknown:
 True

``tank_type`` (string)
----------------------
*\- (no description). Default:* ``http``

``ammo_limit`` (integer)
------------------------
*\- (no description). Default:* ``-1``

``headers`` (string)
--------------------
*\- (no description). Default:* ``""``

``client_cipher_suites`` (string)
---------------------------------
*\- (no description). Default:* ``""``

``timeout`` (string)
--------------------
*\- (no description). Default:* ``11s``

``use_caching`` (boolean)
-------------------------
*\- (no description). Default:* ``True``

``enum_ammo`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

``buffered_seconds`` (integer)
------------------------------
*\- (no description). Default:* ``2``

``loop`` (integer)
------------------
*\- (no description). Default:* ``-1``

``client_certificate`` (string)
-------------------------------
*\- (no description). Default:* ``""``

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

``mem_limit`` (integer)
-----------------------
*\- (no description). Default:* ``512``

``interval`` (string)
---------------------
*\- (no description). Default:* ``10s``

``disk_limit`` (integer)
------------------------
*\- (no description). Default:* ``2048``

ShellExec
=========

``start`` (string)
------------------
*\- (no description). Default:* ``""``

``end`` (string)
----------------
*\- (no description). Default:* ``""``

``prepare`` (string)
--------------------
*\- (no description). Default:* ``""``

``post_process`` (string)
-------------------------
*\- (no description). Default:* ``""``

``poll`` (string)
-----------------
*\- (no description). Default:* ``""``

``catch_out`` (boolean)
-----------------------
*\- (no description). Default:* ``False``

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

``kill_old`` (boolean)
----------------------
*\- (no description). Default:* ``False``

``default_target`` (string)
---------------------------
*\- (no description). Default:* ``localhost``

``ssh_timeout`` (string)
------------------------
*\- (no description). Default:* ``5s``

``config_contents`` (string)
----------------------------
*\- (no description).*

``disguise_hostnames`` (boolean)
--------------------------------
*\- (no description). Default:* ``True``

``config`` (string)
-------------------
*\- (no description). Default:* ``auto``

TipsAndTricks
=============

``disable`` (boolean)
---------------------
*\- (no description). Default:* ``False``