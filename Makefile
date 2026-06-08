.PHONY: pipeline ingest validate features collinearity train backtest test clean install

PYTHON := python
PIPELINE := $(PYTHON) -m src.avm.pipeline

install:
	pip install -r requirements.txt

pipeline:
	$(PIPELINE) --all

ingest:
	$(PIPELINE) --ingest

validate:
	$(PIPELINE) --validate

features:
	$(PIPELINE) --features

collinearity:
	$(PIPELINE) --collinearity

train:
	$(PIPELINE) --train

backtest:
	$(PIPELINE) --backtest

synthetic:
	$(PIPELINE) --all --synthetic

test:
	$(PYTHON) -m pytest tests/ -v

clean:
	rm -f data/interim/*.csv data/processed/*.csv
	rm -f reports/*.csv reports/*.html reports/*.png
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
