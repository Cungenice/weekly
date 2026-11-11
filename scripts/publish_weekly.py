#!/usr/bin/env python3
"""Validate and publish an edited weekly report into the static site."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish an edited weekly brief and update the issue manifest")
    parser.add_argument("input", help="reviewed JSON file, usually data/draft.json")
    args = parser.parse_args()
    source = Path(args.input)
    if not source.is_absolute():
        source = ROOT / source
    report = json.loads(source.read_text(encoding="utf-8"))

    if report.get("status") != "published":
        raise SystemExit("拒绝发布：请先在 JSON 中将 status 改为 published。")
    summary = (report.get("summary") or "").strip()
    if not summary or "编辑填写" in summary or "待补充" in summary:
        raise SystemExit("拒绝发布：请先补全本周结论。")

    start = dt.date.fromisoformat(report["week_start"])
    end = dt.date.fromisoformat(report["week_end"])
    year, week, _ = end.isocalendar()
    expected_id = f"{year}-W{week:02d}"
    if start.weekday() != 0 or end.weekday() != 4 or (end - start).days != 4 or report.get("id") != expected_id:
        raise SystemExit("拒绝发布：期号或日期范围不匹配。需要周一至周五，期号格式为 YYYY-Www。")

    target = ROOT / "data" / f"{expected_id}.json"
    manifest_path = ROOT / "data" / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        manifest = []
    if not isinstance(manifest, list):
        raise SystemExit("manifest.json 格式错误：应为周报 ID 数组。")
    manifest = sorted(set(manifest + [expected_id]), reverse=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已发布数据：{target}")
    print(f"已更新目录：{manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

