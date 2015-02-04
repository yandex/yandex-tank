#!/usr/bin/env python

from setuptools import setup, find_packages

setup(
    name='yandextank',
    version='1.6.8',
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
        'tornado',
        'pyjade',
        'tornadio2',
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
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
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
    data_files=[
        ('/etc/yandex-tank', ['config/00-base.ini'])
    ]
)
