import uuid
import pytest
from unittest.mock import patch, MagicMock
from google.protobuf.any_pb2 import Any

from yandextank.plugins.DataUploader.loadtesting_agent import agent_registration_service_pb2, \
    LoadtestingAgent, AgentOrigin, METADATA_LT_CREATED_ATTR, METADATA_AGENT_VERSION_ATTR
from yandex.cloud.operation import operation_pb2


class Stb:
    Register = None
    ExternalAgentRegister = None


@pytest.fixture()
def patch_agent_registration_stub_register():
    with patch.object(Stb, 'Register') as p:
        yield p


@pytest.fixture()
def patch_agent_registration_stub_external_register():
    with patch.object(Stb, 'ExternalAgentRegister') as p:
        yield p


@pytest.fixture()
def patch_agent_registration_stub():
    with patch('yandextank.plugins.DataUploader.loadtesting_agent.agent_registration_service_pb2_grpc.AgentRegistrationServiceStub') as stb:
        stb.return_value = Stb
        yield stb


@pytest.fixture()
def patch_loadtesting_agent_get_instance_metadata():
    with patch('yandextank.plugins.DataUploader.loadtesting_agent.get_instance_metadata') as p:
        p.return_value = {}
        yield p


@pytest.mark.usefixtures('patch_agent_registration_stub', 'patch_loadtesting_agent_get_instance_metadata')
def test_agent_send_version_on_greet(patch_agent_registration_stub_register):
    version = str(uuid.uuid4())
    patch_agent_registration_stub_register.return_value = agent_registration_service_pb2.RegisterResponse(
        agent_instance_id='abc'
    )

    lt = LoadtestingAgent('backend_url', MagicMock(), MagicMock(),
                          agent_origin=AgentOrigin.COMPUTE_LT_CREATED, agent_version=version)

    assert lt.agent_id == 'abc'
    patch_agent_registration_stub_register.assert_called_once()
    _, kwargs = patch_agent_registration_stub_register.call_args
    assert 'metadata' in kwargs
    assert (METADATA_AGENT_VERSION_ATTR, version) in kwargs['metadata']


@pytest.mark.usefixtures('patch_agent_registration_stub', 'patch_loadtesting_agent_get_instance_metadata')
@pytest.mark.parametrize('agent_origin, agent_name, folder_id', [
    (AgentOrigin.COMPUTE_EXTERNAL, '', ''),
    (AgentOrigin.EXTERNAL, 'agent name', 'folder id')
])
def test_external_agent_registration(agent_origin, agent_name, folder_id, patch_agent_registration_stub_external_register):
    version = str(uuid.uuid4())
    metadata = Any()
    metadata.Pack(
        agent_registration_service_pb2.ExternalAgentRegisterMetadata(
            agent_instance_id='abc-ext'
        )
    )
    patch_agent_registration_stub_external_register.return_value = operation_pb2.Operation(metadata=metadata)

    lt = LoadtestingAgent('backend_url', MagicMock(), MagicMock(), agent_origin=agent_origin, agent_name=agent_name,
                          folder_id=folder_id, agent_version=version)
    assert lt.agent_id == 'abc-ext'
    patch_agent_registration_stub_external_register.assert_called_once()
    _, kwargs = patch_agent_registration_stub_external_register.call_args
    assert 'metadata' in kwargs
    assert (METADATA_AGENT_VERSION_ATTR, version) in kwargs['metadata']


@pytest.mark.usefixtures('patch_agent_registration_stub', 'patch_loadtesting_agent_get_instance_metadata')
@pytest.mark.parametrize('agent_origin', [
    (AgentOrigin.EXTERNAL, AgentOrigin.COMPUTE_EXTERNAL)
])
def test_external_agent_registration_fail(agent_origin):
    with pytest.raises(RuntimeError):
        LoadtestingAgent('backend_url', MagicMock(), MagicMock(), agent_origin=agent_origin)


@pytest.mark.usefixtures('patch_agent_registration_stub', 'patch_agent_registration_stub_register')
def test_identify_compute_metadata(patch_loadtesting_agent_get_instance_metadata):
    version = str(uuid.uuid4())
    patch_loadtesting_agent_get_instance_metadata.return_value = {
        'id': 'some_id',
        'attributes': {
            METADATA_AGENT_VERSION_ATTR: version,
            METADATA_LT_CREATED_ATTR: True
        }
    }

    lt = LoadtestingAgent('backend_url', MagicMock(), MagicMock())

    assert lt.compute_instance_id == 'some_id'
    assert lt.agent_version == version
    assert lt.agent_origin == AgentOrigin.COMPUTE_LT_CREATED
