"""MoneyIQ Fund Analyzer - Flask API for Vercel"""
import json
import math
import urllib.request
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

RISK_FREE_RATE = 0.07
ROLLING_WINDOWS = [3, 5]
WINDOW_TOLERANCE = 10

MARKET_PROXIES = {
    "nifty_50":       {"code": "120716", "name": "Nifty 50", "fund": "UTI Nifty 50 Index Fund Direct Growth"},
    "nifty_midcap":   {"code": "120684", "name": "Nifty Midcap 150", "fund": "Motilal Oswal Nifty Midcap 150 Index Fund Direct Growth"},
    "nifty_smallcap": {"code": "125494", "name": "Nifty Smallcap 250", "fund": "Motilal Oswal Nifty Smallcap 250 Index Fund Direct Growth"},
    "nifty_500":      {"code": "147625", "name": "Nifty 500", "fund": "Motilal Oswal Nifty 500 Index Fund Direct Plan"},
    "nifty_next50":   {"code": "120700", "name": "Nifty Next 50", "fund": "UTI Nifty Next 50 Index Fund Direct Growth"},
    "sensex":         {"code": "119707", "name": "Sensex", "fund": "HDFC Index Fund Sensex Direct Growth"},
}


def fetch_nav(scheme_code):
    url = f"https://api.mfapi.in/mf/{scheme_code}"
    req = urllib.request.Request(url, headers={"User-Agent": "MoneyIQ-Fund-Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = json.loads(resp.read().decode("utf-8"))
    if raw.get("status") == "ERROR" or "data" not in raw:
        raise ValueError("API returned error or no data")
    meta = raw["meta"]
    nav_list = []
    for entry in raw["data"]:
        try:
            date = datetime.strptime(entry["date"], "%d-%m-%Y")
            nav = float(entry["nav"])
            nav_list.append((date, nav))
        except (ValueError, KeyError):
            continue
    nav_list.sort(key=lambda x: x[0])
    return meta, nav_list


def calculate_cagr(start_nav, end_nav, days):
    if start_nav <= 0 or days <= 0:
        return None
    years = days / 365.25
    return (end_nav / start_nav) ** (1 / years) - 1


def calculate_point_to_point_returns(nav_list):
    if len(nav_list) < 2:
        return {}
    latest_date, latest_nav = nav_list[-1]
    earliest_date, earliest_nav = nav_list[0]
    results = {}
    periods = {"1Y": 365, "3Y": 3*365, "5Y": 5*365, "7Y": 7*365, "10Y": 10*365}
    for label, target_days in periods.items():
        target_date = latest_date - timedelta(days=target_days)
        closest = min(nav_list, key=lambda x: abs((x[0] - target_date).days))
        if abs((closest[0] - target_date).days) <= 15:
            actual_days = (latest_date - closest[0]).days
            cagr = calculate_cagr(closest[1], latest_nav, actual_days)
            if cagr is not None:
                results[label] = {
                    "cagr_pct": round(cagr * 100, 2),
                    "absolute_return_pct": round((latest_nav / closest[1] - 1) * 100, 2),
                    "start_date": closest[0].strftime("%Y-%m-%d"),
                    "start_nav": round(closest[1], 2),
                    "end_date": latest_date.strftime("%Y-%m-%d"),
                    "end_nav": round(latest_nav, 2),
                }
    total_days = (latest_date - earliest_date).days
    inception_cagr = calculate_cagr(earliest_nav, latest_nav, total_days)
    if inception_cagr is not None:
        results["since_inception"] = {
            "cagr_pct": round(inception_cagr * 100, 2),
            "absolute_return_pct": round((latest_nav / earliest_nav - 1) * 100, 2),
            "start_date": earliest_date.strftime("%Y-%m-%d"),
            "start_nav": round(earliest_nav, 2),
            "end_date": latest_date.strftime("%Y-%m-%d"),
            "end_nav": round(latest_nav, 2),
            "years": round(total_days / 365.25, 1),
        }
    return results


def calculate_rolling_returns(nav_list, window_years):
    target_days = int(window_years * 365.25)
    rolling = []
    for i in range(len(nav_list)):
        start_date, start_nav = nav_list[i]
        target_end = start_date + timedelta(days=target_days)
        best_match = None
        best_diff = float("inf")
        for j in range(i + 1, len(nav_list)):
            diff = abs((nav_list[j][0] - target_end).days)
            if diff < best_diff:
                best_diff = diff
                best_match = j
            elif diff > best_diff:
                break
        if best_match is not None and best_diff <= WINDOW_TOLERANCE:
            end_date, end_nav = nav_list[best_match]
            actual_days = (end_date - start_date).days
            cagr = calculate_cagr(start_nav, end_nav, actual_days)
            if cagr is not None:
                rolling.append({
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "cagr_pct": round(cagr * 100, 2),
                })
    return rolling


def summarize_rolling(rolling_data):
    if not rolling_data:
        return None
    returns = [r["cagr_pct"] for r in rolling_data]
    returns_sorted = sorted(returns)
    n = len(returns_sorted)
    def pctl(data, p):
        k = (n - 1) * (p / 100)
        f, c = math.floor(k), math.ceil(k)
        return data[int(k)] if f == c else data[f] * (c - k) + data[c] * (k - f)
    positive_count = sum(1 for r in returns if r > 0)
    above_10 = sum(1 for r in returns if r > 10)
    above_15 = sum(1 for r in returns if r > 15)
    return {
        "total_windows": n,
        "best_pct": round(max(returns), 2),
        "worst_pct": round(min(returns), 2),
        "average_pct": round(sum(returns) / n, 2),
        "median_pct": round(pctl(returns_sorted, 50), 2),
        "p10_pct": round(pctl(returns_sorted, 10), 2),
        "p25_pct": round(pctl(returns_sorted, 25), 2),
        "p75_pct": round(pctl(returns_sorted, 75), 2),
        "p90_pct": round(pctl(returns_sorted, 90), 2),
        "positive_probability_pct": round(positive_count / n * 100, 1),
        "above_10_probability_pct": round(above_10 / n * 100, 1),
        "above_15_probability_pct": round(above_15 / n * 100, 1),
    }


def build_distribution(rolling_data, bucket_size=2):
    if not rolling_data:
        return []
    returns = [r["cagr_pct"] for r in rolling_data]
    min_r = math.floor(min(returns) / bucket_size) * bucket_size
    max_r = math.ceil(max(returns) / bucket_size) * bucket_size
    buckets = []
    current = min_r
    while current < max_r:
        count = sum(1 for r in returns if current <= r < current + bucket_size)
        buckets.append({
            "range_start": current, "range_end": current + bucket_size,
            "label": f"{current}% to {current + bucket_size}%",
            "count": count, "percentage": round(count / len(returns) * 100, 1),
        })
        current += bucket_size
    return buckets


def calculate_risk_metrics(nav_list):
    if len(nav_list) < 30:
        return {}
    daily_returns = []
    for i in range(1, len(nav_list)):
        days_gap = (nav_list[i][0] - nav_list[i-1][0]).days
        if days_gap <= 5:
            daily_returns.append((nav_list[i][1] / nav_list[i-1][1]) - 1)
    if len(daily_returns) < 20:
        return {}
    n = len(daily_returns)
    mean_daily = sum(daily_returns) / n
    annualized_return = (1 + mean_daily) ** 252 - 1
    variance = sum((r - mean_daily) ** 2 for r in daily_returns) / (n - 1)
    daily_std = math.sqrt(variance)
    annual_std = daily_std * math.sqrt(252)
    downside = [r for r in daily_returns if r < 0]
    downside_std = math.sqrt(sum(r**2 for r in downside) / len(downside)) * math.sqrt(252) if downside else 0.001
    sharpe = (annualized_return - RISK_FREE_RATE) / annual_std if annual_std > 0 else 0
    sortino = (annualized_return - RISK_FREE_RATE) / downside_std if downside_std > 0 else 0
    peak = nav_list[0][1]
    max_dd = 0
    dd_peak_date = dd_trough_date = current_peak_date = nav_list[0][0]
    for date, nav in nav_list:
        if nav > peak:
            peak = nav
            current_peak_date = date
        dd = (nav - peak) / peak
        if dd < max_dd:
            max_dd = dd
            dd_peak_date = current_peak_date
            dd_trough_date = date
    recovery_days = None
    found_trough = False
    for date, nav in nav_list:
        if date == dd_trough_date:
            found_trough = True
        if found_trough and nav >= peak:
            recovery_days = (date - dd_trough_date).days
            break
    return {
        "annualized_return_pct": round(annualized_return * 100, 2),
        "annualized_volatility_pct": round(annual_std * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "max_drawdown_peak_date": dd_peak_date.strftime("%Y-%m-%d"),
        "max_drawdown_trough_date": dd_trough_date.strftime("%Y-%m-%d"),
        "recovery_days": recovery_days,
        "risk_free_rate_used_pct": round(RISK_FREE_RATE * 100, 2),
        "trading_days_analyzed": len(daily_returns),
    }


def detect_market_proxy(scheme_name):
    name = scheme_name.lower().replace("-", " ")
    if any(kw in name for kw in ["small cap", "smallcap"]):
        return "nifty_smallcap"
    if any(kw in name for kw in ["mid cap", "midcap"]):
        return "nifty_midcap"
    if any(kw in name for kw in ["large cap", "largecap", "bluechip", "nifty 50", "focused"]):
        return "nifty_50"
    if any(kw in name for kw in ["flexi cap", "flexicap", "multi cap", "multicap"]):
        return "nifty_500"
    if any(kw in name for kw in ["elss", "tax saver"]):
        return "nifty_500"
    return "nifty_50"


def compute_monthly_returns(nav_list):
    monthly_navs = {}
    for date, nav in nav_list:
        monthly_navs[(date.year, date.month)] = nav
    sorted_months = sorted(monthly_navs.keys())
    returns = {}
    for i in range(1, len(sorted_months)):
        prev, curr = sorted_months[i-1], sorted_months[i]
        if monthly_navs[prev] > 0:
            returns[curr] = ((monthly_navs[curr] / monthly_navs[prev]) - 1) * 100
    return returns


def calculate_capture_ratios(fund_nav, market_nav, period_years=None):
    fund_m = compute_monthly_returns(fund_nav)
    market_m = compute_monthly_returns(market_nav)
    common = sorted(set(fund_m.keys()) & set(market_m.keys()))
    if period_years and common:
        last = common[-1]
        cutoff = (last[0] - period_years, last[1])
        common = [m for m in common if m > cutoff]
    if len(common) < 12:
        return None
    up_f, up_m, dn_f, dn_m = [], [], [], []
    for m in common:
        if market_m[m] > 0:
            up_f.append(fund_m[m]); up_m.append(market_m[m])
        elif market_m[m] < 0:
            dn_f.append(fund_m[m]); dn_m.append(market_m[m])
    if len(up_m) < 3 or len(dn_m) < 3:
        return None
    avg_uf, avg_um = sum(up_f)/len(up_f), sum(up_m)/len(up_m)
    avg_df, avg_dm = sum(dn_f)/len(dn_f), sum(dn_m)/len(dn_m)
    up_cap = (avg_uf / avg_um) * 100 if avg_um else 0
    dn_cap = (avg_df / avg_dm) * 100 if avg_dm else 0
    ratio = up_cap / dn_cap if dn_cap else 0
    return {
        "up_capture_pct": round(up_cap, 1),
        "down_capture_pct": round(dn_cap, 1),
        "capture_ratio": round(ratio, 2),
        "up_months_analyzed": len(up_m),
        "down_months_analyzed": len(dn_m),
        "total_months_analyzed": len(common),
    }


@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"error": "Query must be at least 2 characters", "results": []}), 400
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
        resp = jsonify({"results": results[:20]})
        resp.headers["Cache-Control"] = "public, max-age=3600"
        return resp
    except Exception as e:
        return jsonify({"error": f"Failed to search funds: {str(e)}", "results": []}), 502


@app.route("/api/analyze")
def analyze():
    scheme_code = request.args.get("scheme", "").strip()
    if not scheme_code or not scheme_code.isdigit():
        return jsonify({"error": "Valid scheme code required (e.g. ?scheme=122639)"}), 400
    try:
        meta, nav_list = fetch_nav(scheme_code)
        if len(nav_list) < 30:
            return jsonify({"error": "Insufficient NAV data for analysis"}), 422
        scheme_name = meta.get("scheme_name", "Unknown Fund")
        earliest = nav_list[0]
        latest = nav_list[-1]
        years_of_data = round((latest[0] - earliest[0]).days / 365.25, 1)
        ptp = calculate_point_to_point_returns(nav_list)
        rolling = {}
        for w in ROLLING_WINDOWS:
            if years_of_data >= w + 0.5:
                r = calculate_rolling_returns(nav_list, w)
                if r:
                    rolling[f"{w}Y"] = {
                        "window_years": w,
                        "summary": summarize_rolling(r),
                        "distribution": build_distribution(r),
                        "time_series": [
                            {"start_date": x["start_date"], "cagr_pct": x["cagr_pct"]}
                            for x in r[::5]
                        ],
                    }
        risk = calculate_risk_metrics(nav_list)
        capture = {}
        try:
            proxy_key = detect_market_proxy(scheme_name)
            proxy_info = MARKET_PROXIES.get(proxy_key, MARKET_PROXIES["nifty_50"])
            _, market_nav = fetch_nav(proxy_info["code"])
            if market_nav:
                for label, yrs in [("3Y", 3), ("5Y", 5), ("since_inception", None)]:
                    cr = calculate_capture_ratios(nav_list, market_nav, yrs)
                    if cr:
                        cr["benchmark"] = proxy_info["name"]
                        cr["benchmark_fund"] = proxy_info["fund"]
                        capture[label] = cr
        except Exception:
            pass
        nav_chart = [
            {"date": d.strftime("%Y-%m-%d"), "nav": round(n, 2)}
            for d, n in nav_list[::5]
        ]
        if nav_list[-1] != nav_list[::5][-1] if nav_list[::5] else True:
            nav_chart.append({"date": latest[0].strftime("%Y-%m-%d"), "nav": round(latest[1], 2)})
        result = {
            "meta": {
                "scheme_code": meta.get("scheme_code", scheme_code),
                "scheme_name": scheme_name,
                "fund_house": meta.get("fund_house", ""),
                "scheme_category": meta.get("scheme_category", ""),
                "scheme_type": meta.get("scheme_type", ""),
            },
            "data_summary": {
                "total_data_points": len(nav_list),
                "earliest_date": earliest[0].strftime("%Y-%m-%d"),
                "latest_date": latest[0].strftime("%Y-%m-%d"),
                "earliest_nav": round(earliest[1], 4),
                "latest_nav": round(latest[1], 4),
                "years_of_data": years_of_data,
            },
            "nav_chart": nav_chart,
            "point_to_point_returns": ptp,
            "rolling_returns": rolling,
            "risk_metrics": risk,
            "capture_ratios": capture,
            "calculated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "disclaimer": (
                "This analysis is generated using publicly available historical NAV data "
                "from AMFI (Association of Mutual Funds in India) and is provided for "
                "educational and informational purposes only. It does not constitute "
                "investment advice. Past performance does not guarantee future results. "
                "Mutual fund investments are subject to market risks."
            ),
        }
        resp = jsonify(result)
        resp.headers["Cache-Control"] = "public, max-age=1800"
        return resp
    except Exception as e:
        return jsonify({"error": f"Analysis failed: {str(e)}"}), 502
