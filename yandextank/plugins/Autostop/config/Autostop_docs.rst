Autostop
========

**report_file** (string)
------------------------
*\- path to file to store autostop report. Default:* ``autostop_report.txt``

**autostop** (list of string)
-----------------------------
*\- list of autostop constraints. Default:* ``[]``

:[list_element] (string):
 *\- autostop constraint,.*
 
 :examples:
  :``http(4xx,50%,5)``:
   stop when rate of 4xx http codes is 50% or more during 5 seconds

:examples:
 :``[quantile(50,100,20), http(4xx,50%,5)]``:
  stop when either quantile 50% or 4xx http codes exceeds specified levels