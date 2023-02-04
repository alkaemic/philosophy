import pytest
from .. import philosophy
from datetime import datetime


@pytest.fixture
def db(database_manager):
    return philosophy.Philosophy(database_manager)


@pytest.fixture
def database_manager():
    database_manager = philosophy.PhilosophyAdapter()
    database_manager.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    return database_manager


@pytest.fixture
def Todo(db):
    class Todo(db.Model):
        __tablename__ = "todos"
        id = db.Column("todo_id", db.Integer, primary_key=True)
        title = db.Column(db.String(60))
        text = db.Column(db.String)
        done = db.Column(db.Boolean)
        pub_date = db.Column(db.DateTime)

        def __init__(self, title, text):
            self.title = title
            self.text = text
            self.done = False
            self.pub_date = datetime.utcnow()

    db.create_all()
    yield Todo
    db.drop_all()
