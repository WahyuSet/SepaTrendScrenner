import urllib.request
import json
import re

BASE_URL = "http://127.0.0.1:5000"

def test_endpoints():
    print(">>> 1. Testing /api/idx/quota...")
    req = urllib.request.urlopen(f"{BASE_URL}/api/idx/quota")
    assert req.getcode() == 200, "Quota endpoint failed"
    data = json.loads(req.read().decode())
    print("Quota Response:", data["data"])
    assert data["status"] == "success"
    assert "used" in data["data"]
    assert "remaining" in data["data"]
    assert "limit" in data["data"]

    print("\n>>> 2. Testing /api/idx/broker-summary/BBCA...")
    req2 = urllib.request.urlopen(f"{BASE_URL}/api/idx/broker-summary/BBCA")
    assert req2.getcode() == 200, "Broker summary failed"
    data2 = json.loads(req2.read().decode())
    print("Broker Summary Status:", data2["data"]["status"], "| Top 3 Buyers:", len(data2["data"]["top_buyers"]))
    assert data2["status"] == "success"
    assert "top3_buy_ratio" in data2["data"]

    print("\n>>> 3. Testing /api/idx/broker-accumulation/BBCA...")
    req3 = urllib.request.urlopen(f"{BASE_URL}/api/idx/broker-accumulation/BBCA")
    assert req3.getcode() == 200, "Broker accum failed"
    data3 = json.loads(req3.read().decode())
    print("Accumulation series count:", len(data3["data"]["series"]), "| Trend:", data3["data"]["trend"])
    assert data3["status"] == "success"

    print("\n>>> 4. Testing /api/idx/financials/BBCA...")
    req4 = urllib.request.urlopen(f"{BASE_URL}/api/idx/financials/BBCA")
    assert req4.getcode() == 200, "Financials failed"
    data4 = json.loads(req4.read().decode())
    print("Financials items count:", len(data4["data"]["items"]), "| YoY EPS:", data4["data"]["yoy_eps_growth"])
    assert data4["status"] == "success"

    print("\n>>> 5. Testing /api/idx/analysis/BBCA...")
    req5 = urllib.request.urlopen(f"{BASE_URL}/api/idx/analysis/BBCA")
    assert req5.getcode() == 200, "Analysis failed"
    data5 = json.loads(req5.read().decode())
    print("Analysis Pivots:", data5["data"]["pivots"])
    assert data5["status"] == "success"

    print("\n>>> 6. Testing HTML DOM integrity...")
    req_html = urllib.request.urlopen(BASE_URL)
    assert req_html.getcode() == 200
    html = req_html.read().decode("utf-8")

    assert "id=\"stock-detail-modal\"" in html, "modal_stock_detail.html missing in DOM"
    assert "stock_detail_modal.js" in html, "stock_detail_modal.js missing in DOM"
    assert "stock_modal.css" in html or "@import" in html, "stock_modal css missing"
    assert "id=\"sidebar-quota-box\"" in html, "sidebar quota widget missing in DOM"
    assert "Bandar Flow" in html, "Bandar Flow column missing in DOM"

    print("HTML DOM Integrity: ALL CHECKS PASSED!")
    print("\n==========================================")
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! 🎉")
    print("==========================================")

if __name__ == "__main__":
    test_endpoints()
