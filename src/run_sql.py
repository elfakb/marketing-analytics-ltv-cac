"""Run every sql/*.sql file against the SQLite DB and print the results.

Run:  python -m src.run_sql          (after python -m src.marts)
"""
import sqlite3

import pandas as pd

from src.config import DB_PATH, SQL_DIR

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 30)


def main():
    if not DB_PATH.exists():
        raise SystemExit("Database not found. Run `python -m src.marts` first.")
    with sqlite3.connect(DB_PATH) as con:
        for f in sorted(SQL_DIR.glob("*.sql")):
            print(f"\n=== {f.name} ===")
            print(pd.read_sql_query(f.read_text(), con).to_string(index=False))


if __name__ == "__main__":
    main()
