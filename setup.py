from setuptools import setup, find_packages

setup(
    name='yandextank',
    version='1.7.13',
    description='a performance measurement tool',
    longer_description='''
Yandex.Tank is a performance measurement and load testing automatization tool.
It uses other load generators such as JMeter, ab or phantom inside of it for
load generation and provides a common configuration system for them and
analytic tools for the results they produce.
''',
    maintainer='Alexey Lavrenuke (load testing)',
    maintainer_email='direvius@yandex-team.ru',
    url='http://yandex.github.io/yandex-tank/',
    packages=find_packages(exclude=["tests"]),
    install_requires=[
        'psutil',
        'ipaddr',
        'progressbar',
        'requests',
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
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    entry_points={
        'console_scripts': [
            'yandex-tank = yandextank.core.cli:main',
        ],
    },
    package_data={
        'yandextank.core': ['config/*'],
        'yandextank.plugins.GraphiteUploader': ['config/*'],
        'yandextank.plugins.JMeter': ['config/*'],
        'yandextank.plugins.Monitoring': ['config/*'],
        'yandextank.plugins.Phantom': ['config/*'],
        'yandextank.plugins.TipsAndTricks': ['config/*'],
    },
    use_2to3=True,
)
