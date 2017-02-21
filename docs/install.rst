============
Installation
============

.. note::

  Phantom load generator works fine with ``gcc<4.9``.

****************
Docker container
****************

`Install <https://www.docker.com/products/overview>`_ docker and use this command to run Yandex.Tank:

.. code-block:: bash

    docker run -v $(pwd):/var/loadtest -v $HOME/.ssh:/root/.ssh --net host -it direvius/yandex-tank

.. note::

  ``$HOME/.ssh`` is mounted in order for monitoring plugin to work. It uses your ssh keys to remotely login to monitored hosts

************************
Installation, from PyPi
************************

These are the packages that are required to build different python libraries. Install them with `apt`:

.. code-block:: bash

    sudo apt-get install python-pip build-essential python-dev libffi-dev gfortran libssl-dev

Update your pip:

.. code-block:: bash

    sudo -H pip install --upgrade pip

Update/install your setuptools:

.. code-block:: bash

    sudo -H pip install --upgrade setuptools

Install latest Yandex.Tank from master branch:

.. code-block:: bash

    sudo -H pip install https://api.github.com/repos/yandex/yandex-tank/tarball/master

You'll probably need Phantom load generator, so install it from our ppa:

.. code-block:: bash

    sudo add-apt-repository ppa:yandex-load/main && sudo apt-get update
    sudo apt-get install phantom phantom-ssl

****************************
Installation, .deb packages
****************************

.. note::
    
    **Deprecated**. Deb packages aren't renewed in PPA. 

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
