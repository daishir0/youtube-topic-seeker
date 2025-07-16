# YouTube Topic Seeker

## Overview
YouTube Topic Seeker is a comprehensive system for searching topics across YouTube videos. It allows you to find exactly where specific topics are discussed in videos, providing timestamps and summaries. The system works in three phases:

1. **Phase 1: Data Download** - Downloads video metadata and transcripts from YouTube channels or individual videos
2. **Phase 2: Transcript Enhancement** - Improves transcript quality using AI
3. **Phase 3: Vector Store Building** - Creates searchable vector databases for semantic search across videos

Perfect for researchers, content creators, or anyone who needs to find specific information across multiple YouTube videos quickly.

## Key Features

### 🎯 Dual URL Support
- **Channel URLs**: Process entire channels (e.g., `https://www.youtube.com/@channel_name`)
- **Video URLs**: Process individual videos (e.g., `https://www.youtube.com/watch?v=VIDEO_ID`)
- **Mixed Processing**: First URL determines the mode - channel or video processing
- **Automatic Channel Detection**: Individual videos automatically detect and register their parent channel

### 🔍 Advanced Search Capabilities
- **Timestamp-Precise Results**: Direct links to exact moments in videos
- **Multi-Channel Search**: Search across all processed channels simultaneously
- **Channel-Specific Search**: Focus search on specific channels
- **AI-Powered Summaries**: Contextual topic summaries for each result
- **Relevance Scoring**: Results ranked by semantic similarity

### 🏗️ Scalable Architecture
- **Multi-Channel Support**: Process and manage multiple YouTube channels
- **Channel-Specific Vector Stores**: Optimized storage and retrieval per channel
- **Incremental Processing**: Only process new content, avoiding duplicates
- **Batch Processing**: Efficient handling of large video collections

## Installation

### Prerequisites
- Python 3.11 or higher
- Conda environment (recommended)
- OpenAI API key

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/daishir0/youtube-topic-seeker.git
   cd youtube-topic-seeker
   ```

2. Create and activate a conda environment:
   ```bash
   conda create -n topic-seeker python=3.11
   conda activate topic-seeker
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Copy the sample configuration file and edit it:
   ```bash
   cp config.yaml.sample config.yaml
   ```

5. Add your OpenAI API key to the config.yaml file:
   ```yaml
   openai:
     api_key: "your-api-key-here"
   ```

## Usage

### Interactive Mode
Run the application in interactive mode:
```bash
python main.py
```

This will present a menu with options to:
- **Phase 1**: Download YouTube Data (channels or videos)
- **Phase 2**: Enhance Transcripts with AI
- **Phase 3**: Build Vector Store (all channels or specific channel)
- **Search Topics**: Unified search across all channels or channel-specific search
- **Channel Management**: Add, remove, and configure channels
- **Date Filter Settings**: Control processing timeframes

### Automatic Mode

#### Channel Processing
Process one or multiple YouTube channels automatically:
```bash
# Single channel
python main.py https://www.youtube.com/@channel_name

# Multiple channels
python main.py https://www.youtube.com/@channel1 https://www.youtube.com/@channel2
```

#### Video Processing
Process individual videos:
```bash
# Single video
python main.py https://www.youtube.com/watch?v=VIDEO_ID

# Multiple videos
python main.py https://www.youtube.com/watch?v=VIDEO1 https://www.youtube.com/watch?v=VIDEO2

# Mixed URLs (first URL determines mode)
python main.py https://www.youtube.com/@channel https://www.youtube.com/watch?v=VIDEO_ID
# ^ This will process as channel mode (first URL is channel)
```

### Phase 3: Vector Store Building Options

When building vector stores, you have three options:

1. **Build for all channels** - Creates separate vector stores for each channel
2. **Build for specific channel** - Creates vector store for selected channel only
3. **Cancel** - Skip vector store building

### Search Examples
After processing videos, you can search for topics:
- "AI ethics in modern technology"
- "Climate change solutions"
- "Financial investment strategies"
- "政治改革について" (Japanese queries supported)

The system will return relevant results with:
- Video title and channel information
- AI-generated topic summary
- Timestamp link to the exact moment
- Relevance score (0-100%)
- Content preview

### Channel Management
The system maintains a `channels.json` file that tracks:
- Channel information (name, ID, URL)
- Processing status and video counts
- Enable/disable status for search operations
- Last update timestamps

## Configuration

### Key Configuration Options

```yaml
# Phase 1: Data Download
phase1:
  date_filter:
    enabled: true
    mode: "recent"  # "recent", "since", "all"
    default_months: 6
  output_dir: "./data/1-plain"

# Phase 2: Transcript Enhancement
phase2:
  input_dir: "./data/1-plain"
  output_dir: "./data/2-target"
  batch_size: 5
  skip_existing: true

# Phase 3: Vector Store
rag:
  input_dir: "./data/2-target"
  vectorstore_dir: "./data/vectorstore"
  chunk_size: 500
  chunk_overlap: 100
  similarity_threshold: 0.7

# Multi-Channel Support
channels:
  management_file: "./data/channels.json"
  unified_search:
    enabled: true
    default_scope: "all"
```

## Directory Structure

```
project/
├── data/
│   ├── 1-plain/           # Phase 1 output (raw data)
│   │   ├── channel_1/     # Channel-specific directories
│   │   └── channel_2/
│   ├── 2-target/          # Phase 2 output (enhanced transcripts)
│   │   ├── channel_1/
│   │   └── channel_2/
│   ├── vectorstore/       # Phase 3 output (vector databases)
│   │   ├── channel_1/     # Channel-specific vector stores
│   │   └── channel_2/
│   └── channels.json      # Channel management file
├── src/                   # Source code
├── logs/                  # Application logs
└── config.yaml           # Configuration file
```

## Advanced Features

### URL Classification System
- Automatic detection of channel vs video URLs
- Support for various YouTube URL formats:
  - `youtube.com/channel/UC...`
  - `youtube.com/@channelname`
  - `youtube.com/c/channelname`
  - `youtube.com/watch?v=...`
  - `youtu.be/VIDEO_ID`
  - `youtube.com/shorts/VIDEO_ID`

### Data Consistency
- Automatic channel registration from individual videos
- Cross-phase data integrity validation
- Orphaned data detection and cleanup
- Incremental processing with duplicate detection

### Performance Optimization
- Batch processing for large datasets
- Token limit handling for OpenAI API
- Efficient vector store management
- Configurable chunk sizes and overlaps

## Troubleshooting

### Common Issues

1. **"No enhanced transcripts found"** - Ensure Phase 2 has been completed successfully
2. **OpenAI API timeouts** - Reduce batch_size in config.yaml
3. **Vector store build failures** - Use channel-specific building instead of unified mode
4. **URL processing errors** - Verify URL format and accessibility

### Performance Tips
- Process channels separately for better stability
- Use incremental mode for regular updates
- Monitor OpenAI API usage and adjust batch sizes
- Clean up orphaned data periodically

## Notes
- The system requires an OpenAI API key for transcript enhancement and search functionality
- Processing large channels may take significant time and API usage
- For optimal performance, ensure your config.yaml settings are tuned for your needs
- The system supports multiple languages, with priority given to Japanese and English
- Proxy support is available for network-restricted environments
- Individual video processing automatically detects and registers parent channels

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# YouTube Topic Seeker (日本語版)

## 概要
YouTube Topic Seekerは、YouTube動画全体からトピックを検索するための総合システムです。特定のトピックがどの動画のどの時間に話されているかを正確に見つけ出し、タイムスタンプと要約を提供します。システムは3つのフェーズで動作します：

1. **フェーズ1：データダウンロード** - YouTubeチャンネルや個別動画からメタデータとトランスクリプトをダウンロード
2. **フェーズ2：トランスクリプト強化** - AIを使用してトランスクリプトの品質を向上
3. **フェーズ3：ベクトルストア構築** - 動画全体のセマンティック検索を可能にする検索可能なベクトルデータベースを作成

研究者、コンテンツクリエイター、または複数のYouTube動画から特定の情報を素早く見つける必要がある方に最適です。

## 主要機能

### 🎯 デュアルURL対応
- **チャンネルURL**: チャンネル全体を処理 (例: `https://www.youtube.com/@チャンネル名`)
- **動画URL**: 個別動画を処理 (例: `https://www.youtube.com/watch?v=VIDEO_ID`)
- **混合処理**: 最初のURLが処理モードを決定（チャンネルまたは動画処理）
- **自動チャンネル検出**: 個別動画から自動的に親チャンネルを検出・登録

### 🔍 高度な検索機能
- **タイムスタンプ精密結果**: 動画内の正確な瞬間への直接リンク
- **マルチチャンネル検索**: 処理済みの全チャンネルを同時に検索
- **チャンネル特化検索**: 特定のチャンネルに絞った検索
- **AI生成要約**: 各結果に対する文脈的トピック要約
- **関連度スコア**: セマンティック類似度によるランキング

### 🏗️ スケーラブルアーキテクチャ
- **マルチチャンネル対応**: 複数のYouTubeチャンネルを処理・管理
- **チャンネル専用ベクトルストア**: チャンネルごとに最適化されたストレージと検索
- **増分処理**: 新しいコンテンツのみを処理し、重複を回避
- **バッチ処理**: 大量の動画コレクションを効率的に処理

## インストール方法

### 前提条件
- Python 3.11以上
- Conda環境（推奨）
- OpenAI APIキー

### 手順
1. リポジトリをクローンします：
   ```bash
   git clone https://github.com/daishir0/youtube-topic-seeker.git
   cd youtube-topic-seeker
   ```

2. Conda環境を作成して有効化します：
   ```bash
   conda create -n topic-seeker python=3.11
   conda activate topic-seeker
   ```

3. 依存関係をインストールします：
   ```bash
   pip install -r requirements.txt
   ```

4. サンプル設定ファイルをコピーして編集します：
   ```bash
   cp config.yaml.sample config.yaml
   ```

5. config.yamlファイルにOpenAI APIキーを追加します：
   ```yaml
   openai:
     api_key: "あなたのAPIキーをここに入力"
   ```

## 使い方

### 対話モード
アプリケーションを対話モードで実行します：
```bash
python main.py
```

これにより、以下のオプションを含むメニューが表示されます：
- **フェーズ1**: YouTubeデータのダウンロード（チャンネルまたは動画）
- **フェーズ2**: AIによるトランスクリプト強化
- **フェーズ3**: ベクトルストアの構築（全チャンネルまたは特定チャンネル）
- **トピック検索**: 全チャンネル統合検索またはチャンネル特化検索
- **チャンネル管理**: チャンネルの追加、削除、設定
- **日付フィルター設定**: 処理期間の制御

### 自動モード

#### チャンネル処理
単一または複数のYouTubeチャンネルを自動的に処理します：
```bash
# 単一チャンネル
python main.py https://www.youtube.com/@チャンネル名

# 複数チャンネル
python main.py https://www.youtube.com/@チャンネル1 https://www.youtube.com/@チャンネル2
```

#### 動画処理
個別動画を処理します：
```bash
# 単一動画
python main.py https://www.youtube.com/watch?v=VIDEO_ID

# 複数動画
python main.py https://www.youtube.com/watch?v=VIDEO1 https://www.youtube.com/watch?v=VIDEO2

# 混合URL（最初のURLがモードを決定）
python main.py https://www.youtube.com/@チャンネル https://www.youtube.com/watch?v=VIDEO_ID
# ^ これはチャンネルモードで処理されます（最初のURLがチャンネル）
```

### フェーズ3: ベクトルストア構築オプション

ベクトルストアを構築する際、3つのオプションがあります：

1. **全チャンネル向け構築** - 各チャンネルに個別のベクトルストアを作成
2. **特定チャンネル向け構築** - 選択したチャンネルのみのベクトルストアを作成
3. **キャンセル** - ベクトルストア構築をスキップ

### 検索例
動画を処理した後、トピックを検索できます：
- 「現代技術におけるAI倫理」
- 「気候変動の解決策」
- 「金融投資戦略」
- 「政治改革について」

システムは以下を含む関連結果を返します：
- 動画タイトルとチャンネル情報
- AI生成トピック要約
- 正確な瞬間へのタイムスタンプリンク
- 関連度スコア（0-100%）
- コンテンツプレビュー

### チャンネル管理
システムは以下を追跡する `channels.json` ファイルを維持します：
- チャンネル情報（名前、ID、URL）
- 処理ステータスと動画数
- 検索操作の有効/無効ステータス
- 最終更新タイムスタンプ

## 高度な機能

### URL分類システム
- チャンネルvs動画URLの自動検出
- 様々なYouTube URLフォーマットをサポート：
  - `youtube.com/channel/UC...`
  - `youtube.com/@channelname`
  - `youtube.com/c/channelname`
  - `youtube.com/watch?v=...`
  - `youtu.be/VIDEO_ID`
  - `youtube.com/shorts/VIDEO_ID`

### データ整合性
- 個別動画からの自動チャンネル登録
- フェーズ間データ整合性検証
- 孤立データの検出とクリーンアップ
- 重複検出を伴う増分処理

### パフォーマンス最適化
- 大量データセットのバッチ処理
- OpenAI APIのトークン制限処理
- 効率的なベクトルストア管理
- 設定可能なチャンクサイズとオーバーラップ

## トラブルシューティング

### よくある問題

1. **「No enhanced transcripts found」** - フェーズ2が正常に完了していることを確認
2. **OpenAI APIタイムアウト** - config.yamlのbatch_sizeを減らす
3. **ベクトルストア構築失敗** - 統合モードの代わりにチャンネル特化構築を使用
4. **URL処理エラー** - URLフォーマットとアクセシビリティを確認

### パフォーマンスのヒント
- 安定性向上のため、チャンネルを個別に処理
- 定期更新には増分モードを使用
- OpenAI API使用量を監視し、バッチサイズを調整
- 定期的に孤立データをクリーンアップ

## 注意点
- システムはトランスクリプト強化と検索機能にOpenAI APIキーが必要です
- 大きなチャンネルの処理には、かなりの時間とAPI使用量が必要になる場合があります
- 最適なパフォーマンスを得るには、config.yamlの設定をニーズに合わせて調整してください
- システムは複数の言語をサポートし、日本語と英語が優先されます
- ネットワーク制限のある環境向けにプロキシサポートが利用可能です
- 個別動画処理は自動的に親チャンネルを検出・登録します

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。