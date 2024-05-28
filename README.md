# Yandex Tank [![Gitter](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/yandex/yandex-tank?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

### Yandextank has been moved to Python 3.
####[Latest stable release for Python 2 here](https://github.com/yandex/yandex-tank/releases/tag/Python2).
Yandex.Tank is an extensible open source load testing tool for advanced linux users which is especially good as a part of an automated load testing suite

![Quantiles chart example](https://raw.githubusercontent.com/yandex/yandex-tank/master/logos/screen.png)

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

## Documentation
- [Installation](http://yandextank.readthedocs.org/en/latest/install.html)

- Rest of [documentation](https://yandextank.readthedocs.org/en/latest/)

- [Stackoverflow](https://stackoverflow.com/) – use `load-testing` + `yandex` tags

## Get help
Chat with authors and other performance specialists: [![Gitter](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/yandex/yandex-tank?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

## See also
- [Overload𝛃](https://overload.yandex.net/) – performance analytics server

- Evgeniy Mamchits' [phantom](https://github.com/yandex-load/phantom) – phantom scalable IO engine

- [Vagrant environment](https://github.com/c3037/yandex-tank) with Yandex.Tank by Dmitry Porozhnyakov
