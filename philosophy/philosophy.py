"""
    philosophy.philosophy
    ~~~~~

    This module is the core implementation of the Philosophy library.
"""
import functools
import sqlalchemy
import sys
import time
from sqlalchemy import event, orm
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.orm.session import Session as SessionBase
from threading import Lock
from typing import Any
from typing import Optional
from typing import Union
from .model import DefaultMeta, Model
from .mixin import mixin_sqlalchemy, mixin_sqlalchemy_orm


# the best timer function for the platform
if sys.platform == "win32":
    if sys.version_info >= (3, 3):
        _timer = time.perf_counter
    else:
        _timer = time.clock
else:
    _timer = time.time


def _make_table(db):
    #: TODO this seems "utility-ish", move it out of here to either utils or something more appropriate to SQLAlchemy??
    def _make_table(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], db.Column):
            args = (args[0], db.metadata) + args[1:]
        info = kwargs.pop("info", None) or {}
        info.setdefault("bind_key", None)
        kwargs["info"] = info
        return sqlalchemy.Table(*args, **kwargs)

    return _make_table


def _set_default_query_class(d, cls):
    if "query_class" not in d:
        d["query_class"] = cls


def _wrap_with_default_query_class(fn, cls):
    @functools.wraps(fn)
    def newfn(*args, **kwargs):
        _set_default_query_class(kwargs, cls)
        if "backref" in kwargs:
            backref = kwargs["backref"]
            if isinstance(backref, str):
                backref = (backref, {})
            _set_default_query_class(backref[1], cls)
        return fn(*args, **kwargs)

    return newfn


def _include_sqlalchemy(obj, cls):
    obj = mixin_sqlalchemy(obj, cls)
    obj = mixin_sqlalchemy_orm(obj, cls)

    # Note: obj.Table does not attempt to be a SQLAlchemy Table class.
    obj.Table = _make_table(obj)
    obj.relationship = _wrap_with_default_query_class(obj.relationship, cls)
    obj.dynamic_loader = _wrap_with_default_query_class(obj.dynamic_loader, cls)
    obj.event = event


def get_state(philosophy_adapter):
    """Gets the state for the philosophy adapter"""
    assert "sqlalchemy" in philosophy_adapter.extensions, (
        "The sqlalchemy extension was not registered to the current "
        "philosophy adapter.  Please make sure to call init_philosophy_adapter() "
        "first."
    )
    return philosophy_adapter.extensions["sqlalchemy"]


class _EngineConnector(object):
    def __init__(self, philosophy, philosophy_adapter, bind=None):
        self._philosophy = philosophy
        self._philosophy_adapter = philosophy_adapter
        self._engine = None
        self._connected_for = None
        self._bind = bind
        self._lock = Lock()

    def get_uri(self):
        if self._bind is None:
            return self._philosophy_adapter.config["SQLALCHEMY_DATABASE_URI"]
        binds = self._philosophy_adapter.config.get("SQLALCHEMY_BINDS") or ()
        assert self._bind in binds, (
            "Bind %r is not specified.  Set it in the SQLALCHEMY_BINDS "
            "configuration variable" % self._bind
        )
        return binds[self._bind]

    def get_engine(self):
        with self._lock:
            uri = self.get_uri()
            echo = self._philosophy_adapter.config["SQLALCHEMY_ECHO"]
            if (uri, echo) == self._connected_for:
                return self._engine

            sa_url = make_url(uri)
            options = self.get_options(sa_url, echo)
            self._engine = rv = self._philosophy.create_engine(sa_url, options)

            self._connected_for = (uri, echo)

            return rv

    def get_options(self, sa_url, echo):
        options = {}

        self._philosophy.apply_driver_hacks(self._philosophy_adapter, sa_url, options)
        if echo:
            options["echo"] = echo

        # Give the config options set by a developer explicitly priority
        # over decisions FSA makes.
        options.update(self._philosophy_adapter.config["SQLALCHEMY_ENGINE_OPTIONS"])

        # Give options set in SQLAlchemy.__init__() ultimate priority
        options.update(self._philosophy._engine_options)

        return options


class _PhilosophyState(object):
    """Remembers configuration for the (db, app) tuple."""

    def __init__(self, db):
        self.db = db
        self.connectors = {}


class _QueryProperty(object):
    def __init__(self, sa):
        self.sa = sa

    def __get__(self, obj, type):
        try:
            mapper = orm.class_mapper(type)
            if mapper:
                return type.query_class(mapper, session=self.sa.session())
        except UnmappedClassError:
            return None


class PhilosophyAdapter(object):
    """The ``PhilosophyAdapter`` is an interface between an application, e.g.
    Flask, FastAPI, etc., and Philosophy.

    The configuration for SQLAlchemy and the database engine should be stored on
    on an instance of the philosophy adapter, a philosophy adapter might be
    configured directly, e.g.::

        philosophy_adapter = PhilosophyAdapter()
        philosophy_adapter.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    Or, in some cases it might receive its configuration from the attached
    application. (TODO)
    """

    def __init__(self, app=None):
        self.app = app
        self.config = dict()
        self.extensions = dict()


class Philosophy(object):
    """Philosophy is an interface to SQLAlchemy, and a SQLAlchemy database
    session.
    """

    @property
    def engine(self):
        """Return the engine."""
        return self.get_engine()

    @property
    def metadata(self):
        """The metadata associated with ``db.Model``."""
        return self.Model.metadata

    @property
    def Query(self):
        return orm.Query

    def __init__(
        self,
        adapter: Optional[PhilosophyAdapter] = None,
        session_options: Any = None,
        metadata: Any = None,
        query_class: Any = None,
        model_class: Any = Model,
        engine_options: Any = None,
        use_async: bool = False,
    ):
        #: TODO:
        #: In Flask, this configuration is set on the application instance
        #: (i.e. app.config) and is always present when you pass the app through
        self.async_ = use_async
        self.session = self.create_scoped_session(session_options)
        self.Model = self.make_declarative_base(model_class, metadata)
        self._engine_lock = Lock()
        self._engine_options = engine_options or {}

        _include_sqlalchemy(self, query_class)
        self.set_adapter(adapter=adapter)

    def set_adapter(self, adapter=None):
        self.adapter = adapter
        if adapter is not None:
            self.init_adapter(adapter)

    def _execute_for_all_tables(self, adapter, bind, operation, skip_tables=False):
        adapter = self.get_adapter(adapter)

        if bind == "__all__":
            binds = [None] + list(adapter.config.get("SQLALCHEMY_BINDS") or ())
        elif isinstance(bind, str) or bind is None:
            binds = [bind]
        else:
            binds = bind

        for bind in binds:
            extra = {}
            if not skip_tables:
                tables = self.get_tables_for_bind(bind)
                extra["tables"] = tables
            op = getattr(self.Model.metadata, operation)
            op(bind=self.get_engine(adapter, bind), **extra)

    def init_adapter(self, adapter):
        # We intentionally don't set self.adapter = adapter,
        # to support multiple applications. If the adapter is passed
        # in the constructor, we set it and don't support multiple applications.
        if not (
            adapter.config.get("SQLALCHEMY_DATABASE_URI")
            or adapter.config.get("SQLALCHEMY_BINDS")
        ):
            raise RuntimeError(
                "Either SQLALCHEMY_DATABASE_URI or " "SQLALCHEMY_BINDS needs to be set."
            )

        adapter.config.setdefault("SQLALCHEMY_DATABASE_URI", None)
        adapter.config.setdefault("SQLALCHEMY_BINDS", None)
        adapter.config.setdefault("SQLALCHEMY_ECHO", False)
        adapter.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
        adapter.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})

        adapter.extensions["sqlalchemy"] = _PhilosophyState(self)

    def apply_driver_hacks(self, philosophy_adapter, sa_url, options):
        """This method is called before engine creation and used to inject
        driver specific hacks into the options.  The `options` parameter is
        a dictionary of keyword arguments that will then be used to call
        the :func:`sqlalchemy.create_engine` function.
        The default implementation provides some saner defaults for things
        like pool sizes for MySQL and sqlite.  Also it injects the setting of
        `SQLALCHEMY_NATIVE_UNICODE`.
        """
        if sa_url.drivername.startswith("mysql"):
            sa_url.query.setdefault("charset", "utf8")
            if sa_url.drivername != "mysql+gaerdbms":
                options.setdefault("pool_size", 10)
                options.setdefault("pool_recycle", 7200)
        elif sa_url.drivername == "sqlite":
            pool_size = options.get("pool_size")
            if sa_url.database in (None, "", ":memory:"):
                from sqlalchemy.pool import StaticPool

                options["poolclass"] = StaticPool
                if "connect_args" not in options:
                    options["connect_args"] = {}
                options["connect_args"]["check_same_thread"] = False

                # we go to memory and the pool size was explicitly set
                # to 0 which is fail.  Let the user know that
                if pool_size == 0:
                    raise RuntimeError(
                        "SQLite in memory database with an "
                        "empty queue not possible due to data loss."
                    )
            # if pool size is None or explicitly set to 0 we assume the
            # user did not want a queue for this sqlite connection and
            # hook in the null pool.
            elif not pool_size:
                from sqlalchemy.pool import NullPool

                options["poolclass"] = NullPool

    def create_all(self, bind="__all__", philosophy_adapter=None):
        """Creates all tables."""
        self._execute_for_all_tables(philosophy_adapter, bind, "create_all")

    def create_scoped_session(self, options=None):
        if options is None:
            options = {}

        options.setdefault("query_cls", self.Query)
        return orm.scoped_session(self.create_session(options))

    def create_session(self, options):
        if self.async_:
            return self._create_async_session(options)
        else:
            return self._create_session(options)

    def _create_async_session(self, options):
        return orm.sessionmaker(class_=PhilosophyAsyncSession, db=self, **options)

    def _create_session(self, options):
        return orm.sessionmaker(class_=PhilosophySession, db=self, **options)

    def drop_all(self, bind="__all__", philosophy_adapter=None):
        """Drops all tables."""
        self._execute_for_all_tables(philosophy_adapter, bind, "drop_all")

    def get_binds(self, adapter=None):
        """Returns a dictionary with a table->engine mapping.
        This is suitable for use of sessionmaker(binds=db.get_binds(app)).
        """
        adapter = self.get_adapter(adapter)
        binds = [None] + list(adapter.config.get("SQLALCHEMY_BINDS") or ())
        retval = {}
        for bind in binds:
            engine = self.get_engine(adapter, bind)
            tables = self.get_tables_for_bind(bind)
            retval.update(dict((table, engine) for table in tables))
        return retval

    def get_adapter(self, adapter=None):
        if self.adapter is not None:
            return self.adapter

        raise RuntimeError(
            "No philosophy adapter found. Either work inside a view function or "
            "push a philosophy adapter context. See "
            "<TODO>."
        )

    def get_engine(self, adapter=None, bind=None):
        """Returns a specific engine."""
        adapter = self.get_adapter(adapter)
        state = get_state(adapter)

        with self._engine_lock:
            connector = state.connectors.get(bind)

            if connector is None:
                connector = self.make_connector(adapter, bind)
                state.connectors[bind] = connector

            return connector.get_engine()

    def create_engine(self, sa_url, engine_opts):
        """
        Override this method to have final say over how the SQLAlchemy engine
        is created.

        In most cases, you will want to use ``'SQLALCHEMY_ENGINE_OPTIONS'``
        config variable or set ``engine_options`` for :func:`SQLAlchemy`.
        """
        if self.async_:
            return self._create_async_engine(sa_url, engine_opts)
        else:
            return self._create_engine(sa_url, engine_opts)

    def _create_async_engine(self, sa_url, engine_opts):
        """Create an async engine."""
        engine = create_async_engine(sa_url, **engine_opts)
        return engine

    def _create_engine(self, sa_url, engine_opts):
        """Create an engine."""
        engine = sqlalchemy.create_engine(sa_url, **engine_opts)
        return engine

    def get_tables_for_bind(self, bind=None):
        """Returns a list of all tables relevant for a bind."""
        result = []
        for table in iter(self.Model.metadata.tables.values()):
            if table.info.get("bind_key") == bind:
                result.append(table)
        return result

    def make_connector(self, adapter=None, bind=None):
        """Creates the connector for a given state and bind."""
        return _EngineConnector(self, self.get_adapter(adapter), bind)

    def make_declarative_base(self, model, metadata=None):
        if not isinstance(model, DeclarativeMeta):
            model = declarative_base(
                cls=model, name="Model", metadata=metadata, metaclass=DefaultMeta
            )

        # if user passed in a declarative base and a metaclass for some reason,
        # make sure the base uses the metaclass
        if metadata is not None and model.metadata is not metadata:
            model.metadata = metadata

        if not getattr(model, "query_class", None):
            model.query_class = self.Query

        model.query = _QueryProperty(self)
        return model

    def __repr__(self):
        return "<%s engine=%r>" % (
            self.__class__.__name__,
            self.engine.url if self.adapter else None,
        )


class PhilosophyAsyncSession(AsyncSession):
    def __init__(self, db, autocommit=False, autoflush=True, **options):
        #: The philosophy adapter that this session belongs to.
        self.adapter = adapter = db.get_adapter()
        bind = options.pop("bind", None) or db.engine
        binds = options.pop("binds", db.get_binds(adapter))

        AsyncSession.__init__(
            self,
            bind=bind,
            binds=binds,
            autocommit=autocommit,
            autoflush=autoflush,
            **options,
        )

    def get_bind(
        self,
        mapper: Optional = None,
        clause: Optional = None,
        bind: Optional = None,
        **kw: Any,
    ) -> Union[Engine, Connection]:
        """Return the engine or connection for a given model or
        table, using the ``__bind_key__`` if it is set.
        """
        # mapper is None if someone tries to just get a connection
        if mapper is not None:
            try:
                # SA >= 1.3
                persist_selectable = mapper.persist_selectable
            except AttributeError:
                # SA < 1.3
                persist_selectable = mapper.mapped_table

            info = getattr(persist_selectable, "info", {})
            bind_key = info.get("bind_key")
            if bind_key is not None:
                state = get_state(self.adapter)
                return state.db.get_engine(self.adapter, bind=bind_key)
        return AsyncSession.get_bind(self, mapper, clause)


class PhilosophySession(SessionBase):
    def __init__(self, db, autocommit=False, autoflush=True, **options):
        #: The philosophy adapter that this session belongs to.
        self.adapter = adapter = db.get_adapter()
        bind = options.pop("bind", None) or db.engine
        binds = options.pop("binds", db.get_binds(adapter))

        SessionBase.__init__(
            self,
            autocommit=autocommit,
            autoflush=autoflush,
            bind=bind,
            binds=binds,
            **options,
        )

    def get_bind(self, mapper=None, clause=None):
        """Return the engine or connection for a given model or
        table, using the ``__bind_key__`` if it is set.
        """
        # mapper is None if someone tries to just get a connection
        if mapper is not None:
            try:
                # SA >= 1.3
                persist_selectable = mapper.persist_selectable
            except AttributeError:
                # SA < 1.3
                persist_selectable = mapper.mapped_table

            info = getattr(persist_selectable, "info", {})
            bind_key = info.get("bind_key")
            if bind_key is not None:
                state = get_state(self.adapter)
                return state.db.get_engine(self.adapter, bind=bind_key)
        return SessionBase.get_bind(self, mapper=mapper, clause=clause)
