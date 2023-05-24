import uuid
import os
import pytest
from unittest.mock import patch, MagicMock
from google.protobuf.any_pb2 import Any

from yandextank.plugins.DataUploader.loadtesting_agent import (
    agent_registration_service_pb2,
    LoadtestingAgent,
    AgentOrigin,
    METADATA_LT_CREATED_ATTR,
    METADATA_AGENT_VERSION_ATTR,
    METADATA_AGENT_NAME_ATTR,
    METADATA_FOLDER_ID_ATTR,
    AgentOriginError,
    use_yandex_compute_metadata,
    RUN_IN_ENVIRONMENT_ENV,
    try_identify_compute_metadata,
    KnownEnvironment,
    _AgentComputeMetadata,
)
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


@pytest.fixture()
def patch_loadtesting_agent_get_instance_yandex_metadata():
    with patch('yandextank.plugins.DataUploader.loadtesting_agent.get_instance_yandex_metadata') as p:
        p.return_value = {}
        yield p


@pytest.mark.usefixtures(
    'patch_agent_registration_stub',
    'patch_loadtesting_agent_get_instance_metadata',
    'patch_loadtesting_agent_get_instance_yandex_metadata',
)
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


@pytest.mark.usefixtures(
    'patch_agent_registration_stub',
    'patch_loadtesting_agent_get_instance_metadata',
    'patch_loadtesting_agent_get_instance_yandex_metadata',
)
def test_external_agent_registration(patch_agent_registration_stub_external_register):
    version = str(uuid.uuid4())
    metadata = Any()
    metadata.Pack(
        agent_registration_service_pb2.ExternalAgentRegisterMetadata(
            agent_instance_id='abc-ext'
        )
    )
    patch_agent_registration_stub_external_register.return_value = operation_pb2.Operation(metadata=metadata)

    lt = LoadtestingAgent('backend_url', MagicMock(), MagicMock(), agent_origin=AgentOrigin.EXTERNAL, agent_name='agent_name',
                          folder_id='folder_id', agent_version=version)
    assert lt.agent_id == 'abc-ext'
    patch_agent_registration_stub_external_register.assert_called_once()
    _, kwargs = patch_agent_registration_stub_external_register.call_args
    assert 'metadata' in kwargs
    assert (METADATA_AGENT_VERSION_ATTR, version) in kwargs['metadata']


@pytest.mark.usefixtures(
    'patch_agent_registration_stub',
    'patch_loadtesting_agent_get_instance_metadata',
    'patch_loadtesting_agent_get_instance_yandex_metadata',
)
def test_external_agent_registration_fail():
    with patch.object(LoadtestingAgent, '_load_agent_id') as load_agent_id:
        load_agent_id.return_value = None
        with pytest.raises(AgentOriginError):
            LoadtestingAgent('backend_url', MagicMock(), MagicMock(), agent_origin=AgentOrigin.EXTERNAL, agent_name='persistent')


@pytest.mark.usefixtures('patch_agent_registration_stub', 'patch_agent_registration_stub_register')
@pytest.mark.parametrize(
    'compute_id, compute_attrs, expected_meta',
    [
        (
            'some_id',
            {
                METADATA_AGENT_VERSION_ATTR: 'some_version',
                METADATA_LT_CREATED_ATTR: True,
                METADATA_AGENT_NAME_ATTR: 'some_agent',
                METADATA_FOLDER_ID_ATTR: 'user_folder',
            },
            _AgentComputeMetadata('some_id', 'some_version', 'some_agent', 'user_folder', True),
        ),
        (
            'some_id',
            {
                METADATA_AGENT_VERSION_ATTR: 'some_version',
                METADATA_LT_CREATED_ATTR: False,
                METADATA_AGENT_NAME_ATTR: 'some_agent',
            },
            _AgentComputeMetadata('some_id', 'some_version', 'some_agent', 'other_folder', False),
        ),
    ],
)
def test_identify_compute_metadata(
    patch_loadtesting_agent_get_instance_metadata,
    patch_loadtesting_agent_get_instance_yandex_metadata,
    compute_id,
    compute_attrs,
    expected_meta,
):
    os.environ[RUN_IN_ENVIRONMENT_ENV] = KnownEnvironment.YANDEX_COMPUTE.value
    patch_loadtesting_agent_get_instance_metadata.return_value = {
        'id': compute_id,
        'attributes': compute_attrs,
    }
    patch_loadtesting_agent_get_instance_yandex_metadata.return_value = {'folderId': 'other_folder'}
    assert try_identify_compute_metadata() == expected_meta


@pytest.mark.parametrize('env_value, expected', [
    ('', False),
    ('bajsdh', False),
    ('YANDEX_CLOUD_COMPUTE', True),
])
def test_use_yandex_compute_metadata(env_value, expected):
    try:
        os.environ[RUN_IN_ENVIRONMENT_ENV] = env_value
        assert use_yandex_compute_metadata() == expected
    finally:
        os.unsetenv(RUN_IN_ENVIRONMENT_ENV)
