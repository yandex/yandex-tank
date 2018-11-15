from yandextank.plugins.Telegraf.config import ConfigManager, AgentConfig
import sys
if sys.version_info[0] < 3:
    from ConfigParser import ConfigParser
else:
    from configparser import ConfigParser


class TestConfigManager(object):
    def test_rawxml_parse(self):
        """ raw xml read from string """
        manager = ConfigManager()
        config = """
        <Monitoring>
            <Host>
                <CPU feature="passed"/>
            </Host>
        </Monitoring>
        """
        etree = manager.parse_xml(config)
        host = etree.findall('Host')[0]
        assert (host[0].tag == 'CPU')

    def test_xml_old_parse(self):
        """ old-style monitoring xml parse """
        manager = ConfigManager()
        configs = manager.getconfig(
            'yandextank/plugins/Telegraf/tests/old_mon.xml', 'sometargethint')
        assert (
            configs[0]['host'] == 'somehost.yandex.tld'
            and configs[0]['host_config']['CPU']['name'] == '[inputs.cpu]')

    def test_xml_telegraf_parse(self):
        """ telegraf-style monitoring xml parse """
        manager = ConfigManager()
        configs = manager.getconfig(
            'yandextank/plugins/Telegraf/tests/telegraf_mon.xml',
            'sometargethint')
        assert (
            configs[0]['host'] == 'somehost.yandex.tld'
            and configs[0]['host_config']['CPU']['name'] == '[inputs.cpu]')

    def test_target_hint(self):
        """ test target hint (special address=[target] option) """
        manager = ConfigManager()
        configs = manager.getconfig(
            'yandextank/plugins/Telegraf/tests/target_hint.xml',
            'somehost.yandex.tld')
        assert (configs[0]['host'] == 'somehost.yandex.tld')


class TestAgentConfig(object):
    def test_create_startup_configs(self):
        """ test agent config creates startup config """
        manager = ConfigManager()
        telegraf_configs = manager.getconfig(
            'yandextank/plugins/Telegraf/tests/telegraf_mon.xml',
            'sometargethint')
        agent_config = AgentConfig(telegraf_configs[0], False)
        startup = agent_config.create_startup_config()
        cfg_parser = ConfigParser()
        cfg_parser.read(startup)
        assert cfg_parser.has_section('startup')

    def test_create_collector_configs(self):
        """ test agent config creates collector config """
        manager = ConfigManager()
        telegraf_configs = manager.getconfig(
            'yandextank/plugins/Telegraf/tests/telegraf_mon.xml',
            'sometargethint')
        agent_config = AgentConfig(telegraf_configs[0], False)
        remote_workdir = '/path/to/workdir/temp'
        collector_config = agent_config.create_collector_config(remote_workdir)
        cfg_parser = ConfigParser()
        cfg_parser.read(collector_config)
        assert (
            cfg_parser.has_section('agent')
            and cfg_parser.get('agent', 'interval') == "'1s'"
            and cfg_parser.has_section('[outputs.file')
            and cfg_parser.get('[outputs.file', 'files')
            == "['{rmt}/monitoring.rawdata']".format(rmt=remote_workdir))

    def test_create_custom_exec_script(self):
        """ test agent config creates custom_exec config """
        manager = ConfigManager()
        telegraf_configs = manager.getconfig(
            'yandextank/plugins/Telegraf/tests/telegraf_mon.xml',
            'sometargethint')
        agent_config = AgentConfig(telegraf_configs[0], False)
        custom_exec_config = agent_config.create_custom_exec_script()
        with open(custom_exec_config, 'r') as custom_fname:
            data = custom_fname.read()
        assert (data.find("-0) curl -s 'http://localhost:6100/stat'") != -1)
