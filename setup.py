from setuptools import setup, find_packages

setup(
    name='yandextank',
    version='1.9.3',
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
    namespace_packages=["yandextank", "yandextank.plugins"],
    packages=find_packages(exclude=["tests", "tmp", "docs", "data"]),
    install_requires=[
        'psutil>=1.2.1', 'requests>=2.5.1', 'paramiko>=1.16.0',
        'pandas>=0.18.0', 'numpy>=1.11.0', 'future>=0.16.0',
        'pip>=8.1.2',
        'matplotlib>=1.5.3', 'seaborn>=0.7.1',
        'pyyaml>=3.12', 'cerberus>=1.1'
    ],
    setup_requires=[
        'pytest-runner', 'flake8',
    ],
    tests_require=[
        'pytest',
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
            'yandex-tank-check-ssh = yandextank.common.util:check_ssh_connection',
            'tank-postloader = yandextank.plugins.DataUploader.cli:post_loader'
        ],
    },
    package_data={
        'yandextank.api': ['config/*'],
        'yandextank.core': ['config/*'],
        'yandextank.plugins.Aggregator': ['config/*'],
        'yandextank.plugins.Android': ['binary/*', 'config/*'],
        'yandextank.plugins.Appium': ['config/*'],
        'yandextank.plugins.Autostop': ['config/*'],
        'yandextank.plugins.BatteryHistorian': ['config/*'],
        'yandextank.plugins.Bfg': ['config/*'],
        'yandextank.plugins.Console': ['config/*'],
        'yandextank.plugins.DataUploader': ['config/*'],
        'yandextank.plugins.GraphiteUploader': ['config/*'],
        'yandextank.plugins.Influx': ['config/*'],
        'yandextank.plugins.JMeter': ['config/*'],
        'yandextank.plugins.JsonReport': ['config/*'],
        'yandextank.plugins.Monitoring': ['config/*'],
        'yandextank.plugins.Pandora': ['config/*'],
        'yandextank.plugins.Phantom': ['config/*'],
        'yandextank.plugins.RCAssert': ['config/*'],
        'yandextank.plugins.ResourceCheck': ['config/*'],
        'yandextank.plugins.ShellExec': ['config/*'],
        'yandextank.plugins.ShootExec': ['config/*'],
        'yandextank.plugins.Telegraf': ['config/*'],
        'yandextank.plugins.TipsAndTricks': ['config/*'],
    },
    use_2to3=False, )
