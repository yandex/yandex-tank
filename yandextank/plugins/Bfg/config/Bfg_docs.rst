Bfg
===

**worker_type** (string)
------------------------
*\- (no description). Default:* 

**force_stepping** (integer)
----------------------------
*\- (no description). Default:* ``0``

**gun_type** (string)
---------------------
*\- (no description).* **Required.**

:one of: [``custom``, ``http``, ``scenario``, ``ultimate``]

**header_http** (string)
------------------------
*\- (no description). Default:* ``1.0``

**file_cache** (integer)
------------------------
*\- (no description). Default:* ``8192``

**ammofile** (string)
---------------------
*\- (no description). Default:* 

**instances** (integer)
-----------------------
*\- (no description). Default:* ``1000``

**cache_dir** (string)
----------------------
*\- (no description). Default:* ``None``

:nullable:
 True

**address** (string)
--------------------
*\- (no description).*

**pip** (string)
----------------
*\- (no description). Default:* 

**chosen_cases** (string)
-------------------------
*\- (no description). Default:* 

**ammo_type** (string)
----------------------
*\- (no description). Default:* ``caseline``

**load_profile** (dict)
-----------------------
*\- (no description).* **Required.**

:load_type (string):
 *\- (no description).* **Required.**
 
 :regex:
  ^rps|instances|stpd_file$
:schedule (string):
 *\- (no description).* **Required.**

**gun_config** (dict)
---------------------
*\- (no description).*

:base_address (string):
 *\- (no description).*
:class_name (string):
 *\- (no description). Default:* ``LoadTest``
:init_param (string):
 *\- (no description). Default:*
:module_name (string):
 *\- (no description).*
:module_path (string):
 *\- (no description). Default:*

:allow_unknown:
 True

**autocases** (string)
----------------------
*\- (no description). Default:* ``0``

**cached_stpd** (boolean)
-------------------------
*\- (no description). Default:* ``False``

**ammo_limit** (integer)
------------------------
*\- (no description). Default:* ``-1``

**headers** (string)
--------------------
*\- (no description). Default:* 

**green_threads_per_instance** (integer)
----------------------------------------
*\- (no description). Default:* ``1000``

**use_caching** (boolean)
-------------------------
*\- (no description). Default:* ``True``

**enum_ammo** (boolean)
-----------------------
*\- (no description). Default:* ``False``

**uris** (string)
-----------------
*\- (no description). Default:* 

**loop** (integer)
------------------
*\- (no description). Default:* ``-1``