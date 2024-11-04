from __future__ import annotations

from enum import Enum
from itertools import islice
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
)

import pandas as pd
from pandas import DataFrame, Series
from pandas.api.types import is_numeric_dtype

from refactor.reader import Reader
from xds.utils.helpers import df_pytypes, icf, xlate, xlation_map

if TYPE_CHECKING:
    from refactor.ntypes import SourceType, StrOrListStr


class DiffType(Enum):
    ALL = 'all'
    DIFF = 'diff'


class DS:
    def __init__(self, **kwargs: Any) -> None:
        self.create(**kwargs)

    @classmethod
    def create(cls, **kwargs: Any) -> DS:
        instance = cls.__new__(cls)

        source = kwargs.get('source')
        keys = kwargs.get('keys', [])
        children = kwargs.get('children', {})

        instance._to_df(source)

        if isinstance(keys, str):
            keys = keys.split(',')
        refs = instance._xdf(list(keys), children)

        instance.schema = refs['schema']
        instance.df = refs['df']
        instance.children = refs['children']
        instance.xlations = xlation_map(instance.df.columns)
        instance.xlations.pop('var', None)
        instance.kv = refs['kv']
        instance.length = instance.df.count()

        return instance

    def kv_search(self, kw: Dict[str, Any]) -> DataFrame:
        mask: Series = Series(True, index=self.df.index)
        for field, val in kw.items():
            if field in self.df.columns:
                value = val
                if isinstance(val, str):
                    value = value.split(',')
                if isinstance(value, (list, tuple)):
                    mask &= self.df[field].isin(value)
                else:
                    mask &= self.df[field] == value
        return self.df[mask]

    def _to_df(self, data: SourceType) -> None:
        xp, xdf = Reader().to_df(data)
        xlations = xlation_map(list(xdf.columns))
        xdf.columns = [xlations['var'].get(col, col) for col in xdf.columns]
        self.protocol: str = xp
        self._odf: DataFrame = xdf

    def _xdf(
        self,
        keys: Optional[List[str]] = None,
        children: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if children is None:
            children = {}
        if keys is None:
            keys = []
        df: pd.DataFrame = self._odf.copy()
        self.keys = [xlate(var)[0] for var in keys]
        schema = df_pytypes(df)
        nested = [col for col, ptype in schema.items() if ptype == 'pd']
        for col, ptype in schema.items():
            if ptype == 'datex':
                df[col] = df[col].dt.strftime('%Y-%m-%d')

        if self.keys:
            unknown = set(self.keys) - set(df.columns)
            if unknown:
                raise ValueError(f'Unknown keys: {unknown}')
            df['key'] = df[self.keys].astype(str).agg('|'.join, axis=1)
            df.set_index('key', inplace=True)

        nodes: Dict[str, 'DS'] = {}

        for k, val in (children or {}).items():
            child = xlate(k)[0]
            if child not in nested:
                continue
            ccols = val['keys']
            if ccols:
                if isinstance(ccols, str):
                    ccols = ccols.split(',')
                ndf = pd.concat(df[child].tolist(), keys=df.index)
                ndf['pkey'] = ndf.index.get_level_values(0)
                ndf.reset_index(inplace=True, drop=True)
                ckeys: List[str] = ['pkey', *ccols]
                nodes[child] = DS(ndf, keys=ckeys)

        for child in nested:
            df.drop(child, axis=1, inplace=True)

        return {
            'schema': df_pytypes(df),
            'df': df,
            'xlations': xlation_map(list(df.columns)),
            'children': nodes,
            'kv': df.to_dict(orient='index'),
        }

    @property
    def df_humanized(self) -> pd.DataFrame:
        hdf = self.df.copy()
        hdf.columns = [
            self.xlations['human'].get(col, col) for col in hdf.columns
        ]
        return hdf

    def _type(self, col: str) -> Any:
        try:
            return self.df[col].dtype
        except KeyError as err:
            raise ValueError(f'Key {col} not found in dataset') from err

    def __getitem__(self, key: str) -> Dict[str, Any]:
        return self.kv.get(key) or {}

    def __setitem__(self, key: str, value: Any) -> None:
        v: Dict[str, Any] = self.kv.get(key) or {}
        v |= value
        try:
            self.df.loc[key] = v
        except KeyError as err:
            raise ValueError(f'Key missing {key}') from err
        self.kv[key] = v

    def unique(self, cols: StrOrListStr) -> List[str]:
        try:
            return list(
                self.df[cols].astype(str).agg('|'.join, axis=1).unique()
            )
        except KeyError as err:
            raise ValueError(
                f'One of the fields {cols} not found in dataset'
            ) from err


"""
To implement diff joins and other callables on df in other callables classes
"""
