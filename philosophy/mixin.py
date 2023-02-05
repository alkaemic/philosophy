import inspect as _inspect


def mixin_sqlalchemy(obj, cls):
    import sqlalchemy

    _module = sqlalchemy
    _modules = sorted(
        name
        for name, obj in _module.__dict__.items()
        if not (name.startswith("_") or _inspect.ismodule(obj))
    )

    for module_name in _modules:
        if not hasattr(obj, module_name):
            setattr(obj, module_name, getattr(_module, module_name))
    return obj


def mixin_sqlalchemy_orm(obj, cls):
    import sqlalchemy.orm

    _module = sqlalchemy.orm
    _modules = sorted(
        name
        for name, obj in _module.__dict__.items()
        if not (name.startswith("_") or _inspect.ismodule(obj))
    )

    for module_name in _modules:
        if not hasattr(obj, module_name):
            setattr(obj, module_name, getattr(_module, module_name))
    return obj
