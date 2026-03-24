# MoneyIQ Fund Analyzer

Instant, in-depth analysis of any Indian mutual fund. Built on live AMFI data via [mfapi.in](https://www.mfapi.in).

## What it does

Search for any Indian mutual fund and get a full analysis in seconds:

- **NAV History** - Interactive chart from inception to today
- **Returns** - 1Y, 3Y, 5Y, 7Y, 10Y, and since-inception CAGR
- **Rolling Returns** - 3Y and 5Y rolling return distributions with probability stats
- **Risk Metrics** - Volatility, Sharpe ratio, Sortino ratio, max drawdown with recovery time
- **Market Capture Ratios** - Up-market, down-market, and total capture ratio vs auto-detected benchmark

No sign-up. No API keys. No tracking. Just analysis.

## Deploy to Vercel

1. Push this repo to GitHub
2. Go to [vercel.com](https://vercel.com) -> New Project -> Import your repo
3. Click Deploy
4. Done.

## Benchmark auto-detection

| Fund Type | Benchmark |
|-----------|-----------|
| Small cap | Nifty Smallcap 250 |
| Mid cap | Nifty Midcap 150 |
| Large cap / Bluechip | Nifty 50 |
| Flexi cap / Multi cap | Nifty 500 |
| ELSS / Tax Saver | Nifty 500 |
| Default | Nifty 50 |

## Data source

All data from [mfapi.in](https://www.mfapi.in) (AMFI). Fetched live on every request.

## Disclaimer

For educational purposes only. Not investment advice. Past performance does not guarantee future results.

## Built by

[MoneyIQ](https://udayanonmoney.com)
