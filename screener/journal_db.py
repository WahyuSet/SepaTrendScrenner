"""
Trading Journal & Watchlist Database Manager (screener/journal_db.py)
--------------------------------------------------------------------
SQLite-backed persistence for Personal Watchlist, Trade Journaling,
Portfolio Performance Analytics, and Money Management settings.
"""
from __future__ import annotations

import os
import sqlite3
import json
import csv
import io
import math
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "trading_journal.db")


def get_db_connection() -> sqlite3.Connection:
    """Create a thread-safe database connection with Row factory."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Initialize database tables and default configuration."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Watchlist Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                sector TEXT DEFAULT 'General',
                notes TEXT DEFAULT '',
                source_screener TEXT DEFAULT 'Manual',
                pinned_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Trade Journal Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS journal_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                name TEXT NOT NULL,
                sector TEXT DEFAULT 'General',
                status TEXT NOT NULL CHECK(status IN ('OPEN', 'CLOSED_WIN', 'CLOSED_LOSS', 'CLOSED_BEP')),
                setup_type TEXT DEFAULT 'Breakout',
                buy_date TEXT NOT NULL,
                buy_price REAL NOT NULL,
                lots INTEGER NOT NULL,
                capital_allocated REAL NOT NULL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                exit_date TEXT,
                exit_price REAL,
                exit_reason TEXT,
                realized_pnl REAL DEFAULT 0.0,
                realized_pnl_pct REAL DEFAULT 0.0,
                net_pnl REAL DEFAULT 0.0,
                broker_fee_total REAL DEFAULT 0.0,
                broker_fee_enabled INTEGER DEFAULT 1,
                notes TEXT DEFAULT '',
                chart_url TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. User Settings Table (Money Management & Fees)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        # Insert default settings if not exists
        default_settings = {
            "portfolio_capital": "100000000",   # Rp 100 Juta default
            "risk_per_trade_pct": "1.0",         # 1.0% default risk
            "max_position_cap_pct": "20.0",      # Max 20% allocation per stock
            "broker_fee_buy_pct": "0.15",        # 0.15% IDX Buy fee
            "broker_fee_sell_pct": "0.25",       # 0.25% IDX Sell fee
            "broker_fee_enabled": "1"            # Enabled by default
        }

        for k, v in default_settings.items():
            cursor.execute("INSERT OR IGNORE INTO user_settings (key, value) VALUES (?, ?)", (k, v))

        conn.commit()


# =========================================================================
# 1. WATCHLIST OPERATIONS
# =========================================================================

def get_all_watchlist() -> List[Dict[str, Any]]:
    """Get all pinned watchlist stocks sorted by pinned_at DESC."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlist ORDER BY pinned_at DESC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_watchlist_tickers() -> set[str]:
    """Get set of pinned ticker symbols."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM watchlist")
        rows = cursor.fetchall()
        return {row["ticker"] for row in rows}


def add_to_watchlist(ticker: str, name: str = "", sector: str = "General",
                     source_screener: str = "Manual", notes: str = "") -> Dict[str, Any]:
    """Add or update a stock in personal watchlist."""
    init_db()
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    if not clean_ticker:
        raise ValueError("Ticker cannot be empty")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO watchlist (ticker, name, sector, source_screener, notes, pinned_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ticker) DO UPDATE SET
                name = excluded.name,
                sector = excluded.sector,
                source_screener = excluded.source_screener,
                notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE watchlist.notes END,
                pinned_at = CURRENT_TIMESTAMP
        """, (clean_ticker, name or clean_ticker, sector or "General", source_screener or "Manual", notes))
        conn.commit()

        cursor.execute("SELECT * FROM watchlist WHERE ticker = ?", (clean_ticker,))
        row = cursor.fetchone()
        return dict(row) if row else {}


def remove_from_watchlist(ticker: str) -> bool:
    """Remove a stock from personal watchlist."""
    init_db()
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE ticker = ?", (clean_ticker,))
        conn.commit()
        return cursor.rowcount > 0


# =========================================================================
# 2. MONEY MANAGEMENT & BROKER FEE CALCULATIONS
# =========================================================================

def calculate_position_sizing(portfolio_capital: float, risk_pct: float,
                              entry_price: float, stop_loss: float,
                              target_1: Optional[float] = None, target_2: Optional[float] = None,
                              max_cap_pct: float = 20.0,
                              buy_fee_pct: float = 0.15, sell_fee_pct: float = 0.25,
                              fee_enabled: bool = True) -> Dict[str, Any]:
    """
    Calculate position size in IDX lots (100 shares/lot) with Minervini Risk %
    and Maximum Position Allocation Cap.
    """
    if entry_price <= 0 or stop_loss <= 0:
        raise ValueError("Harga Entry dan Stop Loss harus lebih besar dari 0")

    if stop_loss >= entry_price:
        raise ValueError("Harga Stop Loss harus lebih rendah dari Harga Entry untuk posisi Long")

    # 1. Toleransi Risiko Maksimal (Max Risk in IDR)
    max_risk_idr = portfolio_capital * (risk_pct / 100.0)

    # 2. Risiko per Lembar Saham (Risk Per Share)
    risk_per_share = entry_price - stop_loss
    risk_share_pct = (risk_per_share / entry_price) * 100.0

    # 3. Lot berdasarkan Risiko Murni: shares = max_risk / risk_per_share
    ideal_shares = max_risk_idr / risk_per_share
    ideal_lots = math.floor(ideal_shares / 100.0)

    # 4. Batas Maksimal Alokasi Modal (Max Position Cap e.g. 20-25%)
    max_capital_allowed = portfolio_capital * (max_cap_pct / 100.0)
    cap_lots = math.floor(max_capital_allowed / (entry_price * 100.0))

    # Recommended lots is minimum between risk-based lots and cap-based lots
    is_capped = ideal_lots > cap_lots
    recommended_lots = max(1, min(ideal_lots, cap_lots)) if ideal_lots > 0 else 0

    # 5. Modal Pembelian Terpakai
    shares_count = recommended_lots * 100
    capital_allocated = shares_count * entry_price
    portfolio_allocation_pct = (capital_allocated / portfolio_capital) * 100.0 if portfolio_capital > 0 else 0.0

    # 6. Biaya Broker
    buy_fee = capital_allocated * (buy_fee_pct / 100.0) if fee_enabled else 0.0
    sl_exit_val = shares_count * stop_loss
    sl_sell_fee = sl_exit_val * (sell_fee_pct / 100.0) if fee_enabled else 0.0

    # 7. Risiko Realistis (Loss saat terkena SL)
    gross_loss = shares_count * risk_per_share
    net_loss = gross_loss + buy_fee + sl_sell_fee if fee_enabled else gross_loss

    # 8. Target 1 & Target 2
    t1_data = None
    if target_1 and target_1 > entry_price:
        t1_gain_share = target_1 - entry_price
        t1_gain_pct = (t1_gain_share / entry_price) * 100.0
        t1_gross_gain = shares_count * t1_gain_share
        t1_sell_val = shares_count * target_1
        t1_sell_fee = t1_sell_val * (sell_fee_pct / 100.0) if fee_enabled else 0.0
        t1_net_gain = t1_gross_gain - (buy_fee + t1_sell_fee) if fee_enabled else t1_gross_gain
        t1_rr = round(t1_gain_share / risk_per_share, 2)
        t1_data = {
            "price": target_1,
            "gain_pct": round(t1_gain_pct, 2),
            "gross_gain": round(t1_gross_gain, 0),
            "net_gain": round(t1_net_gain, 0),
            "risk_reward": t1_rr
        }

    t2_data = None
    if target_2 and target_2 > entry_price:
        t2_gain_share = target_2 - entry_price
        t2_gain_pct = (t2_gain_share / entry_price) * 100.0
        t2_gross_gain = shares_count * t2_gain_share
        t2_sell_val = shares_count * target_2
        t2_sell_fee = t2_sell_val * (sell_fee_pct / 100.0) if fee_enabled else 0.0
        t2_net_gain = t2_gross_gain - (buy_fee + t2_sell_fee) if fee_enabled else t2_gross_gain
        t2_rr = round(t2_gain_share / risk_per_share, 2)
        t2_data = {
            "price": target_2,
            "gain_pct": round(t2_gain_pct, 2),
            "gross_gain": round(t2_gross_gain, 0),
            "net_gain": round(t2_net_gain, 0),
            "risk_reward": t2_rr
        }

    return {
        "portfolio_capital": portfolio_capital,
        "risk_pct": risk_pct,
        "max_risk_idr": round(max_risk_idr, 0),
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "risk_share_pct": round(risk_share_pct, 2),
        "recommended_lots": recommended_lots,
        "recommended_shares": shares_count,
        "capital_allocated": round(capital_allocated, 0),
        "portfolio_allocation_pct": round(portfolio_allocation_pct, 2),
        "is_capped": is_capped,
        "max_cap_pct": max_cap_pct,
        "buy_fee": round(buy_fee, 0),
        "sl_sell_fee": round(sl_sell_fee, 0),
        "gross_loss": round(gross_loss, 0),
        "net_loss": round(net_loss, 0),
        "target_1": t1_data,
        "target_2": t2_data,
        "fee_enabled": fee_enabled
    }


# =========================================================================
# 3. TRADE JOURNAL OPERATIONS
# =========================================================================

def get_all_trades(status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get all trades with optional status filter ('OPEN', 'CLOSED_WIN', etc.)."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if status_filter and status_filter.upper() != "ALL":
            cursor.execute("""
                SELECT * FROM journal_trades
                WHERE status = ?
                ORDER BY buy_date DESC, id DESC
            """, (status_filter.upper(),))
        else:
            cursor.execute("""
                SELECT * FROM journal_trades
                ORDER BY buy_date DESC, id DESC
            """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_trade_by_id(trade_id: int) -> Optional[Dict[str, Any]]:
    """Get a single trade by ID."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal_trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_trade(ticker: str, name: str, sector: str,
              buy_date: str, buy_price: float, lots: int,
              stop_loss: Optional[float] = None,
              target_1: Optional[float] = None,
              target_2: Optional[float] = None,
              setup_type: str = "Breakout",
              notes: str = "", chart_url: str = "",
              broker_fee_enabled: bool = True) -> Dict[str, Any]:
    """Record a new open trade."""
    init_db()
    clean_ticker = ticker.replace(".JK", "").strip().upper()
    if lots <= 0 or buy_price <= 0:
        raise ValueError("Harga Beli dan Lot harus lebih besar dari 0")

    shares = lots * 100
    capital_allocated = round(shares * buy_price, 2)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO journal_trades (
                ticker, name, sector, status, setup_type,
                buy_date, buy_price, lots, capital_allocated,
                stop_loss, target_1, target_2,
                broker_fee_enabled, notes, chart_url
            ) VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clean_ticker, name or clean_ticker, sector or "General", setup_type or "Breakout",
            buy_date or datetime.now().strftime("%Y-%m-%d"),
            buy_price, lots, capital_allocated,
            stop_loss, target_1, target_2,
            1 if broker_fee_enabled else 0,
            notes, chart_url
        ))
        conn.commit()
        new_id = cursor.lastrowid
        return get_trade_by_id(new_id) or {}


def close_trade(trade_id: int, exit_date: str, exit_price: float,
                exit_reason: str = "MANUAL", notes: Optional[str] = None) -> Dict[str, Any]:
    """Close an open trade and calculate realized P&L."""
    init_db()
    trade = get_trade_by_id(trade_id)
    if not trade:
        raise ValueError(f"Trade #{trade_id} tidak ditemukan")

    buy_price = float(trade["buy_price"])
    lots = int(trade["lots"])
    shares = lots * 100
    capital_allocated = float(trade["capital_allocated"])
    fee_enabled = bool(trade["broker_fee_enabled"])

    # Load settings for fee %
    settings = get_settings()
    buy_fee_pct = float(settings.get("broker_fee_buy_pct", 0.15))
    sell_fee_pct = float(settings.get("broker_fee_sell_pct", 0.25))

    # Calculations
    exit_value = shares * exit_price
    gross_pnl = exit_value - capital_allocated
    gross_pnl_pct = ((exit_price - buy_price) / buy_price) * 100.0

    buy_fee = capital_allocated * (buy_fee_pct / 100.0) if fee_enabled else 0.0
    sell_fee = exit_value * (sell_fee_pct / 100.0) if fee_enabled else 0.0
    broker_fee_total = buy_fee + sell_fee

    net_pnl = gross_pnl - broker_fee_total if fee_enabled else gross_pnl

    # Status classification
    if gross_pnl > 0 and gross_pnl_pct >= 0.5:
        status = "CLOSED_WIN"
    elif gross_pnl < 0 and gross_pnl_pct <= -0.5:
        status = "CLOSED_LOSS"
    else:
        status = "CLOSED_BEP"

    merged_notes = trade["notes"]
    if notes:
        merged_notes = f"{merged_notes}\n[Tutup Posisi {exit_date}]: {notes}".strip()

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE journal_trades SET
                status = ?,
                exit_date = ?,
                exit_price = ?,
                exit_reason = ?,
                realized_pnl = ?,
                realized_pnl_pct = ?,
                net_pnl = ?,
                broker_fee_total = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            status, exit_date, exit_price, exit_reason,
            round(gross_pnl, 2), round(gross_pnl_pct, 2),
            round(net_pnl, 2), round(broker_fee_total, 2),
            merged_notes, trade_id
        ))
        conn.commit()

    return get_trade_by_id(trade_id) or {}


def delete_trade(trade_id: int) -> bool:
    """Delete a trade from the journal."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM journal_trades WHERE id = ?", (trade_id,))
        conn.commit()
        return cursor.rowcount > 0


# =========================================================================
# 4. PORTFOLIO & JOURNAL ANALYTICS
# =========================================================================

def get_journal_stats() -> Dict[str, Any]:
    """Calculate key portfolio metrics: Win Rate, Total Realized P&L, Open Capital, etc."""
    init_db()
    trades = get_all_trades()

    open_trades = [t for t in trades if t["status"] == "OPEN"]
    closed_trades = [t for t in trades if t["status"] != "OPEN"]

    open_capital = sum(float(t["capital_allocated"]) for t in open_trades)

    wins = [t for t in closed_trades if t["status"] == "CLOSED_WIN"]
    losses = [t for t in closed_trades if t["status"] == "CLOSED_LOSS"]
    beps = [t for t in closed_trades if t["status"] == "CLOSED_BEP"]

    total_closed = len(closed_trades)
    win_rate = (len(wins) / total_closed * 100.0) if total_closed > 0 else 0.0

    total_realized_gross = sum(float(t["realized_pnl"]) for t in closed_trades)
    total_realized_net = sum(float(t["net_pnl"]) for t in closed_trades)
    total_fees_paid = sum(float(t["broker_fee_total"]) for t in closed_trades)

    gross_profit = sum(float(t["realized_pnl"]) for t in wins)
    gross_loss = abs(sum(float(t["realized_pnl"]) for t in losses))

    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

    avg_win_idr = (gross_profit / len(wins)) if wins else 0.0
    avg_loss_idr = (gross_loss / len(losses)) if losses else 0.0
    avg_win_pct = (sum(float(t["realized_pnl_pct"]) for t in wins) / len(wins)) if wins else 0.0
    avg_loss_pct = (abs(sum(float(t["realized_pnl_pct"]) for t in losses)) / len(losses)) if losses else 0.0

    # Watchlist count
    watchlist_items = get_all_watchlist()

    return {
        "total_watchlist_count": len(watchlist_items),
        "open_trades_count": len(open_trades),
        "open_capital_allocated": round(open_capital, 0),
        "total_closed_trades": total_closed,
        "wins_count": len(wins),
        "losses_count": len(losses),
        "bep_count": len(beps),
        "win_rate_pct": round(win_rate, 1),
        "total_realized_gross": round(total_realized_gross, 0),
        "total_realized_net": round(total_realized_net, 0),
        "total_fees_paid": round(total_fees_paid, 0),
        "profit_factor": profit_factor,
        "avg_win_idr": round(avg_win_idr, 0),
        "avg_loss_idr": round(avg_loss_idr, 0),
        "avg_win_pct": round(avg_win_pct, 1),
        "avg_loss_pct": round(avg_loss_pct, 1)
    }


# =========================================================================
# 5. USER SETTINGS (MONEY MANAGEMENT CONFIG)
# =========================================================================

def get_settings() -> Dict[str, Any]:
    """Retrieve user settings dictionary."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_settings")
        rows = cursor.fetchall()
        settings = {row["key"]: row["value"] for row in rows}

        return {
            "portfolio_capital": float(settings.get("portfolio_capital", 100000000)),
            "risk_per_trade_pct": float(settings.get("risk_per_trade_pct", 1.0)),
            "max_position_cap_pct": float(settings.get("max_position_cap_pct", 20.0)),
            "broker_fee_buy_pct": float(settings.get("broker_fee_buy_pct", 0.15)),
            "broker_fee_sell_pct": float(settings.get("broker_fee_sell_pct", 0.25)),
            "broker_fee_enabled": settings.get("broker_fee_enabled", "1") in ["1", "true", "True"]
        }


def save_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Save user settings."""
    init_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for k, v in settings.items():
            cursor.execute("""
                INSERT INTO user_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (str(k), str(v)))
        conn.commit()
    return get_settings()


# =========================================================================
# 6. EXPORT & BACKUP/RESTORE
# =========================================================================

def export_trades_to_csv() -> str:
    """Export all trades to CSV format."""
    trades = get_all_trades()
    output = io.StringIO()
    fieldnames = [
        "id", "ticker", "name", "sector", "status", "setup_type",
        "buy_date", "buy_price", "lots", "capital_allocated",
        "stop_loss", "target_1", "target_2",
        "exit_date", "exit_price", "exit_reason",
        "realized_pnl", "realized_pnl_pct", "net_pnl", "broker_fee_total",
        "notes", "chart_url"
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for t in trades:
        row = {k: t.get(k, "") for k in fieldnames}
        writer.writerow(row)
    return output.getvalue()


def backup_to_json() -> Dict[str, Any]:
    """Create complete backup of watchlist, trades, and settings."""
    return {
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "settings": get_settings(),
        "watchlist": get_all_watchlist(),
        "trades": get_all_trades()
    }


def restore_from_json(backup_data: Dict[str, Any]) -> Dict[str, int]:
    """Restore watchlist, trades, and settings from JSON backup."""
    init_db()
    w_count = 0
    t_count = 0

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Restore settings
        if "settings" in backup_data and isinstance(backup_data["settings"], dict):
            for k, v in backup_data["settings"].items():
                cursor.execute("""
                    INSERT INTO user_settings (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """, (str(k), str(v)))

        # Restore watchlist
        if "watchlist" in backup_data and isinstance(backup_data["watchlist"], list):
            for w in backup_data["watchlist"]:
                ticker = w.get("ticker", "").strip().upper()
                if ticker:
                    cursor.execute("""
                        INSERT OR IGNORE INTO watchlist (ticker, name, sector, source_screener, notes)
                        VALUES (?, ?, ?, ?, ?)
                    """, (ticker, w.get("name", ticker), w.get("sector", "General"),
                          w.get("source_screener", "Manual"), w.get("notes", "")))
                    w_count += 1

        # Restore trades
        if "trades" in backup_data and isinstance(backup_data["trades"], list):
            for t in backup_data["trades"]:
                ticker = t.get("ticker", "").strip().upper()
                if ticker:
                    cursor.execute("""
                        INSERT INTO journal_trades (
                            ticker, name, sector, status, setup_type,
                            buy_date, buy_price, lots, capital_allocated,
                            stop_loss, target_1, target_2,
                            exit_date, exit_price, exit_reason,
                            realized_pnl, realized_pnl_pct, net_pnl,
                            broker_fee_total, broker_fee_enabled, notes, chart_url
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        ticker, t.get("name", ticker), t.get("sector", "General"),
                        t.get("status", "OPEN"), t.get("setup_type", "Breakout"),
                        t.get("buy_date", datetime.now().strftime("%Y-%m-%d")),
                        float(t.get("buy_price", 0)), int(t.get("lots", 1)),
                        float(t.get("capital_allocated", 0)),
                        t.get("stop_loss"), t.get("target_1"), t.get("target_2"),
                        t.get("exit_date"), t.get("exit_price"), t.get("exit_reason"),
                        float(t.get("realized_pnl", 0)), float(t.get("realized_pnl_pct", 0)),
                        float(t.get("net_pnl", 0)), float(t.get("broker_fee_total", 0)),
                        int(t.get("broker_fee_enabled", 1)),
                        t.get("notes", ""), t.get("chart_url", "")
                    ))
                    t_count += 1

        conn.commit()

    return {"restored_watchlist": w_count, "restored_trades": t_count}
