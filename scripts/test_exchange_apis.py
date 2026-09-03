"""
Test alternative NSE / BSE / Screener / Yahoo methods to get real verified data.
"""
import requests
import json

def test_nse_headers():
    print("=== Testing NSE with enhanced headers ===")
    s = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    try:
        r = s.get("https://www.nseindia.com", headers=headers, timeout=10)
        print(f"NSE Home Status: {r.status_code}")
        print(f"Cookies received: {len(s.cookies)}")
        
        api_headers = headers.copy()
        api_headers["Accept"] = "application/json, text/plain, */*"
        api_headers["Referer"] = "https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern"
        
        r2 = s.get("https://www.nseindia.com/api/corporate-shareholding?symbol=DIXON", headers=api_headers, timeout=10)
        print(f"Shareholding API Status: {r2.status_code}")
        if r2.status_code == 200:
            print("Shareholding response:", r2.text[:200])
    except Exception as e:
        print(f"NSE request failed: {e}")

def test_bse_api():
    print("\n=== Testing BSE India Corporate Filings ===")
    s = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bseindia.com/",
    }
    try:
        # BSE security code for Dixon: 540699, TCS: 532540, Reliance: 500325
        r = s.get("https://api.bseindia.com/BseIndiaAPI/api/ShareholdingPattern/w?scripcode=540699", headers=headers, timeout=10)
        print(f"BSE Shareholding Status: {r.status_code}")
        if r.status_code == 200:
            print("BSE response:", r.text[:300])
    except Exception as e:
        print(f"BSE request failed: {e}")

if __name__ == '__main__':
    test_nse_headers()
    test_bse_api()
