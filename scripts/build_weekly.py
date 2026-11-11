#!/usr/bin/env python3
"""Build a source-linked weekly market brief draft. Standard library only."""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
UA = "market-brief-weekly/1.0 (research digest; contact: configure repository owner)"
NOW = dt.datetime.now(dt.timezone.utc)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url: str, timeout: int = 18) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/rss+xml, application/xml, text/xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def week_range(week: str):
    today = dt.date.today()
    if week == "latest":
        # Week ending on the latest completed Friday (or today when run on Friday).
        end = today - dt.timedelta(days=(today.weekday() - 4) % 7)
        start = end - dt.timedelta(days=4)
        return start, end
    m = re.fullmatch(r"(\d{4})-W(\d{2})", week)
    if not m:
        raise ValueError("--week must be latest or ISO week like 2026-W45")
    year, number = map(int, m.groups())
    start = dt.date.fromisocalendar(year, number, 1)
    return start, start + dt.timedelta(days=4)


def iso_week_id(end: dt.date) -> str:
    y, w, _ = end.isocalendar()
    return f"{y}-W{w:02d}"


def parse_time(item):
    for name in ("published", "updated", "pubDate", "date"):
        raw = item.findtext(name)
        if not raw:
            continue
        try:
            value = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            try:
                value = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc)
    return None


def parse_feed(raw: bytes, source: dict, start: dt.date, end: dt.date):
    root = ET.fromstring(raw)
    items = root.findall(".//item")
    # Atom feeds use a namespace.
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    result = []
    for item in items:
        title = item.findtext("title") or item.findtext("{http://www.w3.org/2005/Atom}title") or ""
        link = item.findtext("link") or ""
        if not link:
            link_el = item.find("{http://www.w3.org/2005/Atom}link")
            if link_el is not None:
                link = link_el.attrib.get("href", "")
        when = parse_time(item)
        if not title.strip() or not link.strip() or not when or not (start <= when.date() <= end):
            continue
        result.append({"title": re.sub(r"\s+", " ", html.unescape(title)).strip(), "url": link.strip(), "source": source["name"], "category": source.get("category", "新闻"), "region": source.get("region", ""), "published_at": when.isoformat(), "summary": "", "review_status": "待阅读原文"})
    return result


def fetch_news(sources: dict, start: dt.date, end: dt.date, warnings: list):
    all_items, seen = [], set()
    for source in sources.get("feeds", []):
        if source.get("kind") == "html":
            warnings.append(f"{source['name']}: 当前为人工核查入口（非 RSS），未自动抓取。")
            continue
        try:
            entries = parse_feed(fetch(source["url"]), source, start, end)
            for entry in entries:
                key = entry["url"].split("#", 1)[0]
                if key not in seen:
                    seen.add(key)
                    all_items.append(entry)
        except Exception as exc:  # preserve partial collection
            warnings.append(f"{source['name']}: 抓取失败：{type(exc).__name__}: {exc}")
    return sorted(all_items, key=lambda x: x["published_at"], reverse=True)


def yahoo_chart(symbol: str, start: dt.date, end: dt.date):
    # Include the preceding week so the return compares Friday close to Friday close,
    # rather than Monday close to Friday close.
    fetch_start = start - dt.timedelta(days=7)
    params = urllib.parse.urlencode({"period1": int(dt.datetime.combine(fetch_start, dt.time.min, dt.timezone.utc).timestamp()), "period2": int(dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, dt.timezone.utc).timestamp()), "interval": "1d", "events": "history"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol, safe='')}?{params}"
    data = json.loads(fetch(url))
    chart = data.get("chart", {})
    if chart.get("error"):
        raise ValueError(str(chart["error"]))
    result = chart["result"][0]
    exchange_tz = result.get("meta", {}).get("exchangeTimezoneName") or "UTC"
    try:
        zone = ZoneInfo(exchange_tz)
    except ZoneInfoNotFoundError:
        zone = dt.timezone.utc
    quote = result["indicators"]["quote"][0]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose", [])
    closes = quote.get("close", [])
    stamps = result.get("timestamp", [])
    observations = []
    for i, stamp in enumerate(stamps):
        close = closes[i] if i < len(closes) else None
        if close is not None:
            observations.append({"date": dt.datetime.fromtimestamp(stamp, dt.timezone.utc).astimezone(zone).date().isoformat(), "close": close, "adjclose": adj[i] if i < len(adj) else close})
    baseline = [x for x in observations if x["date"] < start.isoformat()]
    weekly = [x for x in observations if start.isoformat() <= x["date"] <= end.isoformat()]
    if not baseline or not weekly:
        raise ValueError("周初基准价或周内收盘价不足")
    first, last = baseline[-1], weekly[-1]
    return {"observations": weekly, "baseline_close": first["close"], "baseline_date": first["date"], "start_close": weekly[0]["close"], "end_close": last["close"], "change_pct": (last["close"] / first["close"] - 1) * 100, "change_abs": last["close"] - first["close"], "start_date": first["date"], "end_date": last["date"], "currency": result.get("meta", {}).get("currency"), "exchange_timezone": exchange_tz}


def fetch_markets(config: dict, start: dt.date, end: dt.date, warnings: list):
    result = []
    for item in config.get("symbols", []):
        try:
            series = yahoo_chart(item["symbol"], start, end)
            result.append({**item, **series, "source_url": f"https://finance.yahoo.com/quote/{urllib.parse.quote(item['symbol'], safe='')}"})
        except Exception as exc:
            warnings.append(f"行情 {item['symbol']}: 抓取失败：{type(exc).__name__}: {exc}")
    return result


def fetch_fred(api_key: str | None, start: dt.date, end: dt.date, warnings: list):
    if not api_key:
        return []
    # Core series chosen for weekly context; FRED is not real-time and observations can be revised.
    series = [("DGS2", "美国 2 年期国债收益率"), ("DGS10", "美国 10 年期国债收益率"), ("FEDFUNDS", "联邦基金有效利率"), ("UNRATE", "失业率"), ("CPIAUCSL", "CPI"), ("PCEPI", "PCE 价格指数")]
    out = []
    for sid, label in series:
        try:
            q = urllib.parse.urlencode({"series_id": sid, "api_key": api_key, "file_type": "json", "observation_start": (start - dt.timedelta(days=60)).isoformat(), "observation_end": end.isoformat(), "sort_order": "asc"})
            payload = json.loads(fetch("https://api.stlouisfed.org/fred/series/observations?" + q))
            obs = [{"date": x["date"], "value": float(x["value"])} for x in payload.get("observations", []) if x.get("value") not in (None, ".")]
            if obs:
                out.append({"series_id": sid, "name": label, "observations": obs, "latest": obs[-1], "source_url": f"https://fred.stlouisfed.org/series/{sid}"})
        except Exception as exc:
            warnings.append(f"FRED {sid}: 抓取失败：{type(exc).__name__}: {exc}")
    return out


def make_report(week_id: str, start: dt.date, end: dt.date):
    warnings = []
    sources = read_json(ROOT / "config" / "sources.json")
    market_config = read_json(ROOT / "config" / "markets.json")
    news = fetch_news(sources, start, end, warnings)
    markets = fetch_markets(market_config, start, end, warnings)
    macro = fetch_fred(os.environ.get("FRED_API_KEY"), start, end, warnings)
    if not os.environ.get("FRED_API_KEY"):
        warnings.append("未配置 FRED_API_KEY：本期不含 FRED 宏观序列；可选配置后启用。")
    report = {
        "id": week_id,
        "title": f"市场周报 · {start.isoformat()} — {end.isoformat()}",
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "generated_at": NOW.isoformat(),
        "status": "draft",
        "summary": "编辑填写：用 2–3 句描述本周市场主线、核心变化与反常信号，并注明数据截止时间。",
        "sections": {
            "drivers": [],
            "macro_commentary": [],
            "sector_commentary": [],
            "next_week_events": []
        },
        "markets": markets,
        "macro": macro,
        "news_candidates": news,
        "calendars": sources.get("calendars", []),
        "data_warnings": warnings,
        "editor_checklist": [
            "逐条打开新闻原文，核对标题、发布日期、事件内容及影响；排除重复和低价值条目。",
            "核对指数、利率、外汇和商品的单位、交易日期、时区与周度区间；Yahoo 行情为非官方来源。",
            "补写驱动因素时，把已确认事实与解释/观点分开，并给出来源链接。",
            "从官方发布日历核对下周关键事件的当地时间与北京时间，标明时间区间和不确定项。",
            "校验宏观数据发布日期、修订情况和同比/环比口径。",
            "确认数据警告已处理；添加风险说明后再把 status 改为 published。"
        ],
        "disclaimer": "本简报用于信息整理与研究参考，不构成投资建议。行情及宏观数据可能延迟、修订或存在覆盖缺口。"
    }
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", default="latest", help="latest or ISO week such as 2026-W45")
    parser.add_argument("--output", default=None, help="output JSON path; defaults to data/<week>.json")
    args = parser.parse_args()
    try:
        start, end = week_range(args.week)
        week_id = iso_week_id(end)
        output = Path(args.output) if args.output else ROOT / "data" / f"{week_id}.json"
        if not output.is_absolute():
            output = ROOT / output
        report = make_report(week_id, start, end)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WEEK_ID={week_id}")
        print(f"写入草稿：{output}")
        print(f"新闻候选：{len(report['news_candidates'])} 条；市场序列：{len(report['markets'])} 条；FRED 序列：{len(report['macro'])} 条")
        print(f"数据警告：{len(report['data_warnings'])} 条")
    except Exception as exc:
        print(f"生成失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

