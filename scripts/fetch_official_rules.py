#!/usr/bin/env python3
"""抓取小红书官方《社区规范》原文，检测是否有更新。

用法：
    python -I scripts/fetch_official_rules.py            # 检查更新
    python -I scripts/fetch_official_rules.py --update   # 更新本地快照

退出码：0 = 成功（无论有无更新）；1 = 抓取或解析失败。
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

URL = "https://pages.xiaohongshu.com/data/community_rule"
ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "references" / "official-community-rules.md"
META = ROOT / "references" / ".rules-meta.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"


def fetch():
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
    doc = json.loads(raw.decode("utf-8"))
    if doc.get("code") != 0:
        raise RuntimeError(f"接口返回 code={doc.get('code')} message={doc.get('message')}")
    data = doc.get("data")
    if not isinstance(data, dict) or not data.get("data"):
        raise RuntimeError("接口返回缺少 data.data 结构")
    return data


def walk(node, depth, out):
    if isinstance(node, dict):
        name = node.get("name")
        if isinstance(name, str):
            out.append("  " * depth + ("### " if depth else "## ") + name)
        desc = node.get("description")
        if isinstance(desc, str):
            out.append("  " * depth + "> " + desc)
        content = node.get("content")
        if isinstance(content, str):
            out.append("  " * depth + "- " + content)
        for key in ("list", "listItem"):
            for child in node.get(key) or []:
                walk(child, depth + 1, out)
    elif isinstance(node, list):
        for child in node:
            walk(child, depth, out)


def render(data):
    lines = []
    preface = data.get("preface")
    if isinstance(preface, str):
        lines += ["> " + preface, ""]
    for section in data["data"]:
        walk(section, 0, lines)
        lines.append("")
    body = "\n".join(lines).strip() + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    header = (
        "# 小红书官方《社区规范》原文\n\n"
        f"> 来源：{URL}\n"
        f"> 抓取时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"> 内容哈希：{digest[:16]}\n"
        "> 本文件由 `scripts/fetch_official_rules.py --update` 生成，人工改动会在下次更新时被覆盖。\n\n"
    )
    return header + body, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="写入本地快照")
    args = parser.parse_args()

    try:
        data = fetch()
    except Exception as exc:  # 网络或结构异常必须暴露，不降级
        print(f"FETCH_FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    text, digest = render(data)
    old = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not old:
        print("STATUS: FIRST_RUN（本地无快照）")
    elif old.get("hash") == digest:
        print(f"STATUS: UNCHANGED（官方版本未变，上次抓取 {old.get('fetched_at')}）")
        META.write_text(json.dumps({"hash": digest, "fetched_at": now, "url": URL},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        return 0
    else:
        print(f"STATUS: CHANGED（官方内容已变化，上次 {old.get('fetched_at')}）")
        print(f"  旧哈希 {old.get('hash', '')[:16]} → 新哈希 {digest[:16]}")

    if args.update or not old:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(text, encoding="utf-8")
        META.write_text(json.dumps({"hash": digest, "fetched_at": now, "url": URL},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WROTE: {SNAPSHOT}  ({len(text)} chars)")
    else:
        print(f"  未写入。确认要更新时运行：python -I {Path(__file__).name} --update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
