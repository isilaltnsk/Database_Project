"""Populate CommonCents with realistic, consistent sample data.

Usage:
    python populate.py                  # load into the database (.env)
    python populate.py --scale 10       # ~10x data for the NFR-05 test
    python populate.py --sql-out data.sql   # write INSERTs, no DB needed

Rows are generated in dependency order (Users -> Categories -> Accounts ->
SharedBudgets -> BudgetMembers -> SpendingLimits -> Transactions ->
Contributions -> FinancialGoals -> RecurringPayments), so every foreign key
points to an existing row. The random seed is fixed: runs are repeatable.
All sample users share the demo password "Password123!".
Names, dates and amounts come from the Faker library (fixed seed).
"""
import argparse
import random
import re
from datetime import date, datetime, timedelta
from decimal import Decimal

from faker import Faker
from werkzeug.security import generate_password_hash

TODAY = date(2026, 11, 27)
START = TODAY - timedelta(days=365)      # data covers the last 12 months
FAKE = Faker("tr_TR")

DEFAULT_CATS = ["Salary", "Freelance", "Gifts", "Groceries", "Rent",
                "Utilities", "Transport", "Dining Out", "Entertainment",
                "Health", "Shopping", "Education", "Insurance", "Clothing",
                "Charity"]
INCOME_CATS = {"Salary", "Freelance", "Gifts"}
CUSTOM_CATS = ["Pet Care", "Gym", "Coffee", "Hobbies", "Travel",
               "Subscriptions"]
# expense category -> (min, max) typical amount
EXPENSE_RANGE = {
    "Groceries": (8, 120), "Rent": (200, 700), "Utilities": (15, 90),
    "Transport": (2, 40), "Dining Out": (6, 70), "Entertainment": (5, 60),
    "Health": (10, 150), "Shopping": (10, 250), "Education": (15, 200),
    "Pet Care": (8, 80), "Gym": (15, 50), "Coffee": (2, 9),
    "Hobbies": (10, 100), "Travel": (30, 400), "Subscriptions": (3, 20),
    "Insurance": (30, 200), "Clothing": (15, 180), "Charity": (5, 100),
}
EXPENSE_WEIGHT = {"Groceries": 18, "Dining Out": 12, "Transport": 14,
                  "Shopping": 8, "Entertainment": 7, "Utilities": 5,
                  "Health": 4, "Education": 2, "Rent": 0}
BUDGET_NAMES = ["Household 2026", "Roommates Flat 4B", "Family Holiday Fund",
                "Couple Groceries", "Student House", "Office Lunch Club",
                "Wedding Savings", "Weekend Trips", "Parents Support",
                "Home Renovation"]
GOAL_NAMES = ["Emergency Fund", "New Laptop", "Summer Holiday", "Car Down "
              "Payment", "Wedding", "Moving Costs", "Masters Tuition"]
RECURRING = [("Rent", "Rent", 250, 650, "monthly"),
             ("Netflix", "Entertainment", 8, 15, "monthly"),
             ("Gym Membership", "Health", 20, 45, "monthly"),
             ("Mobile Plan", "Utilities", 10, 25, "monthly"),
             ("Internet", "Utilities", 12, 30, "monthly"),
             ("Course Fee", "Education", 40, 120, "weekly"),
             ("Insurance", "Insurance", 150, 400, "yearly")]

COLUMNS = {
    "Users": "user_id, username, email, password_hash, role, is_active, "
             "created_at",
    "Categories": "category_id, name, is_default, user_id",
    "Accounts": "account_id, user_id, name, type, balance, created_at",
    "SharedBudgets": "budget_id, owner_id, name, total_limit, start_date, "
                     "end_date",
    "BudgetMembers": "budget_id, user_id, role, joined_at, is_active",
    "SpendingLimits": "limit_id, budget_id, category_id, max_amount",
    "Transactions": "transaction_id, account_id, category_id, budget_id, "
                    "amount, date, type, description, created_at",
    "Contributions": "contribution_id, budget_id, user_id, amount, date",
    "FinancialGoals": "goal_id, user_id, account_id, name, target_amount, "
                      "current_amount, deadline",
    "RecurringPayments": "recurring_id, account_id, category_id, name, "
                         "amount, frequency, next_date",
}
SERIALS = {"Users": "user_id", "Categories": "category_id",
           "Accounts": "account_id", "SharedBudgets": "budget_id",
           "SpendingLimits": "limit_id", "Transactions": "transaction_id",
           "Contributions": "contribution_id", "FinancialGoals": "goal_id",
           "RecurringPayments": "recurring_id"}


def money(low, high):
    return FAKE.pydecimal(left_digits=6, right_digits=2, positive=True,
                          min_value=low, max_value=high)


def rand_date(start, end):
    return FAKE.date_between(start_date=start, end_date=end)


def at_noon(day):
    return datetime(day.year, day.month, day.day, 12, 0, 0)


def ascii_name(text):
    text = text.translate(str.maketrans("\u011f\u00fc\u015f\u0131\u00f6"
                                        "\u00e7\u011e\u00dc\u015e\u0130"
                                        "\u00d6\u00c7", "gusiocGUSIOC"))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def generate(scale=1):
    """Return {table: [row tuples]} in dependency order."""
    random.seed(302)
    Faker.seed(302)
    rows = {t: [] for t in COLUMNS}
    n_users = 50 * scale
    pw_hash = generate_password_hash("Password123!", method="pbkdf2:sha256")

    # ---- Users: 1 Admin + (n-1) Users, registered over the last 12 months
    names, active, reg = {}, {}, {}
    for uid in range(1, n_users + 1):
        if uid == 1:
            uname, role = "admin", "Admin"
        else:
            uname = (ascii_name(FAKE.first_name()) + "."
                     + ascii_name(FAKE.last_name()))
            role = "User"
            while uname in names.values():
                uname += str(random.randint(1, 99))
        names[uid] = uname
        active[uid] = uid == 1 or random.random() > 0.08
        reg[uid] = rand_date(START, START + timedelta(days=270))
        rows["Users"].append((uid, uname, f"{uname}@example.com", pw_hash,
                              role, active[uid], at_noon(reg[uid])))
    regular = [u for u in names if u > 1]
    active_regular = [u for u in regular if active[u]]

    # ---- Categories: 15 defaults, custom ones for about half the users
    cat_id, cat_name, user_cats = 0, {}, {u: [] for u in names}
    for name in DEFAULT_CATS:
        cat_id += 1
        cat_name[cat_id] = name
        rows["Categories"].append((cat_id, name, True, None))
    for uid in regular:
        if random.random() < 0.5:
            for name in random.sample(CUSTOM_CATS, random.randint(1, 3)):
                cat_id += 1
                cat_name[cat_id] = name
                user_cats[uid].append(cat_id)
                rows["Categories"].append((cat_id, name, False, uid))
    default_ids = {n: i for i, n in cat_name.items() if i <= len(DEFAULT_CATS)}
    expense_defaults = [default_ids[n] for n in DEFAULT_CATS
                        if n not in INCOME_CATS]

    # ---- Accounts: 2-4 per user (opening balance; final balance later)
    acc_owner, acc_type, opening, user_accs = {}, {}, {}, {}
    acc_id = 0
    for uid in names:
        plan = [("Main Checking", "bank", (500, 5000)),
                ("Wallet", "cash", (1500, 4000))]
        if random.random() < 0.8:
            plan.append(("Savings", "savings", (1000, 10000)))
        if random.random() < 0.35:
            plan.append(("Credit Card", "credit_card", (0, 0)))
        user_accs[uid] = []
        for name, kind, (lo, hi) in plan:
            acc_id += 1
            acc_owner[acc_id], acc_type[acc_id] = uid, kind
            opening[acc_id] = money(lo, hi) if hi else Decimal("0.00")
            user_accs[uid].append(acc_id)
            rows["Accounts"].append([acc_id, uid, name, kind, None,
                                     at_noon(reg[uid])])

    # ---- SharedBudgets and BudgetMembers (3-5 members, admin never)
    members, budget_span = {}, {}
    for b in range(1, 10 * scale + 1):
        owner = random.choice(active_regular)
        start = rand_date(START, START + timedelta(days=120))
        end = start + timedelta(days=random.choice([180, 270, 364]))
        budget_span[b] = (start, end)
        rows["SharedBudgets"].append(
            (b, owner, BUDGET_NAMES[(b - 1) % len(BUDGET_NAMES)],
             money(2000, 15000), start, end))
        others = random.sample([u for u in active_regular if u != owner],
                               random.randint(2, 4))
        members[b] = [owner] + others
        rows["BudgetMembers"].append(
            (b, owner, "Budget Manager", at_noon(start), True))
        for i, u in enumerate(others):
            role = "Budget Manager" if i == 0 and random.random() < .3 \
                else "Regular"
            rows["BudgetMembers"].append(
                (b, u, role, at_noon(start + timedelta(days=i + 1)), True))
        if random.random() < 0.4:   # a former member (soft-deleted)
            ex = random.choice([u for u in regular if u not in members[b]])
            rows["BudgetMembers"].append(
                (b, ex, "Regular", at_noon(start + timedelta(days=3)),
                 False))

    # ---- Transactions
    balance = dict(opening)
    tx_id = 0
    budget_spent = {}

    def add_tx(acc, cid, bud, amount, day, kind, text):
        nonlocal tx_id
        tx_id += 1
        balance[acc] += amount if kind == "income" else -amount
        if bud:
            key = (bud, cid)
            budget_spent[key] = budget_spent.get(key, 0) + amount
        rows["Transactions"].append(
            (tx_id, acc, cid, bud, amount, day, kind, text, at_noon(day)))

    weights = [EXPENSE_WEIGHT.get(cat_name[c], 3) for c in expense_defaults]
    for uid in names:
        first_day = reg[uid]
        last_day = TODAY - timedelta(days=7) if active[uid] \
            else TODAY - timedelta(days=90)
        if last_day <= first_day:
            continue
        span = (last_day - first_day).days
        bank = user_accs[uid][0]
        salary = money(1500, 6000)
        day = date(first_day.year, first_day.month, 1)
        while day <= last_day:
            if day >= first_day:
                add_tx(bank, default_ids["Salary"], None, salary, day,
                       "income", "Monthly salary")
            day = (day + timedelta(days=32)).replace(day=1)
        for _ in range(random.randint(0, 3)):
            cid = default_ids[random.choice(["Freelance", "Gifts"])]
            add_tx(random.choice(user_accs[uid]), cid, None,
                   money(50, 600), rand_date(first_day, last_day),
                   "income", "Extra income")
        my_budgets = [b for b, m in members.items() if uid in m]
        for _ in range(int(span * random.uniform(0.35, 0.5))):
            day = rand_date(first_day, last_day)
            bud = None
            for b in my_budgets:
                s, e = budget_span[b]
                if s <= day <= e and random.random() < 0.15:
                    bud = b
                    break
            if bud:     # budget expenses use default categories only
                cid = random.choices(expense_defaults, weights)[0]
            else:
                pool = expense_defaults + user_cats[uid]
                w = weights + [3] * len(user_cats[uid])
                cid = random.choices(pool, weights=w)[0]
            lo, hi = EXPENSE_RANGE[cat_name[cid]]
            spend = [a for a in user_accs[uid] if acc_type[a] != "savings"]
            acc = random.choices(
                spend, [{"bank": 6, "cash": 2}.get(acc_type[a], 2)
                        for a in spend])[0]
            add_tx(acc, cid, bud, money(lo, hi), day, "expense",
                   cat_name[cid])

    for acc in rows["Accounts"]:
        acc[4] = balance[acc[0]]
    rows["Accounts"] = [tuple(a) for a in rows["Accounts"]]

    # ---- SpendingLimits: 3-6 per budget, sized around actual spending
    lim_id = 0
    for b in budget_span:
        for cid in random.sample(expense_defaults, random.randint(3, 6)):
            lim_id += 1
            spent = budget_spent.get((b, cid), 0)
            amount = (spent * Decimal(str(random.uniform(0.7, 1.4)))
                      ).quantize(Decimal("0.01")) if spent else money(
                          150, 600)
            rows["SpendingLimits"].append(
                (lim_id, b, cid, max(amount, Decimal("50.00"))))

    # ---- Contributions (active members, inside the budget period)
    con_id = 0
    for b, mem in members.items():
        s, e = budget_span[b]
        for u in mem:
            for _ in range(random.randint(3, 6)):
                con_id += 1
                rows["Contributions"].append(
                    (con_id, b, u, money(50, 500),
                     rand_date(s, min(e, TODAY))))

    # ---- FinancialGoals (1:1 with a savings account of the same owner)
    goal_id = 0
    for acc in sorted(acc_owner):
        if acc_type[acc] == "savings" and random.random() < 0.7:
            goal_id += 1
            target = money(1500, 20000)
            rows["FinancialGoals"].append(
                (goal_id, acc_owner[acc], acc,
                 GOAL_NAMES[goal_id % len(GOAL_NAMES)], target,
                 (target * Decimal(str(random.uniform(.05, .95)))
                  ).quantize(Decimal("0.01")),
                 rand_date(TODAY + timedelta(days=30),
                           TODAY + timedelta(days=600))))

    # ---- RecurringPayments (next_date close to today)
    rec_id = 0
    for uid in names:
        count = random.choices([0, 1, 2, 3], [1, 4, 3, 2])[0]
        for name, cat, lo, hi, freq in random.sample(RECURRING, count):
            rec_id += 1
            acc = random.choice([a for a in user_accs[uid]
                                 if acc_type[a] != "savings"])
            rows["RecurringPayments"].append(
                (rec_id, acc, default_ids[cat], name, money(lo, hi), freq,
                 rand_date(TODAY - timedelta(days=7),
                           TODAY + timedelta(days=14))))
    return rows


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, Decimal)):
        return str(v)
    if isinstance(v, datetime):
        return f"'{v.isoformat(sep=' ')}'"
    if isinstance(v, date):
        return f"'{v.isoformat()}'"
    return "'" + str(v).replace("'", "''") + "'"


def write_sql(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for table, data in rows.items():
            for row in data:
                vals = ", ".join(literal(v) for v in row)
                f.write(f"INSERT INTO {table} ({COLUMNS[table]}) "
                        f"VALUES ({vals});\n")
        for table, col in SERIALS.items():
            f.write(f"SELECT setval(pg_get_serial_sequence("
                    f"'{table}', '{col}'), (SELECT MAX({col}) "
                    f"FROM {table}));\n")


def load_db(rows):
    from db import get_connection
    conn = get_connection()
    try:
        with conn, conn.cursor() as cur:
            for table, data in rows.items():
                marks = ", ".join(["%s"] * len(COLUMNS[table].split(",")))
                cur.executemany(
                    f"INSERT INTO {table} ({COLUMNS[table]}) "
                    f"VALUES ({marks})", data)
            for table, col in SERIALS.items():
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), "
                    f"(SELECT MAX({col}) FROM {table}))", (table, col))
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--scale", type=int, default=1)
    parser.add_argument("--sql-out", help="write INSERT statements to file")
    args = parser.parse_args()
    rows = generate(args.scale)
    if args.sql_out:
        write_sql(rows, args.sql_out)
    else:
        load_db(rows)
    for table, data in rows.items():
        print(f"{table:<18}{len(data):>8}")


if __name__ == "__main__":
    main()
