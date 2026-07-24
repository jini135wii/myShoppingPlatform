"""app.db 내용을 사람이 읽기 좋게 출력하는 개발용 조회 스크립트.

사용법:
  ./venv/bin/python tools/dbview.py            # 모든 테이블 스키마 + 전체 행
  ./venv/bin/python tools/dbview.py users      # 특정 테이블만
  ./venv/bin/python tools/dbview.py "SELECT username FROM users"   # 임의 SQL
"""
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.db")


def print_rows(cur):
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    if cols:
        print(" | ".join(cols))
        print("-" * 60)
    for r in rows:
        print(" | ".join(str(v) for v in r))
    print(f"({len(rows)} rows)\n")


def main():
    con = sqlite3.connect(DB)
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    if arg and arg.strip().lower().startswith("select"):
        print_rows(con.execute(arg))
        return

    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )]
    targets = [arg] if arg else tables

    for t in targets:
        print(f"### {t}")
        schema = con.execute(
            "SELECT sql FROM sqlite_master WHERE name=?", (t,)
        ).fetchone()
        if schema:
            print(schema[0])
            print()
        print_rows(con.execute(f"SELECT * FROM {t}"))


if __name__ == "__main__":
    main()
