============
Installation
============

****************
Docker container
****************

`Install <https://www.docker.com/products/overview>`_ docker and use ``direvius/yandex-tank`` (or, if you need jmeter, try ``direvius/yandex-tank:jmeter-latest``) container.
Default entrypoint is ``/usr/local/bin/yandex-tank`` so you may just run it to start test:

.. code-block:: bash

    docker run \
        -v $(pwd):/var/loadtest \
        -v $SSH_AUTH_SOCK:/ssh-agent -e SSH_AUTH_SOCK=/ssh-agent \
        --net host \
        -it direvius/yandex-tank


* ``$(pwd):/var/loadtest`` - current directory mounted to /var/loadtest in container to pass data for test
  (config file, monitoring config, ammo, etc)

* tank will use load.yaml from current directory as default config,
  append ``-c custom-config-name.yaml`` to run with other config

* you may pass other additional parameters for tank in run command, just append it after image name

* ``$SSH_AUTH_SOCK:/ssh-agent`` - ssh agent socket mounted in order to provide use telegraf plugin (monitoring). It uses your ssh keys to remotely login to monitored hosts

If you want to do something in the container before running tank, you will need to change entrypoint:

.. code-block:: bash

    docker run \
        -v $(pwd):/var/loadtest \
        -v $SSH_AUTH_SOCK:/ssh-agent -e SSH_AUTH_SOCK=/ssh-agent \
        --net host \
        -it \
        --entrypoint /bin/bash \
        direvius/yandex-tank

Start test Within container with yandex-tank command:

.. code-block:: bash

    yandex-tank -c config-name.yaml # default config is load.yaml


************************
Installation from PyPi
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
Installation .deb packages
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
