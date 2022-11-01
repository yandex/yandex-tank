from xmlrpc.client import Boolean
from yandextank.common.util import get_test_path
from yandextank.plugins.Telegraf.config import ConfigManager, AgentConfig
import os
import json
import pytest

from configparser import RawConfigParser


class TestConfigManager(object):

    def test_xml_old_parse(self):
        """ old-style monitoring xml parse """
        manager = ConfigManager()
        configs = manager.getconfig(
            os.path.join(get_test_path(), 'yandextank/plugins/Telegraf/tests/old_mon.xml'), 'sometargethint')
        assert configs[0]['host'] == 'somehost.yandex.tld'
        assert configs[0]['host_config']['CPU']['name'] == '[inputs.cpu]'

    @pytest.mark.parametrize('test_file', ['telegraf_mon.xml', 'telegraf_mon.yaml', 'telegraf_global_inputs.yaml'])
    def test_xml_telegraf_parse(self, test_file):
        """ telegraf-style monitoring xml parse """
        manager = ConfigManager()
        configs = manager.getconfig(
            os.path.join(get_test_path(), 'yandextank/plugins/Telegraf/tests/', test_file),
            'sometargethint')
        assert configs[0]['host'] == 'somehost.yandex.tld'
        assert configs[0]['host_config']['CPU']['name'] == '[inputs.cpu]'

    @pytest.mark.parametrize('test_file', ['target_hint.xml', 'target_hint.yaml', 'target_hint_no_hosts.yaml'])
    def test_target_hint(self, test_file):
        """ test target hint (special address=[target] option) """
        manager = ConfigManager()
        configs = manager.getconfig(
            os.path.join(get_test_path(), 'yandextank/plugins/Telegraf/tests/', test_file),
            'somehost.yandex.tld')
        assert configs[0]['host'] == 'somehost.yandex.tld'


class TestAgentConfig(object):
    @pytest.mark.parametrize('test_file', ['telegraf_mon.xml', 'telegraf_mon.yaml', 'telegraf_global_inputs.yaml'])
    def test_create_startup_configs(self, test_file):
        """ test agent config creates startup config """
        manager = ConfigManager()
        telegraf_configs = manager.getconfig(
            os.path.join(get_test_path(), 'yandextank/plugins/Telegraf/tests/', test_file),
            'sometargethint')
        agent_config = AgentConfig(telegraf_configs[0], False)
        startup = agent_config.create_startup_config()
        cfg_parser = RawConfigParser(strict=False)
        cfg_parser.read(startup)
        assert cfg_parser.has_section('startup')

    @pytest.mark.parametrize('test_file', ['telegraf_mon.xml', 'telegraf_mon.yaml', 'telegraf_global_inputs.yaml'])
    def test_create_collector_configs(self, test_file):
        """ test agent config creates collector config """
        manager = ConfigManager()
        telegraf_configs = manager.getconfig(
            os.path.join(get_test_path(), 'yandextank/plugins/Telegraf/tests/', test_file),
            'sometargethint')
        agent_config = AgentConfig(telegraf_configs[0], False)
        remote_workdir = '.'
        collector_config = agent_config.create_collector_config(remote_workdir)
        cfg_parser = RawConfigParser(strict=False)
        cfg_parser.read(collector_config)

        assert cfg_parser.has_section('agent')
        assert cfg_parser.get('agent', 'interval') == "'1s'"
        assert cfg_parser.has_section('[outputs.file]')
        assert cfg_parser.get('[outputs.file]', 'files') == "['{rmt}/monitoring.rawdata']".format(rmt=remote_workdir)

        assert cfg_parser.has_section('[inputs.cpu]')
        assert string_arrays_equal('["time_*", "usage_guest_nice"]', cfg_parser.get('[inputs.cpu]', 'fielddrop'))

        assert cfg_parser.has_section('[inputs.mem]')
        assert string_arrays_equal('["active", "inactive", "total", "used_per*", "avail*"]', cfg_parser.get('[inputs.mem]', 'fielddrop'))

        assert cfg_parser.has_section('[inputs.diskio]')
        assert string_arrays_equal('["vda1","sda1","sda2","sda3","ahalai-mahalai"]', cfg_parser.get('[inputs.diskio]', 'devices'))

    @pytest.mark.parametrize('test_file', ['telegraf_mon.xml', 'telegraf_mon.yaml', 'telegraf_global_inputs.yaml'])
    def test_create_custom_exec_script(self, test_file):
        """ test agent config creates custom_exec config """
        manager = ConfigManager()
        telegraf_configs = manager.getconfig(
            os.path.join(get_test_path(), 'yandextank/plugins/Telegraf/tests/', test_file),
            'sometargethint')
        agent_config = AgentConfig(telegraf_configs[0], False)
        custom_exec_config = agent_config.create_custom_exec_script()
        with open(custom_exec_config, 'r') as custom_fname:
            data = custom_fname.read()
        assert data.find("-0) curl -s 'http://localhost:6100/stat'") != -1


def string_arrays_equal(expected, actual) -> Boolean:
    return json.loads(expected.replace("'", '"')) == json.loads(actual.replace("'", '"'))
