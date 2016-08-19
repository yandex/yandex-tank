# Yandex Tank [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/yandex/yandex-tank?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

[![Build Status](https://secure.travis-ci.org/yandex/yandex-tank.png?branch=master)](http://travis-ci.org/yandex/yandex-tank)

![Quantiles chart example](/logos/screen.png)

## Description
Yandex.Tank is an extensible open source load testing tool for advanced linux users which is especially good as a part of an automated load testing suite.

## Main features
* different load generators supported:
  * Evgeniy Mamchits' [phantom](https://github.com/yandex-load/phantom) is a very fast (100 000+ RPS) shooter written in C++ (default)
  * [JMeter](http://jmeter.apache.org/) is an extendable and widely known one
  * BFG is a Python-based generator that allows you to write your load scenarios in Python
  * experimental Golang generator: [pandora](https://github.com/yandex/pandora)
* performance analytics backend service: [Overload](http://overload.yandex.net/). Store and analyze your test results online
* several ammo formats supported like plain url list or access.log
* test autostop plugin: stop your test when the results have became obvious and save time
* customizable and extendable monitoring that works over SSH

## Installation and configuration
Installation at [ReadTheDocs](http://yandextank.readthedocs.org/en/latest/install.html).

## Get help
Chat with authors and other performance specialists: [![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/yandex/yandex-tank?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

Documentation at [ReadTheDocs](https://yandextank.readthedocs.org/en/latest/).

Ask your questions at [Stackoverflow](https://stackoverflow.com/), use "load-testing" + "yandex" tags.

## See also
[Overload𝛃](https://overload.yandex.net/) - performance analytics server.

Evgeniy Mamchits' [phantom](https://github.com/yandex-load/phantom) – Phantom scalable IO Engine.

[BlazeMeter Sense](https://sense.blazemeter.com) - Performance Testing Analytics by BlazeMeter. Currently only with [1.7](https://github.com/yandex/yandex-tank/tree/v1.7.32) branch

![Yandex.Metrics counter](https://mc.yandex.ru/watch/17743264)
