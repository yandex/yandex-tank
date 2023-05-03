from .local import LocalStorageClient
from .luna import LunaClient
from .lunapark_volta import LunaparkVoltaClient

available_clients = {
    'luna': LunaClient,
    'local_storage': LocalStorageClient,
    'lunapark_volta': LunaparkVoltaClient,
}
