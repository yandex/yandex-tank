Getting started
=================

Welcome to Yandex.Tank documentation. Yandex.Tank is an extensible load testing utility for unix systems. It is written in Python and uses different load generator modules in different languages.

Getting Help
-------------
`Gitter.im <https://gitter.im/yandex/yandex-tank>`_

What are the Yandex.Tank components?
-------------------------------------
* ``Core`` - basic steps of test prepare, configuration, execution. Artifacts storing. Controls plugins/modules.
* ``Load generators`` -  modules that uses and controls load generators (load generators NOT included).
* ``Artifact uploaders`` - modules that uploads artifacts to external storages and services. 
* ``Handy tools`` - monitoring tools, console online screen, autostops and so on.

.. note::
  Using ``phantom`` as a load generator for mild load tests (less then 1000rps) an average laptop with 64bit Ubuntu (10.04/.../13.10) would be sufficient. The tank could be easily used in virtual machine if queries aren't too heavy and load isn't too big. Otherwise it is recommended to request a physical server or a more capable virtual machine from your admin.

Running Yandex.Tank
-------------------
1.Install tank to your system :doc:`install`

2.Tune your system :doc:`generator_tuning`

3.And run the tutorial :doc:`tutorial`

----------

4.If you are skilled enough, feel free to use :doc:`configuration`.

5.For developers :doc:`core_and_modules`.


See also
--------

Evgeniy Mamchits' `phantom <https://github.com/mamchits/phantom>`_ -
Phantom scalable IO Engine

Alexey Lavrenuke's `pandora <https://github.com/yandex/pandora>`_ -
A load generator in Go language

Gregory Komissarov's
`firebat <https://github.com/greggyNapalm/firebat-console>`_ - test tool
based on Phantom

BlazeMeter's `Sense <http://sense.blazemeter.com/>`_ - service for
storing and analysing performance test results
