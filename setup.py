from setuptools import setup, find_packages
from yandextank.version import VERSION

setup(
    name='yandextank',
    version=VERSION,
    description='a performance measurement tool',
    longer_description='''
Yandex.Tank is a performance measurement and load testing automatization tool.
It uses other load generators such as JMeter, ab or phantom inside of it for
load generation and provides a common configuration system for them and
analytic tools for the results they produce.
''',
    python_requires='==3.*',
    maintainer='Yandex Load Team',
    maintainer_email='load@yandex-team.ru',
    url='http://yandex.github.io/yandex-tank/',
    namespace_packages=["yandextank", "yandextank.plugins"],
    packages=find_packages(exclude=["tests", "tmp", "docs", "data"]),
    install_requires=[
        'cryptography>=2.2.1', 'pyopenssl==18.0.0',
        'psutil>=1.2.1', 'requests>=2.5.1', 'paramiko>=1.16.0',
        'pandas<=1.2.5', 'numpy<=1.19.5',
        'pip>=8.1.2',
        'pyyaml>=4.2b1', 'cerberus==1.3.1', 'influxdb>=5.0.0', 'netort>=0.8.0',
        'retrying>=1.3.3', 'pytest-runner', 'typing', 'grpcio', 'grpcio-tools'
    ],
    setup_requires=[
    ],
    tests_require=[
        'pytest==4.6.3', 'flake8', 'pytest-benchmark', 'zipp==0.5.1', 'mock'
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
        'Programming Language :: Python :: 3.7',
    ],
    entry_points={
        'console_scripts': [
            'yandex-tank = yandextank.core.cli:main',
            'yandex-tank-check-ssh = yandextank.common.util:check_ssh_connection',
            'tank-postloader = yandextank.plugins.DataUploader.cli:post_loader',
            'tank-docs-gen = yandextank.validator.docs_gen:main'
        ],
    },
    package_data={
        'yandextank.api': ['config/*'],
        'yandextank.core': ['config/*'],
        'yandextank.aggregator': ['config/*'],
        'yandextank.plugins.Android': ['binary/*', 'config/*'],
        'yandextank.plugins.Autostop': ['config/*'],
        'yandextank.plugins.Bfg': ['config/*'],
        'yandextank.plugins.CloudUploader': ['config/*'],
        'yandextank.plugins.Console': ['config/*'],
        'yandextank.plugins.DataUploader': ['config/*'],
        'yandextank.plugins.InfluxUploader': ['config/*'],
        'yandextank.plugins.OpenTSDBUploader': ['config/*'],
        'yandextank.plugins.JMeter': ['config/*'],
        'yandextank.plugins.JsonReport': ['config/*'],
        'yandextank.plugins.Pandora': ['config/*'],
        'yandextank.plugins.Phantom': ['config/*'],
        'yandextank.plugins.RCAssert': ['config/*'],
        'yandextank.plugins.ResourceCheck': ['config/*'],
        'yandextank.plugins.ShellExec': ['config/*'],
        'yandextank.plugins.ShootExec': ['config/*'],
        'yandextank.plugins.Telegraf': ['config/*', 'agent/*'],
        'yandextank.plugins.NeUploader': ['config/*']
    },
    use_2to3=False, )
