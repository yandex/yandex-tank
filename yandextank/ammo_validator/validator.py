from typing import Any, Type

from yandextank.contrib.netort.netort.resource import ResourceManager, open_file
from yandextank.core import TankCore
from yandextank.plugins.Phantom import Plugin as PhantomPlugin
from yandextank.plugins.Pandora import Plugin as PandoraPlugin

from .common import AmmoType, Decision, FileFormatValidator, InlineFormatValidator, Messages, Message, Features
from .validators.json_grpc import JsonGrpcValidator
from .validators.json_http import JsonHttpValidator
from .validators.phantom import PhantomValidator
from .validators.uri import UriValidator
from .validators.uri_inline import UriInlineValidator
from .validators.uripost import UriPostValidator

FILE_VALIDATORS: tuple[Type[FileFormatValidator], ...] = (
    JsonGrpcValidator,
    JsonHttpValidator,
    PhantomValidator,
    UriValidator,
    UriPostValidator,
)


INLINE_VALIDATORS: tuple[Type[InlineFormatValidator], ...] = (UriInlineValidator,)

PANDORA_STR_TO_AMMO_TYPE = {
    'raw': AmmoType.RAW,
    'uri': AmmoType.URI,
    'uripost': AmmoType.URIPOST,
    'phantom': AmmoType.PHANTOM,
    'http/json': AmmoType.HTTP_JSON,
    'grpc/json': AmmoType.GRPC_JSON,
}

PHANTOM_STR_TO_AMMO_TYPE = {
    'uri': AmmoType.URI,
    'uripost': AmmoType.URIPOST,
    'phantom': AmmoType.PHANTOM,
}


def collect_ammos(core: TankCore) -> tuple[list[tuple[AmmoType, str]], list[tuple[AmmoType, dict]], Messages]:
    msg = Messages()
    ammo_files: list[tuple[AmmoType, str]] = []
    ammo_inline: list[tuple[AmmoType, dict]] = []

    if core.get_option('phantom', 'enabled', False):
        try:
            config = core.get_plugin_of_type(PhantomPlugin).cfg

            ammo_type = config.get('ammo_type')
            ammo_file = config.get('ammofile')
            if ammo_type in PHANTOM_STR_TO_AMMO_TYPE and ammo_file:
                ammo_files.append((PHANTOM_STR_TO_AMMO_TYPE[ammo_type], str(ammo_file)))
            elif ammo_type == 'uri' and 'uris' in config:
                ammo_inline.append((AmmoType.URI, config))
            else:
                msg.warning(
                    Message(f'Unknown phantom ammo type {ammo_type} or file does not specified in phantom section')
                )
        except KeyError:
            msg.warning(Message('Phantom section has bad format'))

    if core.get_option('pandora', 'enabled', False):
        try:
            config = core.get_plugin_of_type(PandoraPlugin).config_contents
            if config:
                for pool_idx, pool_cf in enumerate(config["pools"]):
                    ammo: dict[str, Any]
                    if ammo := pool_cf.get('ammo', {}):
                        ammo_type = ammo.get('type')
                        ammo_file = ammo.get('file')
                        if ammo_type in PANDORA_STR_TO_AMMO_TYPE and ammo_file:
                            ammo_files.append((PANDORA_STR_TO_AMMO_TYPE[ammo_type], str(ammo_file)))
                        elif ammo_type == 'uri' and 'uris' in ammo:
                            ammo_inline.append((AmmoType.URI, ammo))
                        else:
                            msg.warning(
                                Message(
                                    f'Unknown pandora ammo type {ammo_type} or file does not specified'
                                    f' in pandora section in pool #{pool_idx}',
                                )
                            )
            else:
                msg.warning(Message('Pandora section has no config_content section'))
        except KeyError:
            msg.warning(Message('Pandora section has bad format'))

    return ammo_files, ammo_inline, msg


def validate(
    resource_manager: ResourceManager, core: TankCore, max_scan_size: int = 1_000_000_000_000, use_cache=True
) -> Messages:
    ammos, inline_ammos, messages = collect_ammos(core)

    for ammo_type, ammo_file in ammos:
        found = False
        found_ammo_types = Decision(set())
        feat = Features.from_file(resource_manager, ammo_file, max_scan_size)
        for Validator in FILE_VALIDATORS:
            v = Validator()
            decision = v.is_suitable(feat)
            found_ammo_types |= decision
            for d in decision:
                if d == ammo_type:
                    opener = resource_manager.get_opener(ammo_file)
                    with open_file(opener, use_cache) as stream:
                        try:
                            v_msgs = v.validate(stream, max_scan_size)
                        except Exception as e:
                            v_msgs = Messages()
                            v_msgs.warning(Message(f'Error while validating with validator {v.__qualname__}: {e}'))
                    messages.update(v_msgs, ammo_file=ammo_file)
                    found = True
                    break
        if not found:
            messages.warning(
                Message(
                    f'Can\'t find validator for ammo type {ammo_type}.'
                    f' Suggested ammo types: {", ".join(sorted(found_ammo_types))}',
                    ammo_file,
                )
            )

    for ammo_type, ammo_inline in inline_ammos:
        found = False
        for Validator in INLINE_VALIDATORS:
            v = Validator()
            if v.is_suitable(ammo_type):
                v_msgs = v.validate(ammo_inline)
                messages.update(v_msgs)
                found = True
        if not found:
            messages.error(Message(f'Can\'t find inline validator for ammo type {ammo_type}.'))

    return messages
