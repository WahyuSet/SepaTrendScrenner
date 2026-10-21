"""
Tests for screener/lpm_service.py, the LPM job state in IDXApiClient, and the three
/api/idx/lpm routes. HTTP and yfinance are faked, so no quota is used.

Run from the repo root:  python -m unittest tests.test_lpm_service
"""
import unittest
from unittest import mock

from screener.lpm import LPM_PARAMS
from screener.lpm_service import LPMService, LPMDataError, LPMQuotaError
from tests.test_broker_daily import BrokerDailyTestCase, weekdays_before

TODAY = "2026-10-21"


def make_bars(dates):
    return [{"date": d, "open": 1000.0, "high": 1010.0, "low": 990.0, "close": 1000.0, "volume": 1e6} for d in dates]


class LPMServiceTestCase(BrokerDailyTestCase):
    def setUp(self):
        super().setUp()
        no_delay = mock.patch.dict(LPM_PARAMS, {"request_delay_sec": 0})
        no_delay.start()
        self.addCleanup(no_delay.stop)
        self.dates = weekdays_before(TODAY, 80)
        self.bars = make_bars(self.dates + [TODAY])
        self.service = LPMService(self.client, price_loader=lambda ticker, period: list(self.bars))

    def run_backfill(self, ticker="BBCA", days=None):
        result = self.service.start_backfill(ticker, days)
        thread = self.service._threads.get(ticker)
        if thread:
            thread.join(timeout=10)
        return result


class TestGetLpm(LPMServiceTestCase):
    def test_no_history_fetches_nothing(self):
        out = self.service.get_lpm("BBCA")
        self.assertEqual(self.api.calls, [])
        cov = out["coverage"]
        self.assertFalse(cov["has_history"])
        self.assertFalse(cov["complete"])
        self.assertEqual(cov["requested_days"], 80)
        self.assertEqual(cov["missing_days"], 80)
        self.assertEqual(out["as_of"], self.dates[-1])
        self.assertEqual(out["trend"]["status"], "DATA_KURANG")
        self.assertTrue(all(s["gap"] for s in out["series"]))
        self.assertEqual(out["backfill"]["state"], "idle")

    def test_full_history_after_backfill(self):
        self.run_backfill()
        self.api.calls.clear()
        out = self.service.get_lpm("BBCA")
        self.assertEqual(self.api.calls, [])
        self.assertTrue(out["coverage"]["complete"])
        self.assertTrue(out["coverage"]["has_history"])
        self.assertEqual(out["coverage"]["available_days"], 80)
        self.assertEqual(out["trend"]["status"], "RISING")
        self.assertEqual(out["series"][-1]["open"], 1000.0)
        self.assertEqual(out["ticker"], "BBCA")

    def test_sync_fetches_newest_days_up_to_limit(self):
        self.client.backfill_broker_daily("BBCA", self.dates[:70], delay=0)
        self.api.calls.clear()
        out = self.service.get_lpm("BBCA")
        limit = LPM_PARAMS["max_sync_fetch_days"]
        self.assertEqual(self.api.calls, list(reversed(self.dates))[:limit])
        self.assertEqual(out["coverage"]["synced_days"], limit)
        self.assertEqual(out["coverage"]["missing_days"], 10 - limit)
        self.assertFalse(out["coverage"]["complete"])

    def test_sync_skipped_while_backfill_running(self):
        self.client.backfill_broker_daily("BBCA", self.dates[:70], delay=0)
        self.client.claim_lpm_job("BBCA", 10)
        self.api.calls.clear()
        out = self.service.get_lpm("BBCA")
        self.assertEqual(self.api.calls, [])
        self.assertEqual(out["coverage"]["synced_days"], 0)
        self.assertEqual(out["backfill"]["state"], "running")

    def test_zero_volume_day_is_not_requested(self):
        self.bars[40]["volume"] = 0
        self.run_backfill()
        self.assertNotIn(self.dates[40], self.api.calls)
        out = self.service.get_lpm("BBCA")
        self.assertTrue(out["series"][40]["gap"])
        self.assertTrue(out["coverage"]["complete"])

    def test_today_included_after_final_hour(self):
        self.set_now(2026, 10, 21, 17, 30)
        out = self.service.get_lpm("BBCA")
        self.assertEqual(out["as_of"], TODAY)
        self.assertEqual(out["coverage"]["requested_days"], 80)

    def test_no_price_data(self):
        service = LPMService(self.client, price_loader=lambda ticker, period: [])
        with self.assertRaises(LPMDataError):
            service.get_lpm("BBCA")


class TestStartBackfill(LPMServiceTestCase):
    def test_started_then_done(self):
        result = self.run_backfill()
        self.assertEqual(result["status"], "started")
        self.assertEqual(result["missing_days"], 80)
        self.assertEqual(result["estimated_requests"], 80)
        job = self.client.get_lpm_job("BBCA")
        self.assertEqual(job["state"], "done")
        self.assertEqual((job["done"], job["total"], job["requested"]), (80, 80, 80))
        self.assertEqual(self.run_backfill()["status"], "complete")

    def test_second_start_while_running(self):
        self.client.claim_lpm_job("BBCA", 80)
        self.assertEqual(self.service.start_backfill("BBCA")["status"], "running")
        self.assertEqual(self.api.calls, [])

    def test_refused_when_only_reserve_left(self):
        self.set_quota_used(self.client.DAILY_LIMIT - LPM_PARAMS["quota_reserve"])
        with self.assertRaises(LPMQuotaError):
            self.service.start_backfill("BBCA")
        self.assertEqual(self.client.get_lpm_job("BBCA")["state"], "idle")

    def test_stops_at_reserve(self):
        self.set_quota_used(self.client.DAILY_LIMIT - LPM_PARAMS["quota_reserve"] - 10)
        result = self.run_backfill()
        self.assertEqual(result["estimated_requests"], 10)
        job = self.client.get_lpm_job("BBCA")
        self.assertEqual(job["state"], "stopped_quota")
        self.assertEqual(job["requested"], 10)

    def test_days_are_clamped_to_trend_window(self):
        result = self.run_backfill(days=5)
        self.assertEqual(result["missing_days"], LPM_PARAMS["slope_slow"])

    def test_worker_error_is_recorded(self):
        with mock.patch.object(self.client, "backfill_broker_daily", side_effect=ValueError("rusak")):
            self.run_backfill()
        job = self.client.get_lpm_job("BBCA")
        self.assertEqual(job["state"], "error")
        self.assertEqual(job["last_error"], "rusak")


class TestLpmJobs(BrokerDailyTestCase):
    def test_idle_by_default(self):
        self.assertEqual(self.client.get_lpm_job("BBCA")["state"], "idle")

    def test_claim_is_exclusive_until_finished(self):
        self.assertTrue(self.client.claim_lpm_job("BBCA", 10))
        self.assertFalse(self.client.claim_lpm_job("BBCA", 10))
        self.client.update_lpm_job("BBCA", state="done", done=10)
        self.assertTrue(self.client.claim_lpm_job("BBCA", 5))
        self.assertEqual(self.client.get_lpm_job("BBCA")["total"], 5)

    def test_dead_job_is_reported_and_replaceable(self):
        self.client.claim_lpm_job("BBCA", 10)
        self.set_now(2026, 10, 21, 15, 5)
        job = self.client.get_lpm_job("BBCA")
        self.assertEqual(job["state"], "error")
        self.assertIn("terhenti", job["last_error"])
        self.assertTrue(self.client.claim_lpm_job("BBCA", 10))


class TestLpmRoutes(LPMServiceTestCase):
    def setUp(self):
        super().setUp()
        import app as app_module
        self.app_module = app_module
        for name, value in (("idx_client", self.client), ("lpm_service", self.service)):
            patcher = mock.patch.object(app_module, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.http = app_module.app.test_client()
        with self.http.session_transaction() as sess:
            sess["is_admin"] = True

    def test_requires_login(self):
        anon = self.app_module.app.test_client()
        self.assertEqual(anon.get("/api/idx/lpm/BBCA").status_code, 401)
        self.assertEqual(anon.post("/api/idx/lpm/BBCA/backfill").status_code, 401)
        self.assertEqual(anon.get("/api/idx/lpm/BBCA/status").status_code, 401)

    def test_unknown_ticker(self):
        for resp in (self.http.get("/api/idx/lpm/ZZZZ"), self.http.post("/api/idx/lpm/ZZZZ/backfill"),
                     self.http.get("/api/idx/lpm/ZZZZ/status")):
            self.assertEqual(resp.status_code, 404)
            self.assertIn("tidak terdaftar", resp.get_json()["message"])

    def test_get_lpm(self):
        resp = self.http.get("/api/idx/lpm/bbca.jk")
        body = resp.get_json()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["data"]["ticker"], "BBCA")
        self.assertIn("remaining", body["quota"])

    def test_get_lpm_without_prices(self):
        self.service.price_loader = lambda ticker, period: []
        resp = self.http.get("/api/idx/lpm/BBCA")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("tidak tersedia", resp.get_json()["message"])

    def test_backfill_then_status(self):
        resp = self.http.post("/api/idx/lpm/BBCA/backfill", json={"days": 30})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "started")
        self.assertEqual(resp.get_json()["missing_days"], 30)
        self.service._threads["BBCA"].join(timeout=10)
        status = self.http.get("/api/idx/lpm/BBCA/status").get_json()
        self.assertEqual(status["state"], "done")
        self.assertEqual(status["done"], 30)
        self.assertIn("remaining", status["quota"])

    def test_backfill_bad_days(self):
        resp = self.http.post("/api/idx/lpm/BBCA/backfill", json={"days": "banyak"})
        self.assertEqual(resp.status_code, 400)

    def test_backfill_quota_reserve(self):
        self.set_quota_used(self.client.DAILY_LIMIT - LPM_PARAMS["quota_reserve"])
        resp = self.http.post("/api/idx/lpm/BBCA/backfill")
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.get_json()["code"], "QUOTA_RESERVE")
        self.assertIn("cadangan", resp.get_json()["message"])


if __name__ == "__main__":
    unittest.main()
