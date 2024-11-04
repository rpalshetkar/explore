import typing
from datetime import datetime
from typing import Any, Dict

import pytest
from icecream import ic

from xds.core.field import field_spec
from xds.utils.dates import date_modifier


@pytest.fixture(scope='module')
def data() -> Dict[str, Any]:
    fixtures = {
        'tdates': {
            '2024-11-10': [
                ('Today', 'T', '2024-11-10'),
                ('Next day', '1', '2024-11-11'),
                ('Prior day', '-1', '2024-11-09'),
                ('Prior 2 Bus Day', '-2B', '2024-11-08'),
                ('Month start', 'S', '2024-11-01'),
                ('Month end', 'ME', '2024-11-30'),
                ('Next Month', '1M', '2024-12-10'),
                ('Month End 3 Months', '3ME', '2025-02-28'),
                ('Quarter end', 'QE', '2024-12-31'),
                ('First Quarter After', '1QE', '2025-03-31'),
                ('Two Quarter After', '2QE', '2025-06-30'),
                ('Year end', 'YE', '2024-12-31'),
            ],
            '2024-02-29': [
                ('Today', 'T', '2024-02-29'),
                ('Next day', '1', '2024-03-01'),
                ('Prior day', '-1', '2024-02-28'),
                ('Prior 2 Bus Day', '-2B', '2024-02-27'),
                ('Month start', 'S', '2024-02-01'),
                ('Month end', 'ME', '2024-02-29'),
                ('Next Month', '1M', '2024-03-29'),
                ('Month End 3 Months', '3ME', '2024-05-31'),
                ('Quarter end', 'QE', '2024-03-31'),
                ('First Quarter After', '1QE', '2024-06-30'),
                ('Two Quarter After', '2QE', '2024-09-30'),
                ('Year end', 'YE', '2024-12-31'),
            ],
        },
        'fldspecs': [
            [
                'req#ge=10#regex=abc.*#fuzzy#color=red#multi#xref=bow?x=y,z#',
                {
                    'color': 'red',
                    'fuzzy': True,
                    'ge': '10',
                    'multi': None,
                    'req': True,
                    'type': str,
                    'xref': 'bow?x=y,z',
                },
            ],
            [
                'req#listi=1,2#color=10#xref=z#has=y#start=z#gt=50#fuzzy#key#uniq',
                {
                    'color': '10',
                    'default': [1, 2],
                    'fuzzy': True,
                    'gt': '50',
                    'has': 'y',
                    'key': True,
                    'listi': '1,2',
                    'req': True,
                    'start': 'z',
                    'type': typing.List[int],
                    'uniq': True,
                    'xref': 'z',
                },
            ],
            [
                'int=42#req#uniq#key#gt=45#lt=50',
                {
                    'default': 42,
                    'gt': '45',
                    'int': '42',
                    'key': True,
                    'lt': '50',
                    'req': True,
                    'type': int,
                    'uniq': True,
                },
            ],
            [
                'int#key#in=17,18,19',
                {
                    'in': [17, 18, 19],
                    'int': None,
                    'key': True,
                    'type': int,
                },
            ],
        ],
    }
    return fixtures


def test_date_patterns(data: Dict[str, Any]):
    tdates = data['tdates']
    for base_date, test_cases in tdates.items():
        for test_name, modifier, expected in test_cases:
            assert date_modifier(modifier, base_date) == expected, (
                f'Failed on {base_date} {test_name}:'
                f'Expected {expected}, Got {date_modifier(modifier, base_date)}'
            )


def test_fld_spec(data: Dict[str, Any]) -> None:
    for spec, expected in data['fldspecs']:
        results = field_spec(spec)
        ic(spec, results)
        assert (
            results == expected
        ), f'Failed on {spec}:Expected {expected}, Got {results}'
