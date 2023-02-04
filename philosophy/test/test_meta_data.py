import sqlalchemy as sa
from .. import philosophy


def test_default_metadata(database_manager):
    db = philosophy.Philosophy(database_manager, metadata=None)

    class One(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        myindex = db.Column(db.Integer, index=True)

    class Two(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        one_id = db.Column(db.Integer, db.ForeignKey(One.id))
        myunique = db.Column(db.Integer, unique=True)

    assert One.metadata.__class__ is sa.MetaData
    assert Two.metadata.__class__ is sa.MetaData

    assert One.__table__.schema is None
    assert Two.__table__.schema is None


def test_custom_metadata(database_manager):
    class CustomMetaData(sa.MetaData):
        pass

    custom_metadata = CustomMetaData(schema="test_schema")
    db = philosophy.Philosophy(database_manager, metadata=custom_metadata)

    class One(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        myindex = db.Column(db.Integer, index=True)

    class Two(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        one_id = db.Column(db.Integer, db.ForeignKey(One.id))
        myunique = db.Column(db.Integer, unique=True)

    assert One.metadata is custom_metadata
    assert Two.metadata is custom_metadata

    assert One.metadata.__class__ is not sa.MetaData
    assert One.metadata.__class__ is CustomMetaData

    assert Two.metadata.__class__ is not sa.MetaData
    assert Two.metadata.__class__ is CustomMetaData

    assert One.__table__.schema == "test_schema"
    assert Two.__table__.schema == "test_schema"
