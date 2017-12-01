jobno_file
==========
:default:
 jobno_file.txt

:type:
 string

network_timeout
===============
:default:
 10

:type:
 integer

meta
====
:required:
 False

:type:
 dict

notify
======
:default:
 

:type:
 string

operator
========
:default:
 None

:nullable:
 True
:type:
 string

job_dsc
=======
:default:
 

:type:
 string

ver
===
:default:
 

:type:
 string

maintenance_timeout
===================
:default:
 60

:type:
 integer

network_attempts
================
:default:
 60

:type:
 integer

api_address
===========
:default:
 https://overload.yandex.net/

:type:
 string

log_data_requests
=================
:default:
 False

:type:
 boolean

api_attempts
============
:default:
 60

:type:
 integer

jobno
=====
:required:
 False

:dependencies:
 upload_token
:type:
 string

api_timeout
===========
:default:
 10

:type:
 integer

component
=========
:default:
 

:type:
 string

lock_targets
============
:default:
 auto

:anyof:
 - :type:
    list
 - :allowed:
    - auto
   :type:
    string

regress
=======
:default:
 False

:type:
 boolean

token_file
==========
:required:
 False

:type:
 string

log_monitoring_requests
=======================
:default:
 False

:type:
 boolean

chunk_size
==========
:default:
 500000

:type:
 integer

upload_token
============
:default:
 None

:dependencies:
 jobno
:nullable:
 True
:type:
 string

connection_timeout
==================
:default:
 30

:type:
 integer

log_other_requests
==================
:default:
 False

:type:
 boolean

send_status_period
==================
:default:
 10

:type:
 integer

task
====
:default:
 

:type:
 string

maintenance_attempts
====================
:default:
 10

:type:
 integer

strict_lock
===========
:default:
 False

:type:
 boolean

writer_endpoint
===============
:default:
 

:type:
 string

job_name
========
:default:
 none

:type:
 string

log_status_requests
===================
:default:
 False

:type:
 boolean

threads_timeout
===============
:default:
 60

:type:
 integer

target_lock_duration
====================
:default:
 30m

:type:
 string

ignore_target_lock
==================
:default:
 False

:type:
 boolean
