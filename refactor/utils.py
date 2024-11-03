from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, TypeAlias
from urllib.parse import parse_qs, urlparse

import attr
import cattrs
import pandas as pd
import yaml
from icecream import ic

NO_XLATIONS_SPECIALS = ['LOB', 'PL', 'PI']

XlationMap: TypeAlias = Dict[str, Dict[str, str]]
ic.configureOutput(prefix='DEBUG: ', includeContext=True)


def df_pytypes(df: pd.DataFrame) -> Dict[str, str]:
    overrides = {
        'datetime.date': 'date',
        'pandas.core.frame.DataFrame': 'pd',
    }
    types = {
        col: str(df[col].apply(type).unique()[0]).split("'")[1]  # type: ignore  # noqa: PGH003
        for col in df.columns
    }
    for col, ptype in types.items():
        if ptype in overrides:
            types[col] = overrides[ptype]
    return types


def xlate(val: str) -> Tuple[str, str]:
    var = re.sub(r'\W+', '_', val).lower()
    arr: List[str] = [
        i.upper() if i.upper() in NO_XLATIONS_SPECIALS else i.title()
        for i in var.split('_')
    ]
    eng = ' '.join(arr)
    return var, eng


def xlation_map(vals: List[str]) -> Dict[str, Dict[str, str]]:
    xlations: Dict[str, Dict[str, str]] = {
        'human': {},
        'var': {},
    }
    for val in vals:
        var, eng = xlate(val)
        xlations['human'][var] = eng
        xlations['var'][eng] = var
        xlations['var'][val] = var
    return xlations


def icf(var: Any, header: str | Any = None) -> None:
    if header:
        ic(header)
    ic(var)


def io_stream(file_path: str) -> Optional[str]:
    try:
        with open(file_path, 'r', encoding='utf-8') as fp:
            return fp.read()
    except FileNotFoundError:
        print(f'Error: The file {file_path} was not found.')
    except IOError as e:
        print(f'Error: An I/O error occurred while reading the file {file_path}: {e}')

    return None


def read_yaml(contents: str) -> Optional[Any]:
    try:
        if contents is None:
            return None
        return yaml.safe_load(contents)
    except yaml.YAMLError as e:
        ic(f'Error: Failed to parse YAML file {contents}: {e}')
    except Exception as e:
        ic(f'Error: An unexpected error occurred while reading {contents}: {e}')

    return None


def read_json(contents: str) -> Optional[Any]:
    try:
        if contents is None:
            return None
        return json.loads(contents)
    except json.JSONDecodeError as json_err:
        raise ValueError('Failed to parse content as JSON') from json_err
    except Exception as e:
        raise ValueError('Failed to parse content as JSON {e}') from e

    return None


def is_pivot(df: pd.DataFrame) -> bool:
    if isinstance(df.index, pd.MultiIndex) or isinstance(df.columns, pd.MultiIndex):  # type: ignore  # noqa: PGH003
        return True
    if df.index.name is not None and df.index.name != 'key':  # type: ignore  # noqa: PGH003
        return True
    if len(df.columns.names) > 1:
        return True
    return False


def parse_url(url: str) -> Dict[str, Any]:
    def parse_nested_qs(qs: Dict[str, List[str]]) -> Dict[str, Any]:
        result = {}
        for k, v in qs.items():
            keys = k.split('.')
            d = result
            for key in keys[:-1]:
                if key not in d:
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = v[0].split(',') if ',' in v[0] else v[0]
        return result

    parsed_url = urlparse(url)
    return parse_nested_qs(parse_qs(parsed_url.query))


def parse_content(content: str) -> Optional[Any]:
    try:
        ic(f'Trying yaml: {content}')
        return read_yaml(content)
    except yaml.YAMLError:
        ic(f'Trying json: {content}')
        return read_json(content)


def input_dict(**kwargs) -> Optional[Any]:
    data: Optional[Any] = None

    try:
        if 'file' in kwargs and 'content' in kwargs and 'url' in kwargs:
            raise ValueError(
                "Only one of 'file', 'content', or 'url' should be provided"
            )

        if 'file' in kwargs:
            file: str = str(kwargs['file'])
            content = io_stream(file)
            if file.lower().endswith(('.yaml', '.yml')):
                data = read_yaml(content)
            elif file.lower().endswith('.json'):
                data = read_json(content)
            else:
                raise ValueError(f'Unsupported file format: {file}')

        elif 'content' in kwargs:
            content = kwargs['content']
            data = parse_content(content)

        elif 'url' in kwargs:
            url = kwargs['url']
            content = parse_url(url)
            if content:
                data = parse_content(content)

        else:
            icf(f'Creating data from kwargs: {kwargs}')
            data = kwargs

        if data is None:
            raise ValueError('No data returned')

        return cattrs.structure(data, Dict[str, Any])

    except (yaml.YAMLError, json.JSONDecodeError, AttributeError) as e:
        raise ValueError(
            f'Exception: Input Parser: Failed to parse input: {e!s}'
        ) from e

    except Exception as e:
        raise ValueError(f'Exception: Input Parser: Invalid info to parse {e!s}') from e


def pprint_obj(self, obj: Any, indent: int = 2) -> None:
    for key, value in attr.asdict(obj).items():
        if isinstance(value, dict) and all(isinstance(v, dict) for v in value.values()):
            ic(f"{'  ' * indent}{key}:")
            self.pprint_obj(value, indent + 1)
        else:
            ic(f"{'  ' * indent}{key}: {value}")
