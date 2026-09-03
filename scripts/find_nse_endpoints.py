from curl_cffi import requests
import re
import json

s = requests.Session(impersonate='chrome124')
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0 Safari/537.36',
    'referer': 'https://www.nseindia.com/'
}
r = s.get('https://www.nseindia.com/companies-listing/corporate-filings-shareholding-pattern', headers=headers)
print('Page status:', r.status_code)
if r.status_code == 200:
    apis = set(re.findall(r'/api/[a-zA-Z0-9_\-\?&=]+', r.text))
    print('APIs in HTML:', apis)
    
    # Let's inspect js scripts
    script_urls = re.findall(r'src="([^"]+\.js)"', r.text)
    for surl in script_urls:
        if not surl.startswith('http'):
            surl = 'https://www.nseindia.com' + surl
        rjs = s.get(surl, headers=headers)
        if rjs.status_code == 200:
            js_apis = set(re.findall(r'/api/[a-zA-Z0-9_\-]+', rjs.text))
            sh_apis = [a for a in js_apis if 'share' in a.lower() or 'holding' in a.lower() or 'corp' in a.lower() or 'filing' in a.lower()]
            if sh_apis:
                print(f"Found in {surl.split('/')[-1]}:", sh_apis)
