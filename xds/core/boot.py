from pathlib import Path
from typing import Dict, Any

from refactor.utils import io_stream
from icecream import ic

import attr
from xds.core.cls_factory import ClassFactory
from xds.core.logger import log
import catalogue


@attr.s(kw_only=True)
class Boot:
    factory = attr.ib(factory=lambda: ClassFactory())
    ns = attr.ib(default='boot')
    # TODO: Hardcoded paths once Env is bootstrapped. Need to figure our fwd reference
    register = attr.ib(factory=lambda: ['env', 'enumeration', 'ds'])
    path = attr.ib(default='xds/catalogue/models')
    models = attr.ib(init=False)

    def __attrs_post_init__(self):
        self.models = [io_stream(Path(self.path, f'{k}.yaml')) for k in self.register]
        self.registry = catalogue.create(self.ns, 'models')

        for model in self.models:
            cls = self.factory.d2c(content=model)
            ic(f'Class {cls.__name__}')
            ic('Class Attributes')
            for fld in attr.fields(cls):
                ic(f'{fld.name} =>\n{fld}')

            log.info(f'Registered into Catalogue: {cls.__name__}')
            self.registry.register(cls.__name__, cls)

        ic(f'All classes in factory:{self.factory.classes}')
        # TODO: Somehow doesn't work in catalogue. Figure out why
        log.info(f'Registered {self.factory.classes} classes')
