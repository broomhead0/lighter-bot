VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: venv install run test fmt lint precommit docker-build docker-run

venv:
	python3.11 -m venv $(VENV)

install: venv
	$(PIP) install -r requirements.txt -r dev-requirements.txt
	pre-commit install

run:
	$(PY) -m core.main

test:
	$(PY) -m pytest -q

fmt:
	$(VENV)/bin/black .

lint:
	$(VENV)/bin/ruff check --fix .

precommit:
	pre-commit run --all-files

docker-build:
	docker build -t lighter-bot -f .devcontainer/Dockerfile .

docker-run:
	docker run --rm -it -p 9100:9100 -v $(PWD):/workspaces/lighter-bot lighter-bot
