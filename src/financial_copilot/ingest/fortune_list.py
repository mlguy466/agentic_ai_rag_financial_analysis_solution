from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_CSV = DATA_DIR / "fortune_500.csv"

API_BASE = "https://fortune.com/api/page/directory/companies"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def fetch_page(page: int, year: int = 2024) -> dict[str, Any] | None:
    params = {"rankingId": 2, "rankingYear": year}
    response = requests.get(f"{API_BASE}/{page}/", params=params, headers=HEADERS, timeout=15)
    if response.status_code != 200:
        print(f"Failed to fetch page {page}: {response.status_code}")
        return None
    return response.json()


def extract_ticker_from_html(html: str) -> str | None:
    match = re.search(r"<script id=\"__NEXT_DATA__\"[^>]*>(.*?)</script>", html, re.DOTALL)
    if not match:
        return None

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    company = payload.get("props", {}).get("pageProps", {}).get("company", {})
    company_info = company.get("companyInfo", {})
    ticker = company_info.get("Ticker")
    if ticker and isinstance(ticker, str):
        return ticker.strip()
    return None


def fetch_company_ticker(url: str) -> str | None:
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return extract_ticker_from_html(response.text)
    except Exception:
        pass
    return None


def build_company_list(year: int = 2024, target: int = 500) -> list[dict[str, str]]:
    companies: list[dict[str, str]] = []
    page = 1

    while len(companies) < target:
        payload = fetch_page(page, year)
        if payload is None:
            break

        items = payload.get("items", [])
        if not items:
            break

        for item in items:
            if len(companies) >= target:
                break
            company = {
                "rank": str(len(companies) + 1),
                "name": item.get("name", "").strip(),
                "link": item.get("permalink") or item.get("uri") or "",
                "slug": item.get("slug", ""),
                "ticker": "",
            }
            companies.append(company)

        pagination = payload.get("pagination", {})
        if not pagination.get("hasMorePages", False):
            break

        page += 1
        time.sleep(0.3)

    return companies


def enrich_tickers(companies: list[dict[str, str]]) -> list[dict[str, str]]:
    for idx, company in enumerate(companies, start=1):
        if company["ticker"]:
            continue

        url = company["link"]
        if url and not url.startswith("http"):
            url = f"https://fortune.com{url}"

        if url:
            ticker = fetch_company_ticker(url)
            if ticker:
                company["ticker"] = ticker
                print(f"{idx}: {company['name']} -> {ticker}")
            else:
                print(f"{idx}: {company['name']} -> ticker not found")
        else:
            print(f"{idx}: {company['name']} -> no URL")

        time.sleep(0.4)

    return companies


def write_csv(companies: list[dict[str, str]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rank", "ticker", "company", "fortune_url"])
        for company in companies:
            writer.writerow([company["rank"], company["ticker"], company["name"], company["link"]])


def main() -> None:
    print("Fetching Fortune 500 list from Fortune.com API...")
    companies = build_company_list(year=2024, target=500)
    if not companies:
        raise SystemExit("No companies fetched.")

    print(f"Fetched {len(companies)} companies. Enriching tickers...")
    companies = enrich_tickers(companies)

    print(f"Writing {OUTPUT_CSV}")
    write_csv(companies, OUTPUT_CSV)
    print("Done.")


if __name__ == "__main__":
    main()
