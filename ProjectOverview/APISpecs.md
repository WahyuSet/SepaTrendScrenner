Base URL: https://stock.arjum.com
API Key : sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms

1. Analisa Saham Komprehensif
Menjalankan mesin analisa teknikal, bandarmologi, dan rasio risiko otomatis untuk 1 saham (contoh: BBCA, RAJA, TLKM) serta memberikan sinyal rekomendasi.
Berdasarkan halaman IDX Edge PRO yang sedang Anda buka, informasi umum mengenai API ini adalah sebagai berikut:

Base URL: [https://stock.arjum.com](https://stock.arjum.com)

Autentikasi: Sertakan API Key pada header HTTP request X-API-Key: sk_live_...

Saat ini, halaman yang sedang aktif hanya menampilkan rincian detail (parameter, contoh kode, dan contoh respons) untuk endpoint Analisa Saham Komprehensif. Untuk endpoint lainnya, sistem hanya menampilkan daftar path/route-nya saja di menu samping (sidebar).

Berikut adalah dokumentasi yang dapat dihimpun berdasarkan tampilan halaman saat ini:

1. Analisa Saham Komprehensif
Menjalankan mesin analisa teknikal, bandarmologi, dan rasio risiko otomatis untuk 1 saham serta memberikan sinyal rekomendasi.

Method: GET

Endpoint: /api/analysis/{code}

Parameter API:

code (string, path): Wajib. Kode saham 4 huruf (contoh: BBCA, RAJA, TLKM). Default: BBCA.

Contoh Request (Python):

Python
import requests

url = "https://stock.arjum.com/api/analysis/BBCA"
headers = {
    "X-API-Key": "sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)
data = response.json()
print("Status Code:", response.status_code)
print(data)
Contoh Format JSON Response:

JSON
{
  "stock_code": "BBCA",
  "output": "===========================================================\nANALISIS SAHAM: BBCA (Bank Central Asia Tbk.)\n===========================================================\nHarga Terakhir: 10,250 (+1.48%)\nSinyal Utama  : STRONG BUY (Win Rate: 78.5%)\nAkumulasi     : BIG ACCUM (Top 3 Broker Buy > Sell)\n\n[REKOMENDASI TRADING]\n- Entry Area : 10,150 - 10,250\n- Target 1   : 10,500 (+2.4%)\n- Target 2   : 10,800 (+5.3%)\n- Stop Loss  : 9,950 (-2.9%)\n==========================================================="
}


2. Broker Summary (Bandarmologi)Endpoint ini digunakan untuk mengambil rincian akumulasi/distribusi broker (Top Buyers, Top Sellers, Net Value/Volume, Foreign Flow) untuk saham tertentu dalam rentang tanggal.Method: GETBase URL: [https://stock.arjum.com](https://stock.arjum.com)Endpoint: /api/broker-summary/{code}Header Wajib: X-API-Key: sk_live_...Parameter APINamaTipe / LokasiStatusDeskripsicodestring (path)WajibKode saham 4 huruf (contoh: BBCA) (default: BBCA)start_datestring (query)OpsionalTanggal mulai filter (Format: YYYY-MM-DD)end_datestring (query)OpsionalTanggal akhir filter (Format: YYYY-MM-DD)netboolean (query)OpsionalTampilkan hanya nilai net buy/sell broker (default: false)broker_limitinteger (query)OpsionalMaks jumlah broker di array brokers (min: 1) (default: 20)level_limitinteger (query)OpsionalMaks pasangan buy/sell di broker_levels (min: 1) (default: 25)all_databoolean (query)OpsionalAbaikan semua limit, return seluruh data broker & level (default: false)flowstring (query)OpsionalFilter aliran dana: F (foreign), D (domestik), all (gabungan) (default: all)Contoh Request (Python)Pythonimport requests

url = "https://stock.arjum.com/api/broker-summary/BBCA?net=false&broker_limit=20&level_limit=25&all_data=false&flow=all"
headers = {
    "X-API-Key": "sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)
data = response.json()
print("Status Code:", response.status_code)
print(data)
Contoh Format JSON ResponseJSON{
  "flow": "all",
  "stock_code": "BBCA",
  "latest_date": "2026-07-24",
  "broker_start": "2026-07-24",
  "broker_end": "2026-07-24",
  "brokers": [
    {
      "broker_code": "BK",
      "broker_name": "J.P. Morgan Sekuritas",
      "bval": 85400000000,
      "sval": 12000000000,
      "nval": 73400000000,
      "nvol": 71600,
      "bfrq": 1500,
      "sfrq": 2800
    },
    {
      "broker_code": "ZP",
      "broker_name": "Maybank Sekuritas",
      "bval": 42000000000,
      "sval": 8000000000,
      "nval": 34000000000,
      "nvol": 33100,
      "bfrq": 850,
      "sfrq": 1200
    },
    {
      "broker_code": "AK",
      "broker_name": "UBS Sekuritas",
      "bval": 31000000000,
      "sval": 5000000000,
      "nval": 26000000000,
      "nvol": 25300,
      "bfrq": 620,
      "sfrq": 900
    }
  ]
}


Berdasarkan halaman IDX Edge PRO yang sedang Anda buka saat ini, berikut adalah dokumentasi lengkap untuk endpoint Akumulasi Broker Historis:3. Akumulasi Broker HistorisEndpoint ini digunakan untuk mengambil tren historis akumulasi vs distribusi broker dari waktu ke waktu untuk melihat pergerakan bandar.Method: GETBase URL: [https://stock.arjum.com](https://stock.arjum.com)Endpoint: /api/broker-accumulation/{code}Header Wajib: X-API-Key: sk_live_...Parameter APINamaTipe / LokasiStatusDeskripsicodestring (path)WajibKode saham 4 huruf (default: BBCA)start_datestring (query)OpsionalTanggal mulai filter (Format: YYYY-MM-DD)end_datestring (query)OpsionalTanggal akhir filter (Format: YYYY-MM-DD)topinteger (query)OpsionalJumlah Top Broker Akumulasi (1 - 5) (default: 3)brokersstring (query)OpsionalFilter broker spesifik dipisah koma (contoh: BK,ZP,AK)Contoh Kode (Python)Pythonimport requests

url = "https://stock.arjum.com/api/broker-accumulation/BBCA?top=3"
headers = {
    "X-API-Key": "sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)
data = response.json()
print("Status Code:", response.status_code)
print(data)
Contoh Format JSON ResponseJSON{
  "code": "BBCA",
  "start_date": "2026-06-01",
  "end_date": "2026-07-24",
  "top_buyers": [
    {
      "broker_code": "BK",
      "broker_name": "J.P. Morgan Sekuritas",
      "net_val": 185000000000
    }
  ],
  "series": [
    {
      "date": "2026-07-20",
      "accum_val": 45000000000
    },
    {
      "date": "2026-07-24",
      "accum_val": 133400000000
    }
  ]
}


4. Laporan KeuanganEndpoint ini mengambil data laporan keuangan (laba rugi, neraca, atau arus kas) secara kuartalan maupun tahunan untuk satu saham.Method: GETBase URL: [https://stock.arjum.com](https://stock.arjum.com)Endpoint: /api/financial-statements/{code}Header Wajib: X-API-Key: sk_live_...Parameter APINamaTipe / LokasiStatusDeskripsicodestring (path)WajibKode saham 4 huruf (contoh: BBCA) (default: BBCA)report_typestring (query)OpsionalINCOME_STATEMENT | BALANCE_SHEET | CASH_FLOW_REPORT (default: INCOME_STATEMENT)periodstring (query)Opsionalquarterly | annually (default: quarterly)limitinteger (query)OpsionalJumlah periode (max 40) (default: 12)yearstring (query)OpsionalFilter tahun spesifik (opsional)Contoh Request (Python)Python# Python (requests)
import requests

url = "https://stock.arjum.com/api/financial-statements/BBCA?report_type=INCOME_STATEMENT&period=quarterly&limit=12"
headers = {
    "X-API-Key": "sk_live_pHzfNvhf-prFU2zXdclByx0tBdS8UyYOTKid3LY_lms",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)
data = response.json()
print("Status Code:", response.status_code)
print(data)
Contoh Format JSON ResponseJSON{
  "stock_code": "BBCA",
  "report_type": "INCOME_STATEMENT",
  "period": "quarterly",
  "count": 1,
  "items": [
    {
      "year": "2026",
      "quarter": "1",
      "label": "Q1 2026",
      "fetched_at": "2026-08-02 19:32:25",
      "data": {
        "laba_rugi": 14689799000000,
        "laba_rugi_per_saham": 119
      }
    }
  ]
}


Note : Test Konek bisa di kosongkan Api keynya