from .. import philosophy
from sqlalchemy.ext.declarative import declared_attr


def test_engine_lookup(db, database_manager):
    database_manager.config["SQLALCHEMY_BINDS"] = {
        "foo": "sqlite://",
        "bar": "sqlite://",
    }

    assert db.get_engine(database_manager, None) == db.engine
    for key in "foo", "bar":
        engine = db.get_engine(database_manager, key)
        connector = database_manager.extensions["sqlalchemy"].connectors[key]
        assert engine == connector.get_engine()
        assert str(engine.url) == database_manager.config["SQLALCHEMY_BINDS"][key]


def test_basic_binds(db, database_manager):
    database_manager.config["SQLALCHEMY_BINDS"] = {
        "foo": "sqlite://",
        "bar": "sqlite://",
    }

    class Foo(db.Model):
        __bind_key__ = "foo"
        __table_args__ = {"info": {"bind_key": "foo"}}
        id = db.Column(db.Integer, primary_key=True)

    class Bar(db.Model):
        __bind_key__ = "bar"
        id = db.Column(db.Integer, primary_key=True)

    class Baz(db.Model):
        id = db.Column(db.Integer, primary_key=True)

    db.create_all()

    # do the models have the correct engines?
    assert db.metadata.tables["foo"].info["bind_key"] == "foo"
    assert db.metadata.tables["bar"].info["bind_key"] == "bar"
    assert db.metadata.tables["baz"].info.get("bind_key") is None

    # see the tables created in an engine
    metadata = db.MetaData()
    metadata.reflect(bind=db.get_engine(database_manager, "foo"))
    assert len(metadata.tables) == 1
    assert "foo" in metadata.tables

    metadata = db.MetaData()
    metadata.reflect(bind=db.get_engine(database_manager, "bar"))
    assert len(metadata.tables) == 1
    assert "bar" in metadata.tables

    metadata = db.MetaData()
    metadata.reflect(bind=db.get_engine(database_manager))
    assert len(metadata.tables) == 1
    assert "baz" in metadata.tables

    # do the session have the right binds set?
    assert db.get_binds(database_manager) == {
        Foo.__table__: db.get_engine(database_manager, "foo"),
        Bar.__table__: db.get_engine(database_manager, "bar"),
        Baz.__table__: db.get_engine(database_manager, None),
    }


def test_abstract_binds(db, database_manager):
    database_manager.config["SQLALCHEMY_BINDS"] = {"foo": "sqlite://"}

    class AbstractFooBoundModel(db.Model):
        __abstract__ = True
        __bind_key__ = "foo"

    class FooBoundModel(AbstractFooBoundModel):
        id = db.Column(db.Integer, primary_key=True)

    db.create_all()

    # does the model have the correct engines?
    assert db.metadata.tables["foo_bound_model"].info["bind_key"] == "foo"

    # see the tables created in an engine
    metadata = db.MetaData()
    metadata.reflect(bind=db.get_engine(database_manager, "foo"))
    assert len(metadata.tables) == 1
    assert "foo_bound_model" in metadata.tables


def test_polymorphic_bind(db, database_manager):
    bind_key = "polymorphic_bind_key"

    database_manager.config["SQLALCHEMY_BINDS"] = {
        bind_key: "sqlite:///:memory",
    }

    class Base(db.Model):
        __bind_key__ = bind_key

        __tablename__ = "base"

        id = db.Column(db.Integer, primary_key=True)

        p_type = db.Column(db.String(50))

        __mapper_args__ = {"polymorphic_identity": "base", "polymorphic_on": p_type}

    class Child1(Base):
        child_1_data = db.Column(db.String(50))
        __mapper_args__ = {
            "polymorphic_identity": "child_1",
        }

    assert Base.__table__.info["bind_key"] == bind_key
    assert Child1.__table__.info["bind_key"] == bind_key
