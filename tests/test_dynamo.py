from pathlib import Path
from typing import Any, Dict

import attr
import pytest
from icecream import ic

from xds.core.dynamo import Dynamo
from xds.core.registry import Registry
from xds.utils.helpers import flat, io_stream, read_yaml
from xds.utils.logger import log


class ClassProxy:
    def __init__(self, **kwargs):
        ic(kwargs)
        ic(f'I am a class proxy {kwargs}')


@pytest.fixture(scope='session')
def setup() -> Dict[str, Any]:
    test_cdir = Path('tests/fixtures')
    data = {
        'registry': Registry(),
    }
    for blueprint in ['student', 'nested', 'a', 'b', 'complex']:
        data[blueprint] = io_stream(
            file=f'{test_cdir}/blueprints/{blueprint}.yaml'
        )
    for blueprint in [
        'student',
        'nested',
        'nestedab',
        'complex',
        'xdsapi',
        'proxy',
    ]:
        data[f'{blueprint}_ex'] = io_stream(
            file=f'{test_cdir}/usecases/{blueprint}_ex.yaml'
        )
    data['tests'] = io_stream(file=f'{test_cdir}/blueprints/models.yaml')
    ic(data['tests'])
    data['factory'] = data['registry'].factory
    return data


def test_log():
    log.debug('This is a debug message.')
    log.info('This is an info message.')
    log.warn('This is a warning message.')
    log.error('This is an error message.')
    log.critical('This is a critical message.')
    assert True


def test_xds(setup: Dict[str, Any]) -> None:
    registry = setup['registry']
    inst = registry.instance(content=setup['proxy_ex'])
    ic(inst)


def test_registry(setup: Dict[str, Any]) -> None:
    registry = setup['registry']
    _ = registry.model('XDS')
    _ = registry.model('Env')
    log.info(f'Registry Namespaces =>\n{registry.ns}')
    env = registry.locator('instances/env/beta')
    log.info(f'Registry Locator =>\n{env}')
    log.info(f'Env Variables =>\n{registry.env}')


def test_env(setup: Dict[str, Any]) -> None:
    env = setup['registry'].env
    ic(env)
    assert env is not None, 'Environment is not set'


def test_registered_classes(setup: Dict[str, Any]) -> None:
    registry = setup['registry']
    ic(registry.models)
    log.info(f'Registered classes: {registry.models}')


def _test_ds(setup: Dict[str, Any]) -> None:
    registry = setup['registry']
    ds = registry.factory.d2c(content=setup['ds'])
    ic(ds)


def test_student(setup: Dict[str, Any]) -> None:
    _adhoc_cls(setup, 'student')
    _adhoc_instance(setup, 'student')


def test_nested(setup: Dict[str, Any]) -> None:
    _adhoc_cls(setup, 'nested')
    _adhoc_instance(setup, 'nested')


def test_nested_ab(setup: Dict[str, Any]) -> None:
    _adhoc_cls(setup, 'a')
    _adhoc_cls(setup, 'b')
    _adhoc_instance(setup, 'nestedab')


def _adhoc_cls(setup: Dict[str, Any], clstr: str) -> None:
    registry = setup['registry']
    cls = registry.factory.d2c(content=setup[clstr])
    _class_info(cls)
    ic(cls)
    assert cls is not None, f'Class {clstr} is None'


def _adhoc_instance(setup: Dict[str, Any], clstr: str) -> None:
    registry = setup['registry']
    iyaml = setup[f'{clstr}_ex']
    inst = registry.factory.instance(content=iyaml)
    ic(inst)
    log.debug(f'Instance of {clstr}: {inst}')
    assert inst is not None, f'Instance of {clstr} is None'


def _adhoc_cls_instance(setup: Dict[str, Any], clstr: str) -> None:
    ic('Setup class')
    cls = setup['factory'].d2c(content=setup[clstr])
    _class_info(cls)
    iyaml = setup[f'{clstr}_ex']
    inst = setup['factory'].instance(content=iyaml)
    ic(inst)
    log.debug(f'Instance of {cls}: {inst}')
    assert inst is not None, f'Instance of {cls} is None'


def _class_info(cls: Any) -> None:
    ic(f'Class {cls}\nAttributes:')
    for fld in attr.fields(cls):
        ic(f'{fld.name} =>\n{fld}')


def test_so_complex(setup: Dict[str, Any]) -> None:
    # data = read_yaml(contents=setup['complex'])
    # flt = flat(data)
    # ic(flt)
    _adhoc_cls(setup, 'complex')
    _adhoc_instance(setup, 'complex')
