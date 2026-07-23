PY ?= .venv/bin/python

.PHONY: census
census:  ## Read-only corpus census -> logs/audits/census-{date}.md (run after every connector run)
	PYTHONPATH=. $(PY) scripts/corpus_census.py
