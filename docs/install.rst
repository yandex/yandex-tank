============
Installation
============

************************
Installation, from PyPi
************************

You will need some packages that are required for building different python libraries:

.. code-block:: bash

    libxml2-dev libxslt1-dev python-dev zlib1g-dev

You will also need a GNU make for building them. In Ubuntu you can install a build-essential package. You should also install pip if you don't have it. Full command for Ubuntu looks like this:

.. code-block:: bash

    sudo apt-get install python-pip build-essential libxml2-dev libxslt1-dev python-dev zlib1g-dev

You can do similar thing for your distribution. After you've installed all the packages, it is easy to install the Tank itself:

.. code-block:: bash

    sudo pip install yandextank

Remember that if you want to use phantom as a load generator you should install it separately. On Ubuntu you can do that by adding our PPA and installing phantom and phantom-ssl packages. On other distros you will maybe need to build it from sources.

.. code-block:: bash

    sudo add-apt-repository ppa:yandex-load/main && sudo apt-get update
    sudo apt-get install phantom phantom-ssl

Report plugin is a distinct project. You can found it `here via github <https://github.com/yandex-load/yatank-online>`_

****************************
Installation, .deb packages
****************************

You should add proper repositories on Debian-based environment.

For instance, add following repos to ``sources.list`` :

.. code-block:: bash

    deb http://ppa.launchpad.net/yandex-load/main/ubuntu trusty main
    deb-src http://ppa.launchpad.net/yandex-load/main/ubuntu trusty main

or this way

.. code-block:: bash

    sudo apt-get install python-software-properties
    sudo apt-get install software-properties-common
    sudo add-apt-repository ppa:yandex-load/main

Then update package list and install ``yandex-tank`` package:

.. code-block:: bash

    sudo apt-get update && sudo apt-get install yandex-tank
