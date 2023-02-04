import sqlalchemy as sa
from .. import philosophy


def test_sqlalchemy_includes():
    """When Philosophy is instantiated, it includes various objects and
    properties from the core SQLAlchemy orm module. This tests to ensure that
    some of those properties are available directly on Philosophy as
    attributes."""
    db = philosophy.Philosophy()

    assert db.Column == sa.Column
    assert db.Query == sa.orm.Query
