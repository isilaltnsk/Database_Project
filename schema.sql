-- =====================================================================
-- CommonCents - Personal Finance & Shared Budget Tracker
-- BBF 302E Database Systems, Fall 2026
-- Relational schema for PostgreSQL (Milestone 2, Sections 5-6)
--
-- Usage (psql):
--   createdb commoncents
--   psql -d commoncents -f schema.sql
--
-- Re-running this file drops and recreates all tables (development only).
-- =====================================================================

-- Deleting users: users are never physically deleted. Closing an account sets
-- Users.is_active = FALSE (and BudgetMembers.is_active = FALSE); every foreign
-- key that references Users uses ON DELETE RESTRICT to protect the history.

-- ---------- Clean start (reverse dependency order) ----------
DROP TABLE IF EXISTS RecurringPayments CASCADE;
DROP TABLE IF EXISTS FinancialGoals    CASCADE;
DROP TABLE IF EXISTS Contributions     CASCADE;
DROP TABLE IF EXISTS SpendingLimits    CASCADE;
DROP TABLE IF EXISTS BudgetMembers     CASCADE;
DROP TABLE IF EXISTS Transactions      CASCADE;
DROP TABLE IF EXISTS SharedBudgets     CASCADE;
DROP TABLE IF EXISTS Categories        CASCADE;
DROP TABLE IF EXISTS Accounts          CASCADE;
DROP TABLE IF EXISTS Users             CASCADE;

-- ---------- 1. Users (Işıl Altınışık) ----------
CREATE TABLE Users (
    user_id        SERIAL       PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL UNIQUE,
    email          VARCHAR(100) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,            -- salted hash, never the plain password
    role           VARCHAR(10)  NOT NULL DEFAULT 'User',
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,   -- soft deletion: closed accounts are kept
    created_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_users_role CHECK (role IN ('User', 'Admin'))
);

-- ---------- 2. Accounts (Ahmet Selim Şahintürk) ----------
CREATE TABLE Accounts (
    account_id  SERIAL        PRIMARY KEY,
    user_id     INT           NOT NULL REFERENCES Users(user_id) ON DELETE RESTRICT,
    name        VARCHAR(100)  NOT NULL,
    type        VARCHAR(12)   NOT NULL,
    balance     NUMERIC(14,2) NOT NULL DEFAULT 0,    -- opening balance; may be negative for credit cards
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_accounts_type CHECK (type IN ('cash', 'bank', 'credit_card', 'savings')),
    CONSTRAINT uq_accounts_user_name UNIQUE (user_id, name),
    CONSTRAINT uq_accounts_id_user   UNIQUE (account_id, user_id)   -- target of FinancialGoals composite FK
);

-- ---------- 3. Categories (Mehmet Arda Öncel) ----------
CREATE TABLE Categories (
    category_id  SERIAL      PRIMARY KEY,
    name         VARCHAR(50) NOT NULL,
    is_default   BOOLEAN     NOT NULL DEFAULT FALSE,
    user_id      INT         REFERENCES Users(user_id) ON DELETE RESTRICT,  -- NULL for default categories
    CONSTRAINT chk_categories_owner CHECK (
        (is_default AND user_id IS NULL) OR (NOT is_default AND user_id IS NOT NULL)
    ),
    CONSTRAINT uq_categories_user_name UNIQUE (user_id, name)
);
-- UNIQUE (user_id, name) does not cover NULL owners, so default names are made unique here:
CREATE UNIQUE INDEX uq_categories_default_name ON Categories (name) WHERE user_id IS NULL;

-- ---------- 5. SharedBudgets (Işıl Altınışık) ----------
CREATE TABLE SharedBudgets (
    budget_id    SERIAL        PRIMARY KEY,
    owner_id     INT           NOT NULL REFERENCES Users(user_id) ON DELETE RESTRICT,  -- creator of the budget
    name         VARCHAR(100)  NOT NULL,
    total_limit  NUMERIC(12,2) NOT NULL,
    start_date   DATE          NOT NULL,
    end_date     DATE          NOT NULL,
    CONSTRAINT chk_budgets_limit CHECK (total_limit > 0),
    CONSTRAINT chk_budgets_dates CHECK (end_date > start_date)
);

-- ---------- 4. Transactions (Mehmet Arda Öncel) ----------
CREATE TABLE Transactions (
    transaction_id  SERIAL        PRIMARY KEY,
    account_id      INT           NOT NULL REFERENCES Accounts(account_id)     ON DELETE CASCADE,
    category_id     INT           NOT NULL REFERENCES Categories(category_id)  ON DELETE NO ACTION,
    budget_id       INT           REFERENCES SharedBudgets(budget_id)          ON DELETE SET NULL,  -- NULL = personal
    amount          NUMERIC(12,2) NOT NULL,
    date            DATE          NOT NULL DEFAULT CURRENT_DATE,
    type            VARCHAR(7)    NOT NULL,
    description     VARCHAR(255),
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_transactions_amount CHECK (amount > 0),
    CONSTRAINT chk_transactions_type   CHECK (type IN ('income', 'expense')),
    CONSTRAINT chk_transactions_budget_expense CHECK (budget_id IS NULL OR type = 'expense')
);
CREATE INDEX idx_transactions_account_date  ON Transactions (account_id, date);
CREATE INDEX idx_transactions_budget_cat    ON Transactions (budget_id, category_id);

-- ---------- 6. BudgetMembers (Safa Oğuzhan Dişbudak) ----------
CREATE TABLE BudgetMembers (
    budget_id  INT         NOT NULL REFERENCES SharedBudgets(budget_id) ON DELETE CASCADE,
    user_id    INT         NOT NULL REFERENCES Users(user_id)           ON DELETE RESTRICT,
    role       VARCHAR(15) NOT NULL DEFAULT 'Regular',
    joined_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,        -- FALSE = left or was removed (history is kept)
    PRIMARY KEY (budget_id, user_id),
    CONSTRAINT chk_members_role CHECK (role IN ('Budget Manager', 'Regular'))
);

-- ---------- 7. SpendingLimits (Semih Tutuş) ----------
CREATE TABLE SpendingLimits (
    limit_id     SERIAL        PRIMARY KEY,
    budget_id    INT           NOT NULL REFERENCES SharedBudgets(budget_id) ON DELETE CASCADE,
    category_id  INT           NOT NULL REFERENCES Categories(category_id)  ON DELETE CASCADE,
    max_amount   NUMERIC(12,2) NOT NULL,
    CONSTRAINT chk_limits_amount CHECK (max_amount > 0),
    CONSTRAINT uq_limits_budget_category UNIQUE (budget_id, category_id)
);

-- ---------- 8. Contributions (Safa Oğuzhan Dişbudak) ----------
CREATE TABLE Contributions (
    contribution_id  SERIAL        PRIMARY KEY,
    budget_id        INT           NOT NULL REFERENCES SharedBudgets(budget_id) ON DELETE CASCADE,
    user_id          INT           NOT NULL REFERENCES Users(user_id)           ON DELETE RESTRICT,
    amount           NUMERIC(12,2) NOT NULL,
    date             DATE          NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT chk_contributions_amount CHECK (amount > 0)
);
CREATE INDEX idx_contributions_budget ON Contributions (budget_id);

-- ---------- 9. FinancialGoals (Ahmet Selim Şahintürk) ----------
CREATE TABLE FinancialGoals (
    goal_id         SERIAL        PRIMARY KEY,
    user_id         INT           NOT NULL REFERENCES Users(user_id)         ON DELETE RESTRICT,
    account_id      INT           NOT NULL UNIQUE REFERENCES Accounts(account_id) ON DELETE CASCADE,  -- 1:1 with Accounts
    name            VARCHAR(100)  NOT NULL,
    target_amount   NUMERIC(12,2) NOT NULL,
    current_amount  NUMERIC(12,2) NOT NULL DEFAULT 0,
    deadline        DATE          NOT NULL,
    CONSTRAINT chk_goals_target  CHECK (target_amount > 0),
    CONSTRAINT chk_goals_current CHECK (current_amount >= 0),
    -- the goal's owner must also be the owner of the tracking account
    CONSTRAINT fk_goals_account_owner FOREIGN KEY (account_id, user_id)
        REFERENCES Accounts (account_id, user_id) ON DELETE CASCADE
);

-- ---------- 10. RecurringPayments (Semih Tutuş) ----------
CREATE TABLE RecurringPayments (
    recurring_id  SERIAL        PRIMARY KEY,
    account_id    INT           NOT NULL REFERENCES Accounts(account_id)    ON DELETE CASCADE,
    category_id   INT           NOT NULL REFERENCES Categories(category_id) ON DELETE NO ACTION,
    name          VARCHAR(100)  NOT NULL,
    amount        NUMERIC(12,2) NOT NULL,
    frequency     VARCHAR(10)   NOT NULL,
    next_date     DATE          NOT NULL,
    CONSTRAINT chk_recurring_amount    CHECK (amount > 0),
    CONSTRAINT chk_recurring_frequency CHECK (frequency IN ('daily', 'weekly', 'monthly', 'yearly'))
);
CREATE INDEX idx_recurring_next_date ON RecurringPayments (next_date);
