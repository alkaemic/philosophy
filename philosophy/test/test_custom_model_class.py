# coding=utf8
import pytest
from .. import philosophy
from ..model import BindMetaMixin
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import declarative_base


def test_custom_model_class():
    class CustomModelClass(philosophy.Model):
        pass

    db = philosophy.Philosophy(model_class=CustomModelClass)

    class SomeModel(db.Model):
        id = db.Column(db.Integer, primary_key=True)

    assert isinstance(SomeModel(), CustomModelClass)


def test_no_table_name():
    class NoNameMeta(BindMetaMixin, DeclarativeMeta):
        pass

    db = philosophy.Philosophy(
        model_class=declarative_base(
            cls=philosophy.Model, metaclass=NoNameMeta, name="Model"
        )
    )

    with pytest.raises(InvalidRequestError):

        class User(db.Model):
            pass


def test_repr(db):
    class User(db.Model):
        name = db.Column(db.String, primary_key=True)

    class Report(db.Model):
        id = db.Column(db.Integer, primary_key=True, autoincrement=False)
        user_name = db.Column(db.ForeignKey(User.name), primary_key=True)

    db.create_all()

    u = User(name="test")
    assert repr(u).startswith("<User (transient ")
    db.session.add(u)
    db.session.flush()
    assert repr(u) == "<User test>"
    assert repr(u) == str(u)

    u2 = User(name="🐍")
    db.session.add(u2)
    db.session.flush()
    assert repr(u2) == str("<User 🐍>")
    assert repr(u2) == str(u2)

    r = Report(id=2, user_name=u.name)
    db.session.add(r)
    db.session.flush()
    assert repr(r) == "<Report 2, test>"
    assert repr(u) == str(u)
