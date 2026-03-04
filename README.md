# dud_news_aggregator

DIG-UP DATA コーポレートサイト向け ニュース自動取得システム。
Dify Cloud + Tavily API を使い、指定ジャンルの最新ニュースを自動収集・整形する。

## 概要

- **目的**: コーポレートサイト（HOME画面）の「最新ニュース」セクションを自動更新し、手動運用コストをゼロにする
- **仕組み**: cron → Dify Advanced Chat API → Tavily検索 → LLM整形 → JSON保存
- **実行頻度**: 1日1〜2回（cron）+ Claude Code `/fetch-news` で手動実行可能
- **検索ジャンル**: AI, Claude Code, 今井翔太（カンマ区切りで送信）

## dud_hp_ver2 との関係

### リポジトリ構成

| リポジトリ | 役割 | URL |
|-----------|------|-----|
| [dud_hp_ver2](https://github.com/yamaneko2023/dud_hp_ver2) | コーポレートサイト本体（PHP/CSS/JS） | https://github.com/yamaneko2023/dud_hp_ver2 |
| **dud_news_aggregator**（本リポジトリ） | ニュース取得バッチ + Difyワークフロー設計 | https://github.com/yamaneko2023/dud_news_aggregator |

### データ連携

```
dud_news_aggregator                          dud_hp_ver2
┌──────────────────────┐                    ┌──────────────────────────┐
│                      │                    │                          │
│  fetch_news.py       │   JSON出力         │  app/data/tech_news.json │
│  (cron / 手動実行)    │ ──────────────→    │         ↓                │
│                      │                    │  PageController.php      │
│  Dify Chat API呼出し │                    │         ↓                │
│  → Tavily検索        │                    │  home.php (データ埋込)    │
│  → LLM整形           │                    │         ↓                │
│  → JSON保存          │                    │  home.js (DOM描画)       │
│                      │                    │                          │
└──────────────────────┘                    └──────────────────────────┘
```

### 連携ポイント

1. **出力先**: 本リポジトリの `fetch_news.py` が生成する `data/tech_news.json` を `dud_hp_ver2/app/data/tech_news.json` に配置する
2. **データフォーマット**: `dud_hp_ver2` の `home.js` が期待するJSON形式に合わせて出力する
3. **dud_hp_ver2 側の変更**: ニュース表示を有効化するために以下の修正が必要
   - `PageController.php`: `tech_news.json` の読み込み復活
   - `home.php`: `const latestNews = [];` → JSON埋め込みに復元

### JSONフォーマット（tech_news.json）

```json
[
  {
    "id": 1,
    "date": "2026-03-03",
    "category": "AI",
    "title": "ニュースタイトル",
    "link": "https://example.com/article",
    "source": "ニュースソース名",
    "type": "article",
    "auto_generated": true
  }
]
```

## ディレクトリ構成

```
dud_news_aggregator/
├── README.md                    # 本ファイル
├── CLAUDE.md                    # Claude Code プロジェクト設定
├── .gitignore
├── docs/
│   └── news-system-design.html  # 詳細設計書（ブラウザで閲覧可能）
├── scripts/
│   └── fetch_news.py            # cron実行スクリプト（Python）
├── config/
│   ├── __init__.py
│   ├── config.py                # API設定（.gitignore対象）
│   └── config.py.example        # 設定ファイルテンプレート
├── data/                        # JSON出力先
│   └── .gitkeep
└── logs/                        # 実行ログ
    └── .gitkeep
```

## 技術スタック

- **Python 3** - cronスクリプト（標準ライブラリのみ、外部依存なし）
- **Dify Cloud** (udify.app) - ワークフローエンジン（Advanced Chat API）
- **Tavily API** - ニュース検索
- **LLM** (gpt-4o-mini / Claude Sonnet) - 記事の整形・翻訳（Dify内で使用）

## セットアップ

詳細は [設計書](docs/news-system-design.html) を参照。

1. Dify Cloud でワークフローを構築
2. Tavily APIキーを取得
3. `cp config/config.py.example config/config.py` で設定ファイルを作成し、APIキーを設定
4. `python3 scripts/fetch_news.py` で動作確認
5. cron登録

## 関連ドキュメント

- [詳細設計書](docs/news-system-design.html) - アーキテクチャ、Difyノード設計、Python実装、コスト見積もり
- [dud_hp_ver2 CLAUDE.md](https://github.com/yamaneko2023/dud_hp_ver2/blob/main/CLAUDE.md) - HP側のニュースデータ仕様
