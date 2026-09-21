PYTHON ?= python3
NPM ?= npm

.PHONY: install test test-backend test-frontend dev cluster deploy smoke clean

install:
	$(PYTHON) -m pip install -r backend/requirements-dev.txt -r workload/requirements-dev.txt -r load-tests/requirements.txt
	cd frontend && $(NPM) install

test: test-backend test-frontend

test-backend:
	PYTHONPATH=backend $(PYTHON) -m pytest backend/tests -q
	PYTHONPATH=workload $(PYTHON) -m pytest workload/tests -q

test-frontend:
	cd frontend && $(NPM) test -- --run
	cd frontend && $(NPM) run build

dev:
	docker compose up --build

cluster:
	./scripts/bootstrap-kind.sh

deploy:
	./scripts/deploy-local.sh

smoke:
	./scripts/smoke-test.sh

fixtures:
	./scripts/run-fixtures.sh

clean:
	docker compose down --remove-orphans
