import os
import yaml
from xml.etree import ElementTree
from requests.structures import CaseInsensitiveDict

from typing import List

TARGET_HINT_PLACEHOLDER = '[target]'
YAML_HOSTS_SECTION = 'hosts'
YAML_METRICS_SECTION = 'metrics'
YAML_CUSTOM_METRIC = 'custom'
YAML_CUSTOM_METRIC_CMD = 'cmd'
XML_HOST_TAG_NAME = 'Host'
XML_HOST_ADDRESS_ATTR = 'address'


class ParseError(Exception):
    pass


class Metric(CaseInsensitiveDict):
    name: str
    text: str

    def __init__(self, name, text, data):
        super().__init__(data)
        self.name = name
        self.text = text


class Host(CaseInsensitiveDict):
    address: str
    metrics: List[Metric]

    def __init__(self, address, metrics, data):
        super().__init__(data)
        self.address = address
        self.metrics = metrics


def parse_xml(config) -> List[Host]:
    try:
        if os.path.exists(config):
            tree = ElementTree.parse(config)
        else:
            tree = ElementTree.fromstring(config)
    except ElementTree.ParseError as ex:
        raise ParseError(ex)

    result = []
    hosts = tree.findall(XML_HOST_TAG_NAME)
    for host in hosts:
        hostname = host.get(XML_HOST_ADDRESS_ATTR, '').lower()
        metrics = [Metric(m.tag, m.text, m.attrib) for m in host]
        result.append(Host(hostname, metrics, host.attrib))
    return result


def parse_yaml(config) -> List[Host]:
    try:
        if os.path.exists(config):
            with open(config, "r") as stream:
                yaml_content = yaml.safe_load(stream)
        else:
            yaml_content = yaml.safe_load(config)
    except yaml.YAMLError as ex:
        raise ParseError(ex)

    result = []

    yaml_content = yaml_content or {}

    global_inputs = yaml_content.get(YAML_METRICS_SECTION, {})
    agents = yaml_content.get(YAML_HOSTS_SECTION, {})

    # if no "agents:" provided use default host
    if len(agents) == 0:
        agents[TARGET_HINT_PLACEHOLDER] = None
    for hostname, hostdata in agents.items():
        metrics = []
        local_inputs = global_inputs.copy()
        hostdata = hostdata or {}

        local_inputs.update(hostdata.get(YAML_METRICS_SECTION, {}))

        for mname, mdata in local_inputs.items():
            if mdata is None:
                mdata = ''

            if mname.lower() == YAML_CUSTOM_METRIC and isinstance(mdata, dict):
                mtext = mdata.get(YAML_CUSTOM_METRIC_CMD, '') or str(mdata)
            else:
                mtext = str(mdata)
            metrics.append(Metric(mname, mtext, mdata if isinstance(mdata, dict) else {}))

        result.append(Host(hostname, metrics, hostdata if isinstance(hostdata, dict) else {}))
    return result
