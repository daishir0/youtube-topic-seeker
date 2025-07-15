# 🌐 SSH SOCKSプロキシ設定ガイド

YouTubeアクセス制限を回避するため、クライアントPC経由でのアクセス機能を追加しました。

## 📋 設定手順

### 1. クライアントPC側（あなたのPC）
```bash
# SSH SOCKS5プロキシを起動（ポート1080）
ssh -D 1080 ec2-user@your-ec2-instance
```

**このコマンドの効果：**
- ローカルポート1080でSOCKS5プロキシサーバーが起動
- EC2への暗号化SSHトンネルが作成
- プロキシ経由通信がトンネル経由でEC2に転送

### 2. EC2側設定

`config.yaml`でプロキシを有効化：
```yaml
proxy:
  enabled: true  # false → true に変更
  type: "socks5"
  host: "127.0.0.1"
  port: 1080
```

### 3. 実行
```bash
conda activate 311
python main.py
```

## 🔧 動作確認

### プロキシ状況確認
```bash
# クライアントPC側でプロキシ起動確認
netstat -an | grep 1080
# または
lsof -i :1080
```

### システム状況確認
```bash
# EC2側でプロキシ設定確認
python main.py
# メニュー「6. 📊 Show Status」でプロキシ有効状況を確認
```

## 📡 通信フロー

```
EC2のPython → localhost:1080(SOCKS5) → SSHトンネル → クライアントPC → YouTube
```

## ⚠️ 注意事項

1. **SSH接続維持必須**: SSH接続が切れるとプロキシも停止
2. **クライアントPC要件**: YouTubeにアクセス可能である必要
3. **追加ソフト不要**: 標準SSH機能のみで実現

## 🚀 対応範囲

以下の全てのYouTubeアクセスがプロキシ経由になります：

- **フェーズ1**: yt-dlp による動画・字幕ダウンロード
- **フェーズ2**: OpenAI API（必要時）
- **フェーズ3**: LangChain OpenAI API

## 🔍 トラブルシューティング

### プロキシ接続エラー
1. SSH接続が生きているか確認
2. ポート1080が使用中でないか確認
3. config.yamlの設定値確認

### YouTube接続エラー
1. クライアントPCからYouTubeアクセス可能か確認
2. ファイアウォール設定確認
3. 地域制限確認

これで地域制限を回避してYouTubeアクセスが可能になります！