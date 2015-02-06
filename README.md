
# Yandex Tank
[![Gitter](https://badges.gitter.im/Join Chat.svg)](https://gitter.im/yandex/yandex-tank?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

[![Build Status](https://secure.travis-ci.org/yandex/yandex-tank.png?branch=master)](http://travis-ci.org/yandex/yandex-tank)

![Quantiles chart example](/logos/screen.png)

## Description
Yandex.Tank is an extendable open source load testing tool for advanced linux users which is especially good as a part of automated load testing suit.

## Main features
* different load generators supported:
  * Evgeniy Mamchits' [phantom](https://github.com/mamchits/phantom) is a very fast (100 000+ RPS) shooter written in C++ (default)
  * [JMeter](http://jmeter.apache.org/) is an extendable and widely known one
  * BFG is an experimental Python-based generator that allows you to write your own shooter function (included)
* customizable reports in .html with pretty interactive charts based on [highcharts](http://www.highcharts.com/) library
* [graphite](https://graphite.readthedocs.org/en/latest/overview.html) support
* several ammo formats supported like plain url list or access.log
* test autostop plugin
* customizable and extendable monitoring that works over SSH

## Install from PyPI
You will need some packages that are required for building different python libraries:
```
libxml2-dev libxslt1-dev python-dev zlib1g-dev
```
You will also need a GNU make for building them. In Ubuntu you can install a ```build-essential``` package. You should also install pip if you don't have it.
Full command for Ubuntu looks like this:
```
sudo apt-get install python-pip build-essential libxml2-dev libxslt1-dev python-dev zlib1g-dev
```
You can do similar thing for your distribution. After you've installed all the packages, it is easy to install the Tank itself:
```
sudo pip install yandextank
```
Remember that if you want to use ```phantom``` as a load generator you should install it separately. On Ubuntu you can do that by adding our PPA and installing ```phantom``` and ```phantom-ssl``` packages. On other distros you will maybe need to build it from sources.
```
sudo add-apt-repository ppa:yandex-load/main && sudo apt-get update
sudo apt-get install phantom phantom-ssl
```

## Get help
Documentation at [ReadTheDocs](https://yandextank.readthedocs.org/en/latest/)

Ask your questions at [Stackoverflow](https://stackoverflow.com/), use "load testing" + "yandex" tags.

## See also
Evgeniy Mamchits' [phantom](https://github.com/mamchits/phantom) - Phantom scalable IO Engine

Andrey Pohilko's [loadosophia](https://loadosophia.org/) - service for storing and analysing performance test results

[Jenkins](https://jenkins-ci.org/) - an extendable open source continuous integration server that may be used to automate test execution.

[Graphite](https://graphite.readthedocs.org/en/latest/overview.html) - an enterprise-scale monitoring tool, use it to store your test results and render graphs.

![Yandex.Metrics counter](https://mc.yandex.ru/watch/17743264)
