from pprint import pprint as pp

import pytest
from pydantic import BaseModel, Field, ValidationError, create_model


def pydantic_model(name: str, fields: dict):
    processed_fields = {}

    for field_name, field_type in fields.items():
        if isinstance(field_type, dict):
            nested_model = pydantic_model(field_name.title(), field_type)
            processed_fields[field_name] = create_field(
                field_name, nested_model
            )
        else:
            processed_fields[field_name] = create_field(field_name, field_type)

    return create_model(name, **processed_fields)


def create_field(name: str, field_type) -> tuple:
    return field_type, Field(
        title=name.title(),
        description=f'Field {name}',
        example=None,
        required=False,
        default=None,
    )


PFIELDS = {
    'name': str,
    'age': int,
    'scores': list[float],
    'address': {'street': str, 'city': str, 'zipcode': str},
}
PersonDelegate = pydantic_model('PersonDelegate', PFIELDS)


def test_dynamic_subclass():
    BaseUser = create_model(
        'BaseUser',
        id=(int, ...),
        name=(str, 'Jane Doe'),
    )
    StudentUser = create_model(
        'StudentUser', __base__=BaseUser, semester=(int, ...)
    )
    student_instance = StudentUser(id=1, name='Alice', semester=2)
    pp(student_instance)


def test_another_way():
    class A:
        def __init__(self, delegate_cls, **kwargs):
            self.delegate = delegate_cls(**kwargs)
            exports = getattr(self.delegate, 'exports', [])
            for name in exports:
                if hasattr(self.delegate, name):
                    setattr(self, name, getattr(self.delegate, name))

    class Delegate:
        def __init__(self, name):
            self.exports = ['name']
            self.name = name

    a = A(Delegate, name='Alice')
    print(f'Initial Main: {a.name} Delegate: {a.delegate.name}')
    a.delegate.name = 'Bob'
    print(f'Updated on delegate: {a.delegate.name} Main: {a.name}')
    a.name = 'Charlie'
    print(f'Updated on main: {a.name} Delegate: {a.delegate.name}')


test_another_way()
test_dynamic_subclass()

"""'

def test_pydantic_model_variations():
    pp(PersonDelegate.model_json_schema())

    def birthday(self):
        self.age += 1

    PersonDelegate.birthday = birthday

    instance = PersonDelegate(
        name='Test',
        scores=[95.5, 87.0],
        age=25,
        address={
            'street': '123 Main St',
            'city': 'Anytown',
            'zipcode': '12345',
        },
    )
    pp(instance.model_dump())

    instance.birthday()
    pp(instance.model_dump())


def pydantic_model_delegate(name: str, fields: dict):
    attach = {}

    for field_name, field_type in fields.items():
        if isinstance(field_type, dict):
            nested_model = pydantic_model(field_name.title(), field_type)
            attach[field_name] = create_field(field_name, nested_model)
        else:
            attach[field_name] = create_field(field_name, field_type)

    def __dgetattr__(self, name):
        print(f'__dgetattr__: {name}')
        if hasattr(self, '_internal') and name in self._internal.__dict__:
            return self._internal.__dict__[name]
        if name in self.__dict__:
            return self.__dict__[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' has no attribute '{name}'"
        )

    def __dpostinit__(self, **kwargs):
        print('__dpostinit__')
        delegated = kwargs.pop('delegate', None)
        if delegated:
            self._internal = delegated(
                **{k: v for k, v in kwargs.items() if k != 'delegate'}
            )
            for attr in dir(self._internal):
                val = getattr(self._internal, attr)
                if not attr.startswith('_') and not callable(val):
                    setattr(self, attr, val)
            for key, value in kwargs.items():
                if key != 'delegate':
                    setattr(self, key, value)

    def printer(self):
        print(
            'I am the Caller using delegate'
            if hasattr(self, '_internal')
            else 'I am not using the Delegate'
        )

    attach['printer'] = printer
    # attach['__post_init__'] = __dpostinit__
    # attach['__getattr__'] = __dgetattr__

    model = create_model(
        name,
        **attach,
    )
    return model


def test_pydantic_model_delegate_stretch():
    PersonDelegate = pydantic_model_delegate('PersonDelegate', PFIELDS)
    pp(PersonDelegate.model_json_schema())
    dinstance = PersonDelegate(
        name='Standing',
        scores=[95.5, 87.0, 100.0],
        age=28,
        address={
            'street': '123 Main St',
            'city': 'Anytown',
            'zipcode': '12345',
        },
    )
    pp(dinstance.model_dump())
    dinstance.printer()


def test_pydantic_model_delegate():
    Person = pydantic_model_delegate('Person', {'delegate': PersonDelegate})
    pp(Person.model_json_schema())
    instance = Person(
        name='Proxied',
        scores=[95.5, 87.0],
        age=38,
        address={
            'street': '123 Main St',
            'city': 'Anytown',
            'zipcode': '12345',
        },
    )
    pp(instance.model_dump())


def test_delegate_method_call():
    fields = {
        'name': str,
        'age': int,
    }

    PersonDelegate = pydantic_model('PersonDelegate', fields)

    def birthday(self):
        self.age += 1
        return self.age

    PersonDelegate.birthday = birthday

    Person = pydantic_model_delegate('Person', {'delegate': PersonDelegate})

    person = Person(delegate=PersonDelegate, name='John', age=25)

    assert person.age == 25  # noqa: PLR2004
    assert person.birthday() == 26  # noqa: PLR2004
    assert person.age == 26  # noqa: PLR2004


def test_delegate_attribute_access():
    PersonDelegate = pydantic_model('PersonDelegate', {'name': str})
    Person = pydantic_model_delegate('Person', {'delegate': PersonDelegate})

    person = Person(delegate=PersonDelegate, name='John')
    assert person.name == 'John'


def test_delegate_missing_attribute():
    PersonDelegate = pydantic_model('PersonDelegate', {'name': str})
    Person = pydantic_model_delegate('Person', {'delegate': PersonDelegate})

    person = Person(delegate=PersonDelegate, name='John')

    with pytest.raises(AttributeError) as exc_info:
        _ = person.non_existent_attribute
    assert "no attribute 'non_existent_attribute'" in str(exc_info.value)


def test_delegate_method_updates_parent():
    fields = {
        'name': str,
        'age': int,
    }

    PersonDelegate = pydantic_model('PersonDelegate', fields)

    def change_name(self, new_name):
        self.name = new_name
        return self.name

    PersonDelegate.change_name = change_name
    Person = pydantic_model_delegate('Person', {'delegate': PersonDelegate})

    person = Person(delegate=PersonDelegate, name='John', age=25)
    assert person.name == 'John'

    person.change_name('Jane')
    assert person.name == 'Jane'
    assert person._internal.name == 'Jane'


def test_dynamic_model():
    User = create_model(
        'User',
        id=(int, ...),  # Required field
        name=(str, ...),  # Required field
        age=(int, None),  # Optional field
    )

    def post_init(self):
        if self.age is not None and self.age < 0:
            raise ValueError('Age must be a non-negative integer.')
        print(f'User created: {self.name} with ID {self.id}')

    User.__post_init_post_parse__ = post_init

    try:
        _ = User(id=1, name='Alice', age=30)
    except ValidationError as e:
        print(e)

    try:
        _ = User(id=2, name='Bob', age=-5)
    except ValueError as e:
        print(e)

"""
