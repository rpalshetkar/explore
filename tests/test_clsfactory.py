from pathlib import Path
from pprint import pformat
from typing import Any, Dict
import attr
import pytest
from refactor.utils import io_stream
from xds.core.cls_factory import ClassFactory
from xds.core.boot import Boot
from icecream import ic


@pytest.fixture(scope='session')
def setup() -> Dict[str, Any]:
    idir = Path('tests/fixtures')
    mdir = Path('xds/catalogue/models')
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
    model = setup['student']
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
