# YouTube Topic Seeker

## Overview
YouTube Topic Seeker is a comprehensive system for searching topics across YouTube videos. It allows you to find exactly where specific topics are discussed in videos, providing timestamps and summaries. The system works in three phases:

1. **Data Download**: Downloads video metadata and transcripts from YouTube channels
2. **Transcript Enhancement**: Improves transcript quality using AI
3. **RAG Search**: Enables semantic search across videos with timestamp-precise results

Perfect for researchers, content creators, or anyone who needs to find specific information across multiple YouTube videos quickly.

## Installation

### Prerequisites
- Python 3.11 or higher
- Conda environment (recommended)
- OpenAI API key

### Steps
1. Clone the repository:
   ```
   git clone https://github.com/daishir0/youtube-topic-seeker.git
   cd youtube-topic-seeker
   ```

2. Create and activate a conda environment:
   ```
   conda create -n topic-seeker python=3.11
   conda activate topic-seeker
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Copy the sample configuration file and edit it:
   ```
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
```
python main.py
```

This will present a menu with options to:
- Download YouTube data
- Enhance transcripts
- Build vector store
- Search topics
- Manage channels
- Migrate data

### Automatic Mode
Process a YouTube channel automatically:
```
python main.py https://www.youtube.com/@channel_name
```

This will run the full pipeline (download, enhance, build vector store) for the specified channel.

### Search Examples
After processing videos, you can search for topics:
- "AI ethics in modern technology"
- "Climate change solutions"
- "Financial investment strategies"

The system will return relevant results with:
- Video title
- Topic summary
- Timestamp link to the exact moment
- Relevance score

## Notes
- The system requires an OpenAI API key for transcript enhancement and search functionality
- Processing large channels may take significant time and API usage
- For optimal performance, ensure your config.yaml settings are tuned for your needs
- The system supports multiple languages, with priority given to Japanese and English
- Proxy support is available for network-restricted environments

## License
This project is licensed under the MIT License - see the LICENSE file for details.

---

# YouTube Topic Seeker

## 概要
YouTube Topic Seekerは、YouTube動画全体からトピックを検索するための総合システムです。特定のトピックがどの動画のどの時間に話されているかを正確に見つけ出し、タイムスタンプと要約を提供します。システムは3つのフェーズで動作します：

1. **データダウンロード**: YouTubeチャンネルから動画メタデータとトランスクリプトをダウンロード
2. **トランスクリプト強化**: AIを使用してトランスクリプトの品質を向上
3. **RAG検索**: タイムスタンプ付きの精密な結果で動画全体のセマンティック検索を可能に

研究者、コンテンツクリエイター、または複数のYouTube動画から特定の情報を素早く見つける必要がある方に最適です。

## インストール方法

### 前提条件
- Python 3.11以上
- Conda環境（推奨）
- OpenAI APIキー

### 手順
1. リポジトリをクローンします：
   ```
   git clone https://github.com/daishir0/youtube-topic-seeker.git
   cd youtube-topic-seeker
   ```

2. Conda環境を作成して有効化します：
   ```
   conda create -n topic-seeker python=3.11
   conda activate topic-seeker
   ```

3. 依存関係をインストールします：
   ```
   pip install -r requirements.txt
   ```

4. サンプル設定ファイルをコピーして編集します：
   ```
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
```
python main.py
```

これにより、以下のオプションを含むメニューが表示されます：
- YouTubeデータのダウンロード
- トランスクリプトの強化
- ベクトルストアの構築
- トピック検索
- チャンネル管理
- データ移行

### 自動モード
YouTubeチャンネルを自動的に処理します：
```
python main.py https://www.youtube.com/@チャンネル名
```

これにより、指定されたチャンネルに対して完全なパイプライン（ダウンロード、強化、ベクトルストア構築）が実行されます。

### 検索例
動画を処理した後、トピックを検索できます：
- 「現代技術におけるAI倫理」
- 「気候変動の解決策」
- 「金融投資戦略」

システムは以下を含む関連結果を返します：
- 動画タイトル
- トピック概要
- 正確な瞬間へのタイムスタンプリンク
- 関連度スコア

## 注意点
- システムはトランスクリプト強化と検索機能にOpenAI APIキーが必要です
- 大きなチャンネルの処理には、かなりの時間とAPI使用量が必要になる場合があります
- 最適なパフォーマンスを得るには、config.yamlの設定をニーズに合わせて調整してください
- システムは複数の言語をサポートし、日本語と英語が優先されます
- ネットワーク制限のある環境向けにプロキシサポートが利用可能です

## ライセンス
このプロジェクトはMITライセンスの下でライセンスされています。詳細はLICENSEファイルを参照してください。