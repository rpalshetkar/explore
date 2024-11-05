from pathlib import Path
from pprint import pformat
from typing import Any, Dict
import attr
import pytest
from refactor.utils import io_stream, modifier_spec
from xds.core.cls_factory import ClassFactory
from xds.core.boot import Boot
from icecream import ic
import re


@pytest.fixture(scope='session')
def setup() -> Dict[str, Any]:
    idir = Path('tests/fixtures')
    mdir = Path('xds/catalogue/blueprints')
    data = {
        'factory': ClassFactory(),
        'student': io_stream(Path(idir, 'models/student.yaml')),
        'john': io_stream(Path(idir, 'data/john.yaml')),
    }
    data['register'] = ['env', 'enumeration', 'ds', 'enumeration']
    for k in data['register']:
        data[k] = io_stream(Path(mdir, f'{k}.yaml'))
    ic(data)
    return data


def test_d2c(setup: Dict[str, Any]) -> None:
    model = setup['ds']
    cls = setup['factory'].d2c(content=model)
    _class_info(cls)


def test_instance(setup: Dict[str, Any]) -> None:
    ic('Setup factory')
    test_d2c(setup)
    ic('Setup Instance')
    student = setup['john']
    cls = setup['factory'].instance(content=student)
    ic(cls)


def _class_info(cls: Any) -> None:
    ic(f'Class {cls}\nAttributes:')
    for fld in attr.fields(cls):
        ic(f'{fld.name} =>\n{fld}')


def test_code_gen(setup: Dict[str, Any]) -> None:
    model = setup['env']
    cls = setup['factory'].d2c(content=model)
    _class_info(cls)
    name: str = cls.__name__
    py = setup['factory'].cls2py(name)
    print(py)
    ic(py)


def test_registry(setup: Dict[str, Any]) -> None:
    for model in setup['register']:
        cls = setup['factory'].d2c(content=setup[model])
        _class_info(cls)
    ic(f'All classes in factory:{setup["factory"].classes}')


def test_boot(setup: Dict[str, Any]) -> None:
    boot = Boot()
    ic(boot)
    dsc = boot.get_class_from_registry('DS')
    ic(dsc)


def test_modifiers() -> None:
    str1 = 'int=42/req/uniq/key/gt=45/lt=50'
    parsed1 = modifier_spec(str1)
    ic(str1, parsed1)
    assert parsed1 == {
        'type': int,
        'default': 42,
        'req': True,
        'uniq': True,
        'key': True,
        'gt': 45,
        'lt': 50,
    }, f'Parsed output for {str1} is incorrect'

    str2 = 'int/key/in=17,18,19'
    parsed2 = modifier_spec(str2)
    ic(str2, parsed2)
    assert parsed2 == {
        'type': int,
        'key': True,
        'in': [17, 18, 19],
    }, f'Parsed output for {str2} is incorrect'
