import re
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.orm.decl_api import DeclarativeMeta, declared_attr
from sqlalchemy.schema import _get_table_key
from typing import Any
from .utils import has_primary_key

camelcase_re = re.compile(r"([A-Z]+)(?=[a-z0-9])")


def camel_to_snake_case(name):
    def _join(match):
        word = match.group()
        if len(word) > 1:
            return ("_%s_%s" % (word[:-1], word[-1])).lower()
        return "_" + word.lower()

    return camelcase_re.sub(_join, name).lstrip("_")


def should_set_tablename(cls):
    """Determine whether ``__tablename__`` should be automatically generated
    for a model.

    * If no class in the MRO sets a name, one should be generated.
    * If a table prefix (__table_prefix__) is specified,
    * If a declared attr is found, it should be used instead.
    * If a name is found, it should be used if the class is a mixin, otherwise
      one should be generated.
    * Abstract models should not have one generated.

    Later, :meth:`._BoundDeclarativeMeta.__table_cls__` will determine if the
    model looks like single or joined-table inheritance. If no primary key is
    found, the name will be unset.
    """
    if cls.__dict__.get("__abstract__", False) or not any(
        isinstance(b, DeclarativeMeta) for b in cls.__mro__[1:]
    ):
        return False

    for base in cls.__mro__:
        if "__tablename__" not in base.__dict__:
            continue
        if isinstance(base.__dict__["__tablename__"], declared_attr):
            return False
        if "__table_prefix__" in base.__dict__:
            return True
        return not (
            base is cls
            or base.__dict__.get("__abstract__", False)
            or not isinstance(base, DeclarativeMeta)
        )

    return True


class AutoBigIntegerIdentifierMetaMixin(object):
    """
    A meta class for auto-generating `BigInteger` primary key columns on models.
    """

    def __init__(
        cls, classname: str, bases: tuple[type[Any], ...], dict_: dict[str, Any]
    ) -> None:
        """ """
        #: Check to see if the class has at least one primary key defined. If
        #: not, automatically generate one.
        has_primary = has_primary_key(cls)

        if not has_primary:
            cls.__dict__.update(
                {"id": sa.Column("id", sa.BigInteger, nullable=False, primary_key=True)}
            )
            cls.__dict__["id"]._creation_order = 1

            dict_.update(
                {"id": sa.Column("id", sa.BigInteger, nullable=False, primary_key=True)}
            )
            dict_["id"]._creation_order = 1
        super().__init__(classname, bases, dict_)


class BindMetaMixin(object):
    """ """

    def __init__(
        cls, classname: str, bases: tuple[type[Any], ...], dict_: dict[str, Any]
    ) -> None:
        bind_key = dict_.pop("__bind_key__", None) or getattr(cls, "__bind_key__", None)

        super().__init__(classname, bases, dict_)

        if bind_key is not None and getattr(cls, "__table__", None) is not None:
            cls.__table__.info["bind_key"] = bind_key


class NameMetaMixin(object):
    """ """

    def __init__(
        cls, classname: str, bases: tuple[type[Any], ...], dict_: dict[str, Any]
    ) -> None:
        if should_set_tablename(cls):
            table_name = camel_to_snake_case(cls.__name__)
            #: If a table prefix is specified, overwrite the `table_name` with
            #: one that contains both the prefix and the name of the table.
            if "__table_prefix__" in cls.__dict__:
                table_prefix = camel_to_snake_case(cls.__table_prefix__)
                table_name = f"{table_prefix}{table_name}"
            cls.__tablename__ = table_name

        super().__init__(classname, bases, dict_)

        # __table_cls__ has run at this point
        # if no table was created, use the parent table
        if (
            "__tablename__" not in cls.__dict__
            and "__table__" in cls.__dict__
            and cls.__dict__["__table__"] is None
        ):
            del cls.__table__

    def __table_cls__(cls, *args, **kwargs):
        """This is called by SQLAlchemy during mapper setup. It determines the
        final table object that the model will use.

        If no primary key is found, that indicates single-table inheritance,
        so no table will be created and ``__tablename__`` will be unset.
        """
        # check if a table with this name already exists
        # allows reflected tables to be applied to model by name
        key = _get_table_key(args[0], kwargs.get("schema"))

        if key in cls.metadata.tables:
            return sa.Table(*args, **kwargs)

        # if a primary key or constraint is found, create a table for
        # joined-table inheritance
        for arg in args:
            print(arg)
            if (isinstance(arg, sa.Column) and arg.primary_key) or isinstance(
                arg, sa.PrimaryKeyConstraint
            ):
                return sa.Table(*args, **kwargs)

        # if no base classes define a table, return one
        # ensures the correct error shows up when missing a primary key
        for base in cls.__mro__[1:-1]:
            if "__table__" in base.__dict__:
                break
        else:
            return sa.Table(*args, **kwargs)

        # single-table inheritance, use the parent tablename
        if "__tablename__" in cls.__dict__:
            del cls.__tablename__


class DefaultMeta(NameMetaMixin, BindMetaMixin, DeclarativeMeta):
    pass


class Model(object):
    """Base class for SQLAlchemy declarative base model.

    To define models, subclass :attr:`db.Model <SQLAlchemy.Model>`, not this
    class. To customize ``db.Model``, subclass this and pass it as
    ``model_class`` to :class:`SQLAlchemy`.
    """

    #: Query class used by :attr:`query`. Defaults to
    # :class:`SQLAlchemy.Query`, which defaults to :class:`BaseQuery`.
    query_class = None

    #: Convenience property to query the database for instances of this model
    # using the current session. Equivalent to ``db.session.query(Model)``
    # unless :attr:`query_class` has been changed.
    query = None

    def __repr__(self):
        identity = inspect(self).identity
        if identity is None:
            pk = "(transient {})".format(id(self))
        else:
            pk = ", ".join(str(value) for value in identity)
        return "<{} {}>".format(type(self).__name__, pk)
