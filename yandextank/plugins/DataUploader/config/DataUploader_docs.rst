DataUploader
============

**jobno_file** (string)
-----------------------
*\- (no description). Default:* ``jobno_file.txt``

**network_timeout** (integer)
-----------------------------
*\- (no description). Default:* ``10``

**meta** (dict)
---------------
*\- (no description).*

**notify** (string)
-------------------
*\- (no description). Default:* 

**operator** (string)
---------------------
*\- (no description). Default:* ``None``

:nullable:
 True

**job_dsc** (string)
--------------------
*\- (no description). Default:* 

**ver** (string)
----------------
*\- (no description). Default:* 

**maintenance_timeout** (integer)
---------------------------------
*\- (no description). Default:* ``60``

**network_attempts** (integer)
------------------------------
*\- (no description). Default:* ``60``

**api_address** (string)
------------------------
*\- (no description). Default:* ``https://overload.yandex.net/``

**log_data_requests** (boolean)
-------------------------------
*\- (no description). Default:* ``False``

**api_attempts** (integer)
--------------------------
*\- (no description). Default:* ``60``

**jobno** (string)
------------------
*\- (no description).*

:dependencies:
 upload_token

**api_timeout** (integer)
-------------------------
*\- (no description). Default:* ``10``

**component** (string)
----------------------
*\- (no description). Default:* 

**lock_targets** (list or string)
---------------------------------
*\- targets to lock. Default:* ``auto``

:one of:
 :``auto``: automatically identify target host
 :``list_of_targets``: list of targets to lock

:tutorial_link:
 http://yandextank.readthedocs.io

**regress** (boolean)
---------------------
*\- (no description). Default:* ``False``

**token_file** (string)
-----------------------
*\- (no description).*

**log_monitoring_requests** (boolean)
-------------------------------------
*\- (no description). Default:* ``False``

**chunk_size** (integer)
------------------------
*\- (no description). Default:* ``500000``

**upload_token** (string)
-------------------------
*\- (no description). Default:* ``None``

:dependencies:
 jobno
:nullable:
 True

**connection_timeout** (integer)
--------------------------------
*\- (no description). Default:* ``30``

**log_other_requests** (boolean)
--------------------------------
*\- (no description). Default:* ``False``

**send_status_period** (integer)
--------------------------------
*\- (no description). Default:* ``10``

**task** (string)
-----------------
*\- (no description). Default:* 

**maintenance_attempts** (integer)
----------------------------------
*\- (no description). Default:* ``10``

**strict_lock** (boolean)
-------------------------
*\- (no description). Default:* ``False``

**writer_endpoint** (string)
----------------------------
*\- (no description). Default:* 

**job_name** (string)
---------------------
*\- (no description). Default:* ``none``

**log_status_requests** (boolean)
---------------------------------
*\- (no description). Default:* ``False``

**threads_timeout** (integer)
-----------------------------
*\- (no description). Default:* ``60``

**target_lock_duration** (string)
---------------------------------
*\- (no description). Default:* ``30m``

**ignore_target_lock** (boolean)
--------------------------------
*\- (no description). Default:* ``False``