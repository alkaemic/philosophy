import mock
import pytest
from ..philosophy import utils


@pytest.fixture
def mock_sqlalchemy(mocker):
    _mock = mocker.patch.object(utils, "sqlalchemy")
    return _mock


def test_parse_version():
    assert utils.parse_version("1.2.3") == (1, 2, 3)
    assert utils.parse_version("1.2") == (1, 2, 0)
    assert utils.parse_version("1") == (1, 0, 0)


def test_sqlalchemy_version(mock_sqlalchemy):
    mock_sqlalchemy.__version__ = "1.3"

    assert not utils.sqlalchemy_version("<", "1.3")
    assert not utils.sqlalchemy_version(">", "1.3")
    assert utils.sqlalchemy_version("<=", "1.3")
    assert utils.sqlalchemy_version("==", "1.3")
    assert utils.sqlalchemy_version(">=", "1.3")

    mock_sqlalchemy.__version__ = "1.2.99"

    assert utils.sqlalchemy_version("<", "1.3")
    assert not utils.sqlalchemy_version(">", "1.3")
    assert utils.sqlalchemy_version("<=", "1.3")
    assert not utils.sqlalchemy_version("==", "1.3")
    assert not utils.sqlalchemy_version(">=", "1.3")
