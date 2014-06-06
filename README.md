# Yandex Tank

![Quantiles chart example](/logos/screen.png)

## Description
Yandex.Tank is an extendable open source load testing tool for advanced linux users which is especially good as a part of automated load testing suit.

## Main features
* different load generators supported:
  * Evgeniy Mamchits' [phantom](https://github.com/mamchits/phantom) is a very fast (100 000+ RPS) shooter written in C++ (default)
  * [JMeter](http://jmeter.apache.org/) is an extendable and widely known one
  * BFG is an experimental Python-based generator (included) allows you to write your own shooter function
* customizable reports in .html with pretty interactive charts based on [highcharts](http://www.highcharts.com/) library
* [graphite](https://graphite.readthedocs.org/en/latest/overview.html) support
* several ammo formats supported like plain url list or access.log
* test autostop plugin
* customizable and extendable monitoring that works over SSH


## Get help
Documentation at [ReadTheDocs](https://yandextank.readthedocs.org/en/latest/)

Ask your questions at [Stackoverflow](https://stackoverflow.com/), use "load testing" + "yandex" tags.

## See also
Evgeniy Mamchits' [phantom](https://github.com/mamchits/phantom) - Phantom scalable IO Engine

Andrey Pohilko's [loadosophia](https://loadosophia.org/) - service for storing and analysing performance test results

[Jenkins](https://jenkins-ci.org/) - an extendable open source continuous integration server that may be used to automate test execution.

[Graphite](https://graphite.readthedocs.org/en/latest/overview.html) - an enterprise-scale monitoring tool, use it to store your test results and render graphs.

![Yandex.Metrics counter](https://mc.yandex.ru/watch/17743264)
