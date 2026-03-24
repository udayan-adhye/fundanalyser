"""
Vercel Serverless Function: Fund Search
GET /api/search?q=parag+parikh

Searches mfapi.in for matching mutual fund schemes.
Returns JSON array of {schemeCode, schemeName}.
"""

import json
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_params = parse_qs(urlparse(self.path).query)
        q = query_params.get("q", [""])[0].strip()

        if not q or len(q) < 2:
            self._respond(400, {"error": "Query must be at least 2 characters", "results": []})
            return

        try:
            url = f"https://api.mfapi.in/mf/search?q={urllib.request.quote(q)}"
            req = urllib.request.Request(url, headers={"User-Agent": "MoneyIQ-Fund-Analyzer/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            results = []
            for item in data:
                name = item.get("schemeName", "")
                results.append({
                    "schemeCode": item["schemeCode"],
                    "schemeName": name,
                    "isDirect": "direct" in name.lower(),
                    "isGrowth": "growth" in name.lower(),
                })

            results.sort(key=lambda x: (not x["isDirect"], not x["isGrowth"]))
            self._respond(200, {"results": results[:20]})

        except Exception as e:
            self._respond(502, {"error": f"Failed to search funds: {str(e)}", "results": []})

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
