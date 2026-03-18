# dud_news_aggregator

DIG-UP DATA コーポレートサイト向け ニュース自動取得システム。
Google News RSS + 直接RSSフィードから日本語ニュースを自動収集・整形する。

## 概要

- **目的**: コーポレートサイト（HOME画面）の「最新ニュース」セクションを自動更新し、手動運用コストをゼロにする
- **仕組み**: cron → Google News RSS / 直接RSS → 重複排除 → LLM整形 or キーワード分類 → JSON保存
- **実行頻度**: 1日1〜2回（cron）+ Claude Code `/fetch-news` で手動実行可能
- **検索ジャンル**: AI, Claude Code, 今井翔太（カンマ区切り）

## アーキテクチャ

```
fetch_news.py（エントリポイント）
    │
    ├── GoogleNewsSource   ← メイン: hl=ja&gl=JP で日本語ニュース確実
    ├── RssSource          ← 補完: ITmedia AI+, Publickey, GIGAZINE
    │
    ▼
ArticleDeduplicator        ← URL重複排除 + タイトル類似排除
    │
    ▼
NewsFormatter              ← OpenAI gpt-4o-mini or キーワード分類
    │
    ▼
NewsStorage                ← アトミック書込み + バックアップ
    │
    ▼
data/tech_news.json        ← 既存フォーマット互換
```

## dud_hp_ver2 との関係

### リポジトリ構成

| リポジトリ | 役割 | URL |
|-----------|------|-----|
| [dud_hp_ver2](https://github.com/yamaneko2023/dud_hp_ver2) | コーポレートサイト本体（PHP/CSS/JS） | https://github.com/yamaneko2023/dud_hp_ver2 |
| **dud_news_aggregator**（本リポジトリ） | ニュース取得バッチ | https://github.com/yamaneko2023/dud_news_aggregator |

### データ連携

```
dud_news_aggregator                          dud_hp_ver2
┌──────────────────────┐                    ┌──────────────────────────┐
│                      │                    │                          │
│  fetch_news.py       │   JSON出力         │  app/data/tech_news.json │
│  (cron / 手動実行)    │ ──────────────→    │         ↓                │
│                      │                    │  PageController.php      │
│  Google News RSS     │                    │         ↓                │
│  + 直接RSS取得       │                    │  home.php (データ埋込)    │
│  → 重複排除          │                    │         ↓                │
│  → LLM整形/分類      │                    │  home.js (DOM描画)       │
│  → JSON保存          │                    │                          │
└──────────────────────┘                    └──────────────────────────┘
```

### JSONフォーマット（tech_news.json）

```json
{
  "fetched_at": "2026-03-17 09:00:00",
  "count": 10,
  "items": [
    {
      "id": 1,
      "date": "2026-03-17",
      "category": "AI",
      "title": "ニュースタイトル",
      "link": "https://example.com/article",
      "source": "ニュースソース名",
      "type": "article",
      "auto_generated": true
    }
  ]
}
```

## ディレクトリ構成

```
dud_news_aggregator/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── .gitignore
├── scripts/
│   ├── fetch_news.py             # メインスクリプト（v3パイプライン）
│   └── optimize_keywords.py      # キーワード最適化スクリプト
├── config/
│   ├── __init__.py
│   ├── config.py                 # 設定ファイル（.gitignore対象）
│   └── config.py.example         # テンプレート
├── src/
│   ├── __init__.py
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py               # 基底クラス + データモデル + parse_feed_date
│   │   ├── google_news.py        # Google News RSS
│   │   └── rss_source.py         # 直接RSSフィード
│   ├── query_builder.py          # ジャンル複合クエリ生成
│   ├── content_filter.py         # 3段ノイズフィルタ
│   ├── llm_filter.py             # LLMバッチ関連度判定
│   ├── formatter.py              # LLM整形 / キーワード分類
│   ├── dedup.py                  # 重複排除 + ランキング
│   ├── validator.py              # 出力バリデーション
│   ├── storage.py                # JSON保存
│   └── keyword_optimizer/        # キーワード最適化サブモジュール
│       ├── config_writer.py      # config.py 書き換え
│       ├── cooccurrence.py       # 共起語分析
│       ├── hatena_collector.py   # はてなブックマーク収集
│       └── merger.py             # 候補マージ
├── tests/
│   ├── test_query_builder.py
│   ├── test_content_filter.py
│   ├── test_llm_filter.py
│   ├── test_mix_ratio.py
│   ├── test_google_news.py
│   ├── test_dedup.py
│   ├── test_validator.py
│   ├── test_config_writer.py
│   ├── test_cooccurrence.py
│   ├── test_hatena_collector.py
│   ├── test_merger.py
│   └── fixtures/
├── data/                         # JSON出力先
└── logs/                         # 実行ログ
```

## 技術スタック

- **Python 3.12+**
- **feedparser** - RSS/Atomフィードのパース
- **openai** - gpt-4o-mini によるニュース整形（オプション）
- **pytest** - テスト

## セットアップ

```bash
# 1. 依存インストール
pip install -r requirements.txt

# 2. 設定ファイル作成
cp config/config.py.example config/config.py
# config.py を編集（LLM使用時は LLM_API_KEY を設定）

# 3. 動作確認（LLMなし・保存なし）
python scripts/fetch_news.py --dry-run --no-llm

# 4. 本番実行
python scripts/fetch_news.py

# 5. cron登録
# 0 9,18 * * * /usr/bin/python3 /path/to/scripts/fetch_news.py >> /path/to/logs/news_fetch.log 2>&1
```

## 使い方

```bash
# 通常実行
python scripts/fetch_news.py

# 取得のみ（保存しない）
python scripts/fetch_news.py --dry-run

# LLMなし（キーワードベース分類）
python scripts/fetch_news.py --no-llm

# Google Newsのみ
python scripts/fetch_news.py --source google

# キーワード最適化（候補表示のみ）
python scripts/optimize_keywords.py

# キーワード最適化（config.py自動更新）
python scripts/optimize_keywords.py --apply

# テスト実行
python -m pytest tests/ -v
```

## 関連ドキュメント

- [dud_hp_ver2](https://github.com/yamaneko2023/dud_hp_ver2) - HP側のニュースデータ仕様
