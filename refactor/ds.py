from __future__ import annotations

from enum import Enum
from itertools import islice
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, TYPE_CHECKING

import pandas as pd
from pandas import DataFrame, Series
from pandas.api.types import is_numeric_dtype


from .reader import Reader
from .utils import df_pytypes, icf, xlate, xlation_map

if TYPE_CHECKING:
    from refactor.ntypes import SourceType, StrOrListStr


class DiffType(Enum):
    ALL = 'all'
    DIFF = 'diff'


class DS:
    def __init__(
        self,
        source: SourceType,
        keys: Optional[StrOrListStr] = None,
        children: Optional[Dict[str, Any]] = None,
    ) -> None:
        if keys is None:
            keys = []
        if children is None:
            children = {}
        self._to_df(source)

        if isinstance(keys, str):
            keys = keys.split(',')
        refs = self._xdf(list(keys), children)

        self.schema: Dict[str, str] = refs['schema']
        self.df: DataFrame = refs['df']
        self.children: Dict[str, DS] = refs['children']

        self.xlations: Dict[str, Dict[str, str]] = xlation_map(self.df.columns)
        self.xlations.pop('var', None)

        self.kv: Dict[str, Dict[str, Any]] = refs['kv']
        self.length: int = self.df.count()

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
        hdf.columns = [self.xlations['human'].get(col, col) for col in hdf.columns]
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
            return list(self.df[cols].astype(str).agg('|'.join, axis=1).unique())
        except KeyError as err:
            raise ValueError(f'One of the fields {cols} not found in dataset') from err

    def join(
        self,
        other: 'DS',
        on: Optional[StrOrListStr] = None,
        how: Literal['inner', 'outer', 'left', 'right'] = 'inner',
        lsuffix: str = 'a',
        rsuffix: str = 'b',
        lkeys: Optional[StrOrListStr] = None,
        rkeys: Optional[StrOrListStr] = None,
    ) -> 'DS':
        def _prepare_df(df: pd.DataFrame, kys: Any, suffix: str) -> pd.DataFrame:
            keys: List[str] = (
                kys.split(',')
                if isinstance(kys, str)
                else kys
                if isinstance(kys, list)
                else ['key']
            )
            dfk: pd.DataFrame = df.copy()
            dfk['key'] = df[keys].astype(str).agg('|'.join, axis=1)
            dfk.columns = [f'{col}-{suffix}' for col in dfk.columns]
            return dfk

        ldf = _prepare_df(self.df, lkeys, lsuffix)
        rdf = _prepare_df(self.df, rkeys, rsuffix)
        joined = ldf.join(rdf, on=on, how=how)  # type: ignore  # noqa: PGH003
        return DS(joined, keys=self.keys)

    def __str__(self) -> str:
        kvs = dict(islice(self.kv.items(), 5))
        data: List[Tuple[str, Any]] = [
            ('Protocol', self.protocol),
            ('Schema', icf(self.schema)),
            ('Keys', self.keys),
            ('Xlations', icf(self.xlations)),
            ('Columns', icf(self.df.columns)),
            ('Dataframe', self.df.head(10)),
            ('KVs Sample', icf(kvs)),
            ('Children', icf(self.children)),
        ]
        sep: str = '-' * 60 + '\n'
        return sep.join(f'{header} ->{content}\n' for header, content in data)

    def __repr__(self) -> str:
        return self.__str__()

    def diff(
        self,
        other: 'DS',
        how: DiffType = DiffType.ALL,
        lkeys: Optional[Union[str, List[str]]] = None,
        rkeys: Optional[Union[str, List[str]]] = None,
        v: Optional[List[str]] = None,
    ) -> 'DS':
        if lkeys is None or rkeys is None:
            raise ValueError(
                "Both 'lkeys' and 'rkeys' must be provided for diff operation."
            )

        lkeys = lkeys.split(',') if isinstance(lkeys, str) else lkeys
        rkeys = rkeys.split(',') if isinstance(rkeys, str) else rkeys

        # Create mkey columns without setting them as index
        self.df['mkey'] = self.df[lkeys].astype(str).agg('/'.join, axis=1)
        other.df['mkey'] = other.df[rkeys].astype(str).agg('/'.join, axis=1)

        left_df = self.df.copy()
        right_df = other.df.copy()

        # Combine the dataframes using outer merge to preserve all rows
        result = pd.merge(
            left_df, right_df, on='mkey', how='outer', suffixes=('_L', '_R')
        )

        # Create status column
        result['status'] = 'MATCH'
        result.loc[
            result['mkey'].isin(left_df['mkey'])
            & ~result['mkey'].isin(right_df['mkey']),
            'status',
        ] = 'ONLY L'
        result.loc[
            ~result['mkey'].isin(left_df['mkey'])
            & result['mkey'].isin(right_df['mkey']),
            'status',
        ] = 'ONLY R'

        # Identify differing rows and calculate diffs for numeric columns
        for lcol, rcol in zip(lkeys, rkeys):
            lcol_full = f'{lcol}_L'
            rcol_full = f'{rcol}_R'
            if lcol_full in result.columns and rcol_full in result.columns:
                mask = (
                    (result[lcol_full] != result[rcol_full])
                    & result[lcol_full].notna()
                    & result[rcol_full].notna()
                )
                result.loc[mask, 'status'] = 'DIFF'
                if (
                    v
                    and lcol in v
                    and rcol in v
                    and is_numeric_dtype(result[lcol_full])
                    and is_numeric_dtype(result[rcol_full])
                ):
                    diff_col_name = (
                        f'Diff - {lcol}' if lcol == rcol else f'Diff {lcol} - {rcol}'
                    )
                    result.loc[mask, diff_col_name] = (
                        result.loc[mask, lcol_full] - result.loc[mask, rcol_full]
                    )

        # Combine _L and _R columns
        for col in set(left_df.columns) | set(right_df.columns):
            if col != 'mkey':
                result[col] = result[f'{col}_L'].combine_first(result[f'{col}_R'])
                result = result.drop(columns=[f'{col}_L', f'{col}_R'], errors='ignore')

        # Apply the 'how' filter
        if how == DiffType.DIFF:
            result = result[result['status'] != 'MATCH']

        # Create the 'id' column
        result['id'] = result['status'] + '_' + result['mkey']

        # Reorder columns
        column_order = ['status', 'id', 'mkey'] + [
            col for col in result.columns if col not in ['status', 'id', 'mkey']
        ]
        result = result[column_order]

        return DS(result)


"""
DSA Dataset
A   | B | C|X| Y|
-----|---|--|-|--|
both1| a1|b2|3|50|
both2| a2|b3|4|60|
both3| a1|b2|3|50|
both4| b3|5 |5|70|
dup05| b3|5 |5|70|
dup05| b3|5 |5|70|
onlyA| b3|5 |5|70|

DSB Dataset
M   | N | C|X| Y|
-----|---|--|--|--|
both1| a1|b2|3|50|
both2| a2|b3|4|60|
both3| a1|b2|3|50|
both4| b3|5 |5|70|
dup05| b3|5 |6|80|
onlyB| b3|5 |5|70|

lhs = DSA, rhs = DSB
lkey = M,N
rkey = A,B


Start with All first.

class DiffType(Enum):
    ALL = 'all'
    DIFF = 'diff'
    PCT = 'pct'
    ABS = 'abs'
    SIDEWAY = 'LRD (Left Right Diff)'

Create Match Key columns using string based on lkey and rkey and apply functions
Then if it find the mask in the other dataframe, it will State = MATCH else DIFF
if not found they ONLY L or ONLY R based on the prefix passed
Create the id = concat(State, Match Key)

For z param which is all numeric columns if passed then DIFF column
would be left - right diff

ALL should return all the columns from LHS and RHS and lx, rx columns asked as params

DIFF would just give only A or B or DIFF rows

SIDEWAY would give Left Columns and Right Columns and Diff Columns
prefixed with (L) and (R) and (DIFF)

"""
