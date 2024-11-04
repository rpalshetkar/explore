import datetime
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set

import attr
import cattrs
from cattrs import Converter
from icecream import ic
from jinja2 import Template

import xds.core.impl
from xds.core.field import field_spec
from xds.utils.helpers import SingletonMeta, input_dict, io_stream, xlate

_DYNAMIC_CLASS = 'DynamicClass'


class Dynamo(metaclass=SingletonMeta):
    """
    Purpose of this module to set the discipline over
    - More implication/inference than being explicit and too maximalist
    - Class generation from yaml or kwargs
    - Enforce namings and decisions around which classes need concrete implementations
    - Proxies/Or 'REVERSE PROXIES' on dynamic classes to add more functionality
    - Facilitate to run validations via driver which is either python, cli, api driver
    - Minimalist yaml with syntax understood/interpreted well for core. Only this module
    - Eventually minimalist yamls could be generated by UI if required
    - This can get complex and would have lot of special/weird interpretation logic
      more like a domain specific/regex for certain purpose
    - Class to python code generation, in case static type checking - IS THIS NEEDED?
    """

    def __init__(self, **kwargs: Dict[str, Any]):
        self.inputs = input_dict(**kwargs)
        self.serializer: Converter = self._cls_converter()
        self.serializer: cattrs.Converter = cattrs.Converter(
            forbid_extra_keys=True
        )
        # TODO: Hardcoded paths once Env is bootstrapped.
        self.models = {}
        self.py = {}
        self.args: Set[str] = set()

    def d2c(self, **kwargs: Dict[str, Any]) -> type:
        data: dict[str, Any] = self._inputs(**kwargs)
        kind: str = data.get('kind', _DYNAMIC_CLASS)
        return self._from_data(kind, data)

    def _inputs(self, **kwargs: Dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = input_dict(**kwargs)
        data = self._if_missing_cls(_DYNAMIC_CLASS, data)
        return data

    def _if_missing_cls(self, key, data):
        if isinstance(data, dict):
            if 'kind' not in data:
                data['kind'] = key
            for k, value in data.items():
                self._if_missing_cls(k, value)
        elif isinstance(data, list):
            for item in data:
                self._if_missing_cls(key, item)
        return data

    def _from_data(
        self, name: str, data: Dict[str, Any], root: str = ''
    ) -> Any:
        """
        This is major workhorse to create classes from yaml. Expecting to autogen
        based on metadata. Dirty and needs cleanup
        """
        attributes = {}
        for key, val in data.items():
            kws = {}
            qualifier = f'{root}.{key}' if root else key
            value = val
            # if isinstance(value, str) and re.search(r',', value):
            #    value = value.split(',')
            if isinstance(value, dict):
                cls = value['kind']
                kws['type'] = self._from_data(cls, value, qualifier)
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    cls = value[0]['kind']
                    kws['type'] = List[
                        self._from_data(cls, value[0], qualifier)
                    ]
                else:
                    kws['type'] = List[type(value[0])]
            else:
                kws['type'] = type(value)

            var, eng = xlate(key)
            meta = {
                'qualifier': qualifier.lower(),
                'var': var,
                'alias': eng,
                'key': key,
                'vtype': type(value),
                'otype': kws.get('type'),
            }
            modifier = field_spec(value) if isinstance(value, str) else {}
            if modifier:
                meta.update(modifier)
            kws['kw_only'] = True
            if modifier.get('xref'):
                kws['type'] = self.models.get(modifier.get('xref'))
            else:
                kws['default'] = modifier.get('default', None)
            kws['metadata'] = meta
            attributes[var] = attr.ib(**kws)

        attributes['nsid'] = attr.ib(type=str, default=None)
        attributes['uid'] = attr.ib(type=str, default='fta')
        dynclass = attr.make_class(name, attributes)

        def _info() -> str:
            cls = dynclass
            info = f'\nClass: {name}/{type(cls)}\n'
            for field in attr.fields(cls):
                lst = [
                    v
                    for v in [
                        field.name,
                        str(field.type),
                        str(field.default),
                        field.metadata.get('title'),
                    ]
                    if v
                ]
                info += '  ' + ', '.join(lst) + '\n'
            return info

        dynclass.info = _info
        self.models[name] = dynclass
        print(dynclass.info())
        return dynclass

    @classmethod
    def _cls_converter(cls) -> Converter:
        converter = cattrs.Converter(forbid_extra_keys=True)
        converter.register_structure_hook(
            tuple, lambda d, _: list(d) if isinstance(d, list) else d
        )
        converter.register_unstructure_hook(tuple, list)

        converter.register_structure_hook(
            set, lambda d, _: list(d) if isinstance(d, list) else d
        )
        converter.register_unstructure_hook(set, list)

        converter.register_structure_hook(
            str,
            lambda d, _: datetime.strptime(d, '%Y-%m-%d')
            if re.match(r'\d{4}-\d{2}-\d{2}', d)
            else d,
        )
        converter.register_structure_hook(
            str,
            lambda d, _: d.split(',') if isinstance(d, str) and ',' in d else d,
        )
        return converter

    def instance(self, **kwargs: Dict[str, Any]) -> Optional[Any]:
        data: dict[str, Any] = self._inputs(**kwargs)
        kind: str = data.get('kind', _DYNAMIC_CLASS)
        cls = self.models.get(kind)
        assert (
            cls is not None
        ), f'Class {kind} not found. Factory not initialized'
        obj = self.serializer.structure(data, cls)
        if hasattr(cls, 'proxy'):
            print(f'Creating proxy with kwargs: {kwargs}')
            obj._internal = cls.proxy(**kwargs)
            print(f'Created proxy object: {obj._internal}')
            for attr_name, attr_value in vars(obj._internal).items():
                if hasattr(cls, attr_name):
                    raise ValueError(
                        f'{attr_name} is not allowed to used in implementation'
                    )
                if not attr_name.startswith('_'):
                    setattr(obj, attr_name, attr_value)
        return obj

    def _proxy_getattr(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        return getattr(self._internal, name)

    def _proxy_setattr(self, name, value):
        if name == '_internal':
            super().__setattr__(name, value)
        elif name in self.__dict__:
            self.__dict__[name] = value
        else:
            setattr(self._internal, name, value)


"""
proxy = attributes.get('proxy')
if proxy:
    attributes['_internal'] = attr.ib(type=proxy, default=None)
if proxy:
    dynclass.__getattr__ = self._proxy_getattr
    dynclass.__setattr__ = self._proxy_setattr
"""
