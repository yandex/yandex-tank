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

``short_only`` (boolean)
------------------------
*\- (no description). Default:* ``False``

``info_panel_width`` (integer)
------------------------------
*\- (no description). Default:* ``33``

``disable_all_colors`` (boolean)
--------------------------------
*\- (no description). Default:* ``False``

``disable_colors`` (string)
---------------------------
*\- (no description). Default:* ``""``

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

``tank_tag`` (string)
---------------------
*\- (no description). Default:* ``unknown``

``grafana_root`` (string)
-------------------------
*\- (no description). Default:* ``http://localhost/``

``address`` (string)
--------------------
*\- (no description). Default:* ``localhost``

``grafana_dashboard`` (string)
------------------------------
*\- (no description). Default:* ``tank-dashboard``

``chunk_size`` (integer)
------------------------
*\- (no description). Default:* ``500000``

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