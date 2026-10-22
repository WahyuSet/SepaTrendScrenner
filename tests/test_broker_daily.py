"""
Tests for the broker_daily storage and backfill in screener/idx_api_client.py.
HTTP is faked, so no IDX Edge PRO quota is used.

Run from the repo root:  python -m unittest tests.test_broker_daily
"""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

from screener.idx_api_client import IDXApiClient, WIB
from screener.lpm import LPM_PARAMS, build_lpm


def weekdays_before(end, n):
    """n weekday dates (YYYY-MM-DD) ending the day before `end`, oldest first."""
    day = datetime.strptime(end, "%Y-%m-%d")
    out = []
    while len(out) < n:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            out.append(day.strftime("%Y-%m-%d"))
    return list(reversed(out))


def broker_rows(i=0):
    big = 60e6 * (1 + 0.1 * (i % 3))
    rows = [{"broker_code": "BK", "broker_name": "BIG", "bval": big, "sval": 0, "bvol": 1, "svol": 0,
             "bfrq": round(big / 6e6), "sfrq": 0, "nval": big, "nvol": 1, "xx": "dibuang"}]
    for r in range(8):
        sv = 100e6 + big / 8
        rows.append({"broker_code": f"R{r}", "broker_name": "RITEL", "bval": 100e6, "sval": sv, "bvol": 1, "svol": 1,
                     "bfrq": 100, "sfrq": round(sv / 1e6), "nval": 100e6 - sv, "nvol": 0})
    return rows


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeApi:
    """Answers /api/broker-summary like the real API; `overrides` maps a date to a custom response."""

    def __init__(self):
        self.calls = []
        self.overrides = {}

    def __call__(self, url, headers=None, params=None, timeout=None):
        date = params["start_date"]
        self.calls.append(date)
        if date in self.overrides:
            return self.overrides[date]
        return FakeResponse(200, {
            "stock_code": "BBCA",
            "broker_start_date": params["start_date"],
            "broker_end_date": params["end_date"],
            "brokers": broker_rows(len(self.calls)),
        })


class BrokerDailyTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.client = IDXApiClient(db_path=os.path.join(self.tmp, "test.db"))
        self.set_now(2026, 10, 21, 15, 0)
        self.api = FakeApi()
        patcher = mock.patch("screener.idx_api_client.requests.get", self.api)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def set_now(self, *parts):
        self.client._now_wib = lambda: datetime(*parts, tzinfo=WIB)

    def set_quota_used(self, used):
        today = datetime.now().strftime("%Y-%m-%d")
        with self.client._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO quota_usage (date, request_count) VALUES (?, ?)", (today, used))
            conn.commit()


class TestGetBrokerDaily(BrokerDailyTestCase):
    def test_ok_day_is_stored_and_not_fetched_twice(self):
        first = self.client.get_broker_daily("BBCA", "2026-10-20")
        second = self.client.get_broker_daily("BBCA.JK", "2026-10-20")
        self.assertEqual(first["status"], "ok")
        self.assertTrue(first["fetched"])
        self.assertFalse(second["fetched"])
        self.assertEqual(self.api.calls, ["2026-10-20"])
        self.assertEqual(self.client.get_quota_status()["used"], 1)
        self.assertNotIn("xx", second["brokers"][0])
        self.assertEqual(second["brokers"][0]["broker_code"], "BK")

    def test_empty_day_is_not_refetched(self):
        self.api.overrides["2026-10-20"] = FakeResponse(200, {
            "broker_start_date": "2026-10-20", "broker_end_date": "2026-10-20", "brokers": []})
        self.assertEqual(self.client.get_broker_daily("BBCA", "2026-10-20")["status"], "empty")
        self.assertEqual(self.client.get_broker_daily("BBCA", "2026-10-20")["status"], "empty")
        self.assertEqual(len(self.api.calls), 1)

    def test_error_is_retried_up_to_the_limit(self):
        self.api.overrides["2026-10-20"] = FakeResponse(500, None)
        for _ in range(LPM_PARAMS["max_fetch_attempts"] + 2):
            result = self.client.get_broker_daily("BBCA", "2026-10-20")
            self.assertEqual(result["status"], "error")
        self.assertEqual(len(self.api.calls), LPM_PARAMS["max_fetch_attempts"])
        self.assertEqual(self.client.missing_broker_days("BBCA", ["2026-10-20"]), [])
        self.assertEqual(self.client.load_broker_daily("BBCA")["2026-10-20"]["note"], "HTTP 500")

    def test_error_then_success_replaces_row(self):
        self.api.overrides["2026-10-20"] = FakeResponse(500, None)
        self.client.get_broker_daily("BBCA", "2026-10-20")
        del self.api.overrides["2026-10-20"]
        self.assertEqual(self.client.get_broker_daily("BBCA", "2026-10-20")["status"], "ok")

    def test_response_for_another_day_is_rejected(self):
        self.api.overrides["2026-10-19"] = FakeResponse(200, {
            "broker_start_date": "2026-10-20", "broker_end_date": "2026-10-20", "brokers": broker_rows()})
        result = self.client.get_broker_daily("BBCA", "2026-10-19")
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["brokers"])
        self.assertIn("tidak sama", self.client.load_broker_daily("BBCA")["2026-10-19"]["note"])

    def test_today_is_ignored_until_final_hour(self):
        self.assertIsNone(self.client.get_broker_daily("BBCA", "2026-10-21"))
        self.assertEqual(self.client.missing_broker_days("BBCA", ["2026-10-20", "2026-10-21"]), ["2026-10-20"])
        self.assertEqual(self.api.calls, [])
        self.set_now(2026, 10, 21, 17, 30)
        self.assertEqual(self.client.get_broker_daily("BBCA", "2026-10-21")["status"], "ok")

    def test_future_date_is_ignored(self):
        self.assertIsNone(self.client.get_broker_daily("BBCA", "2026-10-22"))
        self.assertEqual(self.api.calls, [])

    def test_invalid_ticker(self):
        self.assertIsNone(self.client.get_broker_daily("BB", "2026-10-20"))
        self.assertEqual(self.client.load_broker_daily("BB"), {})

    def test_make_request_behaviour_unchanged(self):
        self.api.overrides["2026-10-20"] = FakeResponse(500, None)
        self.assertIsNone(self.client._make_request("/api/broker-summary/BBCA", {"start_date": "2026-10-20", "end_date": "2026-10-20"}))
        ok = self.client._make_request("/api/broker-summary/BBCA", {"start_date": "2026-10-19", "end_date": "2026-10-19"})
        self.assertIn("brokers", ok)


class TestBandarTabReuse(BrokerDailyTestCase):
    def latest_response(self, date):
        return FakeResponse(200, {"stock_code": "BBCA", "broker_start_date": date, "broker_end_date": date,
                                  "brokers": broker_rows()})

    def test_bandar_tab_response_is_stored_for_lpm(self):
        with mock.patch("screener.idx_api_client.requests.get", return_value=self.latest_response("2026-10-20")):
            self.assertIsNotNone(self.client.get_broker_summary("BBCA", force_refresh=True))
        row = self.client.load_broker_daily("BBCA")["2026-10-20"]
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["note"], "dari tab Bandarmologi")
        self.assertEqual(self.client.missing_broker_days("BBCA", ["2026-10-20"]), [])

    def test_unfinished_day_is_not_stored(self):
        with mock.patch("screener.idx_api_client.requests.get", return_value=self.latest_response("2026-10-21")):
            self.client.get_broker_summary("BBCA", force_refresh=True)
        self.assertEqual(self.client.load_broker_daily("BBCA"), {})

    def test_foreign_flow_is_not_stored(self):
        with mock.patch("screener.idx_api_client.requests.get", return_value=self.latest_response("2026-10-20")):
            self.client.get_broker_summary("BBCA", flow="F", force_refresh=True)
        self.assertEqual(self.client.load_broker_daily("BBCA"), {})


class TestBackfill(BrokerDailyTestCase):
    def test_newest_first_with_request_cap(self):
        dates = weekdays_before("2026-10-21", 10)
        summary = self.client.backfill_broker_daily("BBCA", dates, max_requests=4, delay=0)
        self.assertEqual(self.api.calls, list(reversed(dates))[:4])
        self.assertEqual(summary["requested"], 4)
        self.assertEqual(summary["ok"], 4)
        self.assertEqual(summary["missing"], 10)
        self.assertEqual(summary["stopped_reason"], "max_requests")

    def test_stops_before_touching_quota_reserve(self):
        reserve = LPM_PARAMS["quota_reserve"]
        self.set_quota_used(self.client.DAILY_LIMIT - reserve - 3)
        summary = self.client.backfill_broker_daily("BBCA", weekdays_before("2026-10-21", 10), delay=0)
        self.assertEqual(summary["requested"], 3)
        self.assertEqual(summary["stopped_reason"], "quota_reserve")
        self.assertEqual(self.client.get_quota_status()["remaining"], reserve)

    def test_only_missing_days_are_fetched(self):
        dates = weekdays_before("2026-10-21", 6)
        self.client.get_broker_daily("BBCA", dates[-1])
        self.client.get_broker_daily("BBCA", dates[0])
        self.api.calls.clear()
        progress = []
        summary = self.client.backfill_broker_daily(
            "BBCA", dates, delay=0, on_progress=lambda done, total, date, res: progress.append((done, total)))
        self.assertEqual(sorted(self.api.calls), dates[1:-1])
        self.assertEqual(summary["stopped_reason"], "done")
        self.assertEqual(progress[-1], (4, 4))

    def test_stored_history_feeds_build_lpm(self):
        dates = weekdays_before("2026-10-21", 25)
        self.client.backfill_broker_daily("BBCA", dates, delay=0)
        stored = self.client.load_broker_daily("BBCA", dates)
        days = [{"date": d, "close": 1000.0, "brokers": stored[d]["brokers"]} for d in dates]
        out = build_lpm(days)
        self.assertEqual(out["coverage"], {"available_days": 25, "gap_days": 0})
        self.assertEqual(out["trend"]["status"], "RISING")
        self.assertEqual(out["top_smart_brokers"][0]["broker_code"], "BK")


if __name__ == "__main__":
    unittest.main()
