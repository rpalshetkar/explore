import datetime
from pathlib import Path
import re
from typing import Any, Dict, Optional, List, ClassVar
from jinja2 import Template

import attr
from cattrs import Converter
import cattrs
from icecream import ic
from refactor.utils import input_dict, io_stream, read_yaml

DYNAMIC_CLASS = 'DynamicClass'


class SingletonMeta(type):
    _instances: ClassVar[Dict[str, Any]] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class ClassFactory(metaclass=SingletonMeta):
    def __init__(self, **kwargs: Dict[str, Any]):
        self.inputs = input_dict(**kwargs)
        self.serializer: Converter = self._cls_converter()
        self.py_jtmpl = io_stream(Path('xds/catalogue/templates/classgen.jinja2'))
        self.classes = {}
        self.py = {}

    def d2c(self, **kwargs: Dict[str, Any]) -> type:
        data: dict[str, Any] = self._inputs(**kwargs)
        kind: str = data.get('kind', DYNAMIC_CLASS)
        return self._from_data(kind, data)

    def _inputs(self, **kwargs: Dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = input_dict(**kwargs)
        data = self._if_missing_cls(DYNAMIC_CLASS, data)
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

    def _fld_flags(self, key: str, value: Any) -> Dict[str, Any]:
        if not isinstance(value, str):
            return {}
        val = value.strip().lower()
        flags_mapping = [
            (r'/req', 'required', True),
            (r'/int', 'type', 'int'),
            (r'/float', 'type', 'float'),
            (r'/bool', 'type', 'bool'),
            (r'/date', 'type', 'date'),
            (r'/unique', 'unique', True),
            (r'/key', 'key', True),
            (r'/default', 'default', True),
            (r'/ro', 'ro', True),
            (r'/hide', 'hidden', True),
        ]
        flags = {
            flag: flag_value
            for pattern, flag, flag_value in flags_mapping
            if re.search(pattern, val)
        }
        flags['testing'] = key.title()
        return flags

    def _from_data(self, name: str, data: Dict[str, Any], root: str = '') -> Any:
        attributes = {}
        attributes['context'] = attr.ib(type=Dict[str, Any], default=None)
        for key, val in data.items():
            kws = {}
            qualifier = f'{root}.{key}' if root else key
            value = val
            flags = self._fld_flags(key, value)
            if isinstance(value, str) and re.search(r',', value):
                value = value.split(',')
            if isinstance(value, dict):
                cls = value['kind']
                kws['type'] = self._from_data(cls, value, qualifier)
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    cls = value[0]['kind']
                    kws['type'] = List[self._from_data(cls, value[0], qualifier)]
                else:
                    kws['type'] = List[type(value[0])]
            else:
                kws['type'] = type(value)

            kws['metadata'] = {
                'annotations': key.title(),
                'qualifier': qualifier.lower(),
            }
            kws['metadata'].update(flags)
            kws['default'] = None
            attributes[key] = attr.ib(**kws)

        dynclass = attr.make_class(name, attributes)
        self.classes[name] = dynclass
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
            list, lambda d, _: d[0].split(',') if isinstance(d, str) and ',' in d else d
        )

        return converter

    def instance(self, **kwargs: Dict[str, Any]) -> Optional[Any]:
        data: dict[str, Any] = self._inputs(**kwargs)
        kind: str = data.get('kind', DYNAMIC_CLASS)
        cls = self.classes.get(kind)
        assert cls is not None, f'Class {kind} not found. Factory not initialized'
        obj = self.serializer.structure(data, cls)
        return obj

    def cls2py(self, cls_id: str) -> str:
        cls = self.classes.get(cls_id)
        if cls is None:
            raise ValueError(f'Class {cls_id} not found.')

        fields = attr.fields(cls)
        ic(fields)
        fields_data = [
            self._extract_field_info(attr_value, cls_id) for attr_value in fields
        ]

        py_tmpl = Template(self.py_jtmpl)
        rendered_code = py_tmpl.render(cls_id=cls_id, fields=fields_data)
        self.py[cls_id] = rendered_code
        return rendered_code

    def _get_subfields(self, attr_type) -> List[Dict[str, Any]]:
        subfields_data = [
            self._extract_field_info(sub_attr) for sub_attr in attr.fields(attr_type)
        ]
        return subfields_data

    def _extract_field_info(self, attr_value, cls_id=None) -> Dict[str, Any]:
        attr_type = attr_value.type
        name = attr_value.name
        is_nested = name in self.classes
        subfields = []
        if is_nested:
            subfields = self._get_subfields(attr_type)

        return {
            'name': name,
            'type': attr_type.__name__ if hasattr(attr_type, '__name__') else attr_type,
            'default': cls_id if cls_id and name == 'kind' else None,
            'is_nested': is_nested,
            'subfields': subfields,
        }
