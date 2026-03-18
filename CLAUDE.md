# CLAUDE.md

## Project Overview

DIG-UP DATA コーポレートサイト（dud_hp_ver2）向けのニュース自動取得バッチシステム。
Google News RSS（メイン）+ 直接RSS（補完）で日本語ニュースを収集し、
LLM整形（またはキーワードベース簡易分類）でJSONを生成する。

## dud_hp_ver2 との関係

| リポジトリ | 役割 |
|-----------|------|
| `dud_hp_ver2` | コーポレートサイト本体（PHP/CSS/JS）。HOME画面でニュースを表示する側 |
| `dud_news_aggregator`（本リポ） | ニュース取得バッチ。JSONを生成して `dud_hp_ver2` に渡す側 |

### データフロー（v3パイプライン）

```
[本リポ] fetch_news.py
    ├── build_queries()     ← ジャンル複合クエリ生成（NEWS_SEARCH_CONFIGS）
    ├── GoogleNewsSource    → fetch_by_queries() でWEB+YouTube取得
    ├── RssSource           → ITmedia, Publickey, GIGAZINE 等
    ↓ ContentFilter         ← ノイズパターン/ドメインBL/テック共起語
    ↓ 重複排除 + ランキング
    ↓ LLMFilter             ← gpt-4o-mini バッチ関連度判定（オプション）
    ↓ MixRatio              ← WEB:YouTube = 7:3 の割合制御
    ↓ LLM整形 or キーワード分類
    ↓ JSON出力
[dud_hp_ver2] app/data/tech_news.json → PageController → home.php → home.js
```

### dud_hp_ver2 側で必要な変更

本リポのバッチが動いた後、HP側で以下を有効化する必要がある:
- `PageController.php`: tech_news.json 読み込み復活
- `home.php`: `const latestNews = [];` → JSONデータ埋め込みに復元

## Architecture

- **Google News RSS**: `hl=ja&gl=JP` で日本語ニュースを確実に取得（メインソース）
- **直接RSS**: ITmedia AI+, Publickey, GIGAZINE 等のテック系フィード（補完ソース）
- **ジャンル複合クエリ**: 「テクノロジー AI -ラブライブ」形式でノイズ低減
- **3段コンテンツフィルタ**: ノイズパターン除外 → ドメインBL → テック共起語チェック
- **LLMフィルタ**: gpt-4o-mini でバッチ関連度判定（fail-open）
- **WEB:YouTube割合制御**: 設定比率（デフォルト7:3）で混合
- **OpenAI gpt-4o-mini**: JSON mode で翻訳・要約・カテゴリ分類（オプション）
- **キーワード分類**: LLM不要時のフォールバック
- **Python**: モジュラー設計（sources/, dedup, formatter, validator, storage）
- **cron**: 1日1〜2回実行

## Directory Structure

```
dud_news_aggregator/
├── CLAUDE.md
├── README.md
├── requirements.txt              # feedparser, requests, openai
├── scripts/
│   ├── fetch_news.py             # メインエントリポイント（v3パイプライン）
│   └── optimize_keywords.py      # キーワード最適化スクリプト
├── config/
│   ├── __init__.py
│   ├── config.py                 # 設定ファイル（.gitignore対象）
│   └── config.py.example         # テンプレート
├── src/                          # モジュール群
│   ├── __init__.py
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py               # NewsSource基底 + RawArticle + parse_feed_date
│   │   ├── google_news.py        # Google News RSSソース（fetch_by_queries対応）
│   │   └── rss_source.py         # 直接RSSフィードソース
│   ├── query_builder.py          # ジャンル複合クエリ生成
│   ├── content_filter.py         # 3段ノイズフィルタ
│   ├── llm_filter.py             # LLMバッチ関連度判定
│   ├── formatter.py              # LLM整形 + キーワード分類
│   ├── dedup.py                  # 重複排除 + ランキング
│   ├── validator.py              # 出力JSONバリデーション
│   ├── storage.py                # バックアップ + アトミック保存
│   └── keyword_optimizer/        # キーワード最適化サブモジュール
│       ├── __init__.py
│       ├── config_writer.py      # config.py 書き換え
│       ├── cooccurrence.py       # 共起語分析
│       ├── hatena_collector.py   # はてなブックマーク収集
│       └── merger.py             # 候補マージ
├── tests/
│   ├── __init__.py
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
│       └── google_news_sample.xml
├── data/                         # JSON出力先
└── logs/                         # 実行ログ
```

## Output JSON Format

`tech_news.json` のフォーマット（ラッパーオブジェクト形式）:

```json
{
  "fetched_at": "2026-03-17 09:00:00",
  "count": 10,
  "items": [
    {
      "id": 1,
      "date": "YYYY-MM-DD",
      "category": "AI | DX | データ | テクノロジー",
      "title": "日本語のニュースタイトル",
      "link": "https://example.com/article",
      "source": "ニュースソース名",
      "type": "article | youtube",
      "auto_generated": true
    }
  ]
}
```

## Key Configuration

```python
# 検索設定（ジャンル複合クエリ）
NEWS_SEARCH_CONFIGS = [
    {
        "genre": "テクノロジー",
        "keywords": ["AI", "人工知能"],
        "synonyms": ["生成AI", "機械学習", "LLM"],
        "exclude": ["ラブライブ", "踊ってみた", "歌ってみた", "アイドル"],
        "youtube": True,
    },
    ...
]

# WEB:YouTube 表示割合
OUTPUT_WEB_RATIO = 7
OUTPUT_YT_RATIO = 3

# コンテンツフィルタ
CONTENT_FILTER_ENABLED = True

# ソース設定
GOOGLE_NEWS_ENABLED = True
GOOGLE_NEWS_MAX_PER_GENRE = 5
RSS_FEEDS = [...]

# LLM設定
LLM_PROVIDER = "openai"  # or "none"
LLM_API_KEY = "sk-..."
LLM_MODEL = "gpt-4o-mini"

# ニュース設定
NEWS_MAX_ITEMS = 10
NEWS_DAYS = 7

# 旧設定（後方互換: NEWS_SEARCH_CONFIGS 未定義時のフォールバック）
NEWS_GENRES = "AI,Claude Code,今井翔太"
```

## Usage

```bash
python scripts/fetch_news.py               # 通常実行
python scripts/fetch_news.py --dry-run      # 取得のみ、保存しない
python scripts/fetch_news.py --no-llm       # LLMなしフォールバック
python scripts/fetch_news.py --source google  # Google Newsのみ
python scripts/fetch_news.py --source rss     # 直接RSSのみ
```

## Security

- **コミット禁止**: APIキー、トークン（config.py は .gitignore に含める）
- config.py.example をテンプレートとして管理する

## Related Resources

- HP側リポ: https://github.com/yamaneko2023/dud_hp_ver2
