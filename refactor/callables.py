from typing import Callable, Dict

from refactor.ds import DS

callables: Dict[str, Callable] = {
    'Field Value': DS.kv_search,
    'Field Search': DS.field_search,
}
