.PHONY: install test lint check plan generate validate serve docker-up docker-down

install:
	python -m pip install -e ".[dev]"

test:
	pytest --cov=cardioclaw --cov-report=term-missing

lint:
	ruff check .
	python -m compileall -q cardioclaw cardio_claw.py serve.py

check: lint test

plan:
	cardioclaw plan --type weekly

generate:
	cardioclaw generate --type weekly

validate:
	cardioclaw validate

serve:
	cardioclaw serve

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down
