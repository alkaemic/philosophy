Philosophy
==========

Philosophy is intended to act as a universal interface to a database and the
underlying session, allowing code to define models, run queries, and otherwise
do everything that you would want to do with a dtabase while maintaining a clear
separation from an application's usage of those database conenctions.

The project is titled **philosophy** because we believe that defining your
database interaction model is a fundamental part of your application but it
shouldn't matter whether you are using SQLAlchemy or another database connection
toolkit. If you happen to run two or more frameworks, and need to share some
code, you can create different database managers that allow you to adapt to your
needs without having to redefine how represent your models or write your
queries.

Philosophy was heavily inspired by [Flask-SQLAlchemy][_flask_sqlalchemy].


[_flask_sqlalchemy]: https://github.com/pallets/flask-sqlalchemy