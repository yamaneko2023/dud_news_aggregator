#!/usr/bin/env python3
"""
ニュース自動取得スクリプト（cron実行用）

Dify Advanced Chat API経由でTavilyニュースを取得し、JSONに保存する。
エラー時は既存データを上書きしない安全設計。

Usage:
    python scripts/fetch_news.py

cron例:
    0 9,18 * * * /usr/bin/python3 /path/to/scripts/fetch_news.py >> /path/to/logs/news_fetch.log 2>&1
"""

import json
import os
import shutil
import sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# config読み込み
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from config.config import (
    DIFY_API_URL,
    DIFY_API_KEY,
    NEWS_GENRES,
    NEWS_MAX_ITEMS,
    NEWS_FETCH_TIMEOUT,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TARGET_FILE = os.path.join(DATA_DIR, "tech_news.json")


def log(message: str) -> None:
    """タイムスタンプ付きログ出力"""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}", flush=True)


def fetch_from_dify() -> str:
    """Dify Advanced Chat APIを呼び出してニュースを取得"""
    payload = json.dumps({
        "inputs": {},
        "query": NEWS_GENRES,
        "response_mode": "blocking",
        "conversation_id": "",
        "user": "hp-news-fetcher",
    }).encode("utf-8")

    req = Request(
        DIFY_API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "User-Agent": "DUD-NewsAggregator/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=NEWS_FETCH_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
    except HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")[:200]
        raise RuntimeError(f"Dify API error: HTTP {e.code} - {error_body}")
    except URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}")

    data = json.loads(body)

    answer = data.get("answer")
    if not answer:
        raise RuntimeError(f"No answer in Dify response: {json.dumps(data, ensure_ascii=False)[:300]}")

    return answer


def validate_news(raw_answer: str) -> list:
    """LLM応答からJSON配列を抽出・バリデーション"""
    # LLMがマークダウンコードブロックで囲む場合に対応
    text = raw_answer.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 先頭の ```json や ``` を除去
        lines = lines[1:]
        # 末尾の ``` を除去
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)

    news = json.loads(text)

    if not isinstance(news, list) or len(news) == 0:
        raise RuntimeError("Result is not a valid JSON array or is empty")

    required = ["id", "date", "category", "title", "link"]
    first = news[0]
    for field in required:
        if field not in first:
            raise RuntimeError(f"Missing required field: {field}")

    return news


def backup_existing() -> None:
    """既存ファイルを日時付きでバックアップ"""
    if not os.path.exists(TARGET_FILE):
        return

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_file = os.path.join(DATA_DIR, f"tech_news_{timestamp}.json")

    shutil.copy2(TARGET_FILE, backup_file)
    log(f"Backup: {backup_file}")


def save_json(news: list) -> None:
    """JSONをアトミックに書き込む"""
    items = news[:NEWS_MAX_ITEMS]
    json_str = json.dumps(items, ensure_ascii=False, indent=2)

    tmp_file = TARGET_FILE + ".tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(json_str + "\n")
        os.replace(tmp_file, TARGET_FILE)
    except Exception:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
        raise


def main():
    try:
        log(f"Start: genres={NEWS_GENRES}")

        # 1. Dify APIからニュース取得
        answer = fetch_from_dify()
        log("Dify API response received")

        # 2. バリデーション
        news = validate_news(answer)
        log(f"Validated: {len(news)} articles")

        # 3. 既存ファイルのバックアップ
        backup_existing()

        # 4. JSON保存（アトミック書き込み）
        save_json(news)
        saved_count = min(len(news), NEWS_MAX_ITEMS)
        log(f"OK: {saved_count} articles saved to {TARGET_FILE}")

    except Exception as e:
        log(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
