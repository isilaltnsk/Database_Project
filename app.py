"""CommonCents - Flask application entry point (Milestone 3 skeleton)."""
import os
from pathlib import Path

from flask import Flask, abort, jsonify, request

from db import fetch_all

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")

QUERY_DIR = Path(__file__).parent / "queries"


def run_query_file(name, params):
    """Execute one planned complex query (queries/<name>.sql) via Flask."""
    path = QUERY_DIR / f"{name}.sql"
    if not path.is_file():
        abort(404)
    return fetch_all(path.read_text(encoding="utf-8"), params)


@app.route("/")
def index():
    return jsonify(app="CommonCents", status="running")


@app.route("/db-check")
def db_check():
    """Raw SQL #1: proves the database connection works."""
    rows = fetch_all("SELECT version() AS version, NOW() AS server_time")
    return jsonify(
        version=rows[0]["version"], server_time=str(rows[0]["server_time"])
    )


@app.route("/users")
def users():
    """Raw SQL #2: list active users (parametrized, paginated)."""
    limit = request.args.get("limit", 10, type=int)
    rows = fetch_all(
        "SELECT user_id, username, email, role FROM Users "
        "WHERE is_active = %(active)s ORDER BY user_id LIMIT %(limit)s",
        {"active": True, "limit": limit},
    )
    return jsonify(rows)


@app.route("/stats")
def stats():
    """Raw SQL #3: row counts of all tables (used for the NFR-05 check)."""
    sql = """
        SELECT 'Users' AS table_name, COUNT(*) AS rows FROM Users
        UNION ALL SELECT 'Accounts', COUNT(*) FROM Accounts
        UNION ALL SELECT 'Categories', COUNT(*) FROM Categories
        UNION ALL SELECT 'Transactions', COUNT(*) FROM Transactions
        UNION ALL SELECT 'SharedBudgets', COUNT(*) FROM SharedBudgets
        UNION ALL SELECT 'BudgetMembers', COUNT(*) FROM BudgetMembers
        UNION ALL SELECT 'SpendingLimits', COUNT(*) FROM SpendingLimits
        UNION ALL SELECT 'Contributions', COUNT(*) FROM Contributions
        UNION ALL SELECT 'FinancialGoals', COUNT(*) FROM FinancialGoals
        UNION ALL SELECT 'RecurringPayments', COUNT(*) FROM RecurringPayments
    """
    return jsonify(fetch_all(sql))


@app.route("/queries/<name>")
def planned_query(name):
    """Run a planned query, e.g. /queries/q03_monthly_income_expense."""
    params = {
        "user_id": request.args.get("user_id", 2, type=int),
        "budget_id": request.args.get("budget_id", 1, type=int),
        "year": request.args.get("year", 2026, type=int),
    }
    return jsonify(run_query_file(name, params))


if __name__ == "__main__":
    app.run(debug=True)
