.DEFAULT_GOAL := help

#: The path to this Makefile.
MAKEFILE_PATH := $(abspath $(lastword $(MAKEFILE_LIST)))

#: The root directory of the project, also the directory that the
#: Makefile is in.
ROOT_DIR := $(dir $(MAKEFILE_PATH))

owner := $(shell whoami)

group := $(shell id -gn)


default: help


### <summary>
### Displays a help screen and listing of commands that can be run through Make.
### </summary>
.PHONY: help
help:
	@echo "Command Tool v1.0"
	@echo ""
	@echo "\033[1mUSAGE\033[0m"
	@echo "  make [COMMAND]"
	@echo ""
	@echo "\033[1mUSAGE EXAMPLES\033[0m"
	@echo ""
	@echo "    Build Docker images for your environment:"
	@echo "    $$ make build"
	@echo ""
	@echo ""
	@echo "\033[1mCOMMANDS\033[0m"
	@echo "  build                 Build Docker images."
	@echo "  clean                 Clean Docker images, containers, clear warmed files."
	@echo "  init                  Initialize the project and exectute the build"
	@echo "                        command."
	@echo "  start                 Starts all service containers."
	@echo "  status                Show the status of all containers."
	@echo "  stop                  Stops and removes all service containers, "
	@echo "                        networks, images, and volumes."
	@echo "  test                  Runs test suite and generates code coverage report."
	@echo ""
	@echo "\033[1mDATABASE\033[0m"
	@echo "  db.build              Build Docker images."
	@echo "  db.create             Create the database."
	@echo "  db.drop               Drop the database."
	@echo "  db.rebuild            Rebuild the database by dropping, creating, and"
	@echo "                        building it."
	@echo "  db.populate           Populate the database with data."
	@echo ""


.PHONY: black
black:
	@python -W always::DeprecationWarning -m black philosophy


### <summary>
### </summary>
.PHONY: .clean-pyx
.clean-pyx:
	@echo "> Cleaning .pyc, .pyo files..."
	@find . -name '*.pyc' -exec rm -f {} +
	@find . -name '*.pyo' -exec rm -f {} +
	@find . -name '*.py,cover' -exec rm -f {} +
	@find . -name '__pycache__' -exec rm -rf {} +


### <summary>
### </summary>
.PHONY: .fix-permissions
.fix-permissions:
	@chown -R $(owner):$(group) $(ROOT_DIR)

.PHONY: clean
clean: .clean-pyx


### <summary>
### Initializes the project on macOS.
###
### After setting up initial development environment dependencies for macOS,
### this will call the shared `init` script which will generate SSL certificates
### for development and build the Docker images.
###
### E.g.
###
###   $ make init.macos
###
### </summary>
.PHONY: init.macos
init.macos: init.macos.deps


.PHONY: init.macos.deps
init.macos.deps:
	@brew install python@3.10 openssl rust
	@curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -


.PHONY: lint
lint:
	@python -W always::DeprecationWarning -m flake8


.PHONY: logs
logs:
	@docker compose logs -f


### <summary>
### </summary>
.PHONY: test
test:
	@SQLALCHEMY_WARN_20=1 python -W always::DeprecationWarning -m pytest
