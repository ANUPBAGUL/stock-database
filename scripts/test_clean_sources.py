from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
import json

symbols = [
    {"nse": "DIXON", "bse": "540699", "name": "Dixon Technologies"},
    {"nse": "TCS", "bse": "532540", "name": "Tata Consultancy Services"},
    {"nse": "RELIANCE", "bse": "500325", "name": "Reliance Industries"}
]

print("===============================================================", flush=True)
print("1. TESTING SCREENER.IN (CLEAN INDIAN FINANCIALS & SHAREHOLDING)", flush=True)
print("===============================================================", flush=True)

s = cffi_requests.Session(impersonate='chrome124')
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

for item in symbols:
    sym = item["nse"]
    url = f"https://www.screener.in/company/{sym}/consolidated/"
    try:
        r = s.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            url = f"https://www.screener.in/company/{sym}/"
            r = s.get(url, headers=headers, timeout=10)
            
        print(f"\n[{sym}] Screener URL: {url} | HTTP {r.status_code}", flush=True)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            
            # Top ratios
            ratios = {}
            for li in soup.find_all('li', class_='flex'):
                name_span = li.find('span', class_='name')
                val_span = li.find('span', class_='number') or li.find('span', class_='value')
                if name_span and val_span:
                    name = name_span.text.strip()
                    val = val_span.text.strip().replace(',', '')
                    ratios[name] = val
            print(f"  Ratios: Price=Rs.{ratios.get('Current Price')}, ROCE={ratios.get('ROCE')}%, ROE={ratios.get('ROE')}%, PE={ratios.get('Stock P/E')}, MarketCap=Rs.{ratios.get('Market Cap')} Cr", flush=True)
            
            # Shareholding
            shp_section = soup.find('section', id='shareholding')
            if shp_section:
                table = shp_section.find('table')
                if table:
                    headers_row = [th.text.strip() for th in table.find_all('th')]
                    periods = [h for h in headers_row if h]
                    print(f"  Shareholding Quarters: {periods[-2:]}", flush=True)
                    for tr in table.find('tbody').find_all('tr'):
                        row_title = tr.find('td', class_='text') or tr.find('td')
                        if row_title:
                            cells = [td.text.strip().replace('%', '') for td in tr.find_all('td')[1:]]
                            if cells:
                                print(f"    {row_title.text.strip():<15}: {cells[-1]}% (Latest {periods[-1] if periods else ''})", flush=True)
                                
            # Balance Sheet (Debt, Leases, Equity, Assets)
            bs_section = soup.find('section', id='balance-sheet')
            if bs_section:
                table = bs_section.find('table')
                if table:
                    years = [th.text.strip() for th in table.find_all('th') if th.text.strip()]
                    print(f"  Balance Sheet (Latest: {years[-1]}):", flush=True)
                    for tr in table.find('tbody').find_all('tr'):
                        tds = tr.find_all('td')
                        if tds:
                            row_name = tds[0].text.strip()
                            if any(k in row_name.lower() for k in ['borrowing', 'equity', 'liabilit', 'asset', 'cwig', 'fixed']):
                                vals = [t.text.strip().replace(',', '') for t in tds[1:]]
                                print(f"    {row_name:<20}: Rs.{vals[-1]} Cr", flush=True)

    except Exception as e:
        print(f"[{sym}] Screener Error: {e}", flush=True)

print("\n===============================================================", flush=True)
print("2. TESTING BSE INDIA OFFICIAL ANNOUNCEMENTS & METADATA API", flush=True)
print("===============================================================", flush=True)

bse_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bseindia.com/",
    "Accept": "application/json, text/plain, */*"
}
for item in symbols:
    bse_code = item["bse"]
    sym = item["nse"]
    
    # Announcements
    url_ann = f"https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w?pageno=1&strCat=-1&strPrevDate=&strScrip={bse_code}&strSearch=P&strToDate=&strType=C"
    try:
        r = s.get(url_ann, headers=bse_headers)
        if r.status_code == 200:
            data = r.json()
            table = data.get("Table", [])
            print(f"\n[{sym}] BSE Official Announcements: {len(table)} filings", flush=True)
            if table:
                latest = table[0]
                print(f"    Latest ({latest.get('DT_TM')}): {latest.get('NEWSSUB')}", flush=True)
                if latest.get('ATTACHMENTNAME'):
                    print(f"    Official PDF: https://www.bseindia.com/xml-data/corpfiling/AttachLive/{latest.get('ATTACHMENTNAME')}", flush=True)
    except Exception as e:
        print(f"[{sym}] BSE Announcements Error: {e}", flush=True)
