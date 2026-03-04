# CLAUDE.md

## Project Overview

DIG-UP DATA コーポレートサイト（dud_hp_ver2）向けのニュース自動取得バッチシステム。
Dify Cloud + Tavily API で最新ニュースを収集し、コーポレートサイトのHOME画面に表示するJSONを生成する。

## dud_hp_ver2 との関係

| リポジトリ | 役割 |
|-----------|------|
| `dud_hp_ver2` | コーポレートサイト本体（PHP/CSS/JS）。HOME画面でニュースを表示する側 |
| `dud_news_aggregator`（本リポ） | ニュース取得バッチ。JSONを生成して `dud_hp_ver2` に渡す側 |

### データフロー

```
[本リポ] fetch_news.php → Dify API → Tavily検索 → LLM整形
    ↓ JSON出力
[dud_hp_ver2] app/data/tech_news.json → PageController → home.php → home.js
```

### dud_hp_ver2 側で必要な変更

本リポのバッチが動いた後、HP側で以下を有効化する必要がある:
- `PageController.php`: tech_news.json 読み込み復活
- `home.php`: `const latestNews = [];` → JSONデータ埋め込みに復元

## Architecture

- **Dify Cloud** (udify.app): ワークフローエンジン。Tavilyツール + LLMで検索・整形
- **Tavily API**: ニュース特化の検索API（topic: "news", days: 7）
- **PHP**: cronスクリプト（Dify API呼出し → JSON保存）
- **cron**: 1日1〜2回実行

## Directory Structure

```
dud_news_aggregator/
├── CLAUDE.md
├── README.md
├── docs/
│   └── news-system-design.html  # 詳細設計書
├── scripts/
│   └── fetch_news.php           # cronスクリプト
├── config/
│   └── config.php               # API設定（APIキー等）
└── logs/                        # 実行ログ
```

## Output JSON Format

`tech_news.json` のフォーマット（dud_hp_ver2 の home.js が期待する形式）:

```json
[
  {
    "id": 1,
    "date": "YYYY-MM-DD",
    "category": "AI | DX | データ | テクノロジー",
    "title": "日本語のニュースタイトル（50文字以内）",
    "link": "https://example.com/article",
    "source": "ニュースソース名",
    "type": "article | youtube",
    "auto_generated": true
  }
]
```

## Key Configuration

```php
DIFY_API_URL   = 'https://api.dify.ai/v1/workflows/run'
DIFY_API_KEY   = 'app-xxxxxxxx'  // Dify Cloudで発行
NEWS_GENRES    = 'AI,Claude Code,今井翔太'
NEWS_MAX_ITEMS = 10
```

## Security

- **コミット禁止**: APIキー、トークン（config.php は .gitignore に含める）
- config.php.example をテンプレートとして管理する

## Related Resources

- 詳細設計書: `docs/news-system-design.html`
- HP側リポ: https://github.com/yamaneko2023/dud_hp_ver2
- Dify Cloud: https://udify.app
- Tavily API: https://tavily.com
