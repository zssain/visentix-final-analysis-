PY ?= .venv/bin/python

.PHONY: census guards report-css
census:  ## Read-only corpus census -> logs/audits/census-{date}.md (run after every connector run)
	PYTHONPATH=. $(PY) scripts/corpus_census.py

guards:  ## Run the same repository-truth guards as CI
	$(PY) scripts/build_banned_terms.py --check
	$(PY) scripts/build_report_css.py --check
	$(PY) scripts/check_acronyms.py
	$(PY) scripts/check_colors.py
	node scripts/check_contrast.mjs
	$(PY) scripts/check_dead_css.py
	$(PY) scripts/check_docs_layout.py
	$(PY) scripts/check_hedging.py
	$(PY) scripts/check_labels.py
	$(PY) scripts/check_masking.py
	$(PY) scripts/check_mocks.py
	$(PY) scripts/check_routes.py
	$(PY) scripts/check_specs.py

report-css:  ## Regenerate the WeasyPrint palette from web/src/theme.css
	$(PY) scripts/build_report_css.py
