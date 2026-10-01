.PHONY: install test lint data train evaluate all serve demo docker

install:
	pip install -e ".[dev,api,lab]"

test:
	pytest --cov --cov-report=term-missing

lint:
	ruff check . && ruff format --check . && mypy

data:
	python -m sikaguard_lab.build

train:
	python -m sikaguard_lab.train

evaluate:
	python -m sikaguard_lab.evaluate

all: data train evaluate test

serve:
	uvicorn sikaguard.api:app --port 8000

demo:
	python demo/app.py

docker:
	docker build -t sikaguard-api .
