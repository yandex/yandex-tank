#!/usr/bin/env python

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup, find_packages

setup(
    name='yandextank',
    version='1.7.0',
    description='a performance measurement tool',
    longer_description='''
Yandex.Tank is a performance measurement and load testing automatization tool.
It uses other load generators such as JMeter, ab or phantom inside of it for
load generation and provides a common configuration system for them and
analytic tools for the results they produce.
''',
    maintainer='Alexey Lavrenuke',
    maintainer_email='direvius@gmail.com',
    url='http://yandex.github.io/yandex-tank/',
    packages=find_packages(),
    install_requires=[
        'psutil',
        'ipaddr',
        'lxml',
        'progressbar',
    ],
    license='LGPLv2',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Lesser General Public License v2 or later (LGPLv2+)',
        'Operating System :: POSIX',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing',
        'Topic :: Software Development :: Testing :: Traffic Generation',
    ],
    entry_points={
        'console_scripts': [
            'yandex-tank = yandextank.core.cli:main',
        ],
    },
    package_data={},
    # TODO: move them all to resources maybe
    data_files=[
        ('/etc/yandex-tank', [
            'config/00-base.ini',
        ]),
        ('/etc/yandex-tank/JMeter', [
            'config/JMeter/jmeter_argentum.xml',
            'config/JMeter/jmeter_var_template.xml',
            'config/JMeter/jmeter_writer.xml',
        ]),
        ('/etc/yandex-tank/GraphiteUploader', [
            'config/GraphiteUploader/graphite-js.tpl',
            'config/GraphiteUploader/graphite.tpl',
        ]),
        ('/etc/yandex-tank/Monitoring', [
            'config/Monitoring/agent.cfg',
            'config/Monitoring/monitoring_default_config.xml',
        ]),
        ('/etc/yandex-tank/Phantom', [
            'config/Phantom/phantom.conf.tpl',
            'config/Phantom/phantom_benchmark_additional.tpl',
            'config/Phantom/phantom_benchmark_main.tpl',
        ]),
        ('/etc/yandex-tank/TipsAndTricks', [
            'config/TipsAndTricks/tips.txt',
        ]),
        ('/etc/bash_completion.d', [
            'data/yandex-tank.completion'
        ]),
    ]
)
