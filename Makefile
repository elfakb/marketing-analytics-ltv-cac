.PHONY: all data marts report sql test dashboard clean
PY ?= python

all: data marts report        ## full pipeline

data:       ## 1) generate synthetic raw data
	$(PY) -m src.generate_data
marts:      ## 2) LTV, marts, Power BI CSVs, SQLite
	$(PY) -m src.marts
report:     ## 3) figures + findings.md
	$(PY) -m src.analysis
sql:        ## run the SQL scripts
	$(PY) -m src.run_sql
test:
	$(PY) -m pytest -q
dashboard:
	streamlit run dashboard/app.py
clean:
	rm -f data/raw/*.csv data/processed/* powerbi/data/* reports/figures/* reports/findings.md
