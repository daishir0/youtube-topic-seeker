#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL分類器 - YouTubeチャンネルURLと動画URLを判別

チャンネルURL・動画URL両対応システムのためのURL判別ロジック
"""

import re
from urllib.parse import urlparse, parse_qs
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class URLType(Enum):
    """URL種別の定義"""
    CHANNEL = "channel"
    VIDEO = "video"
    UNKNOWN = "unknown"

class URLClassifier:
    """YouTube URL分類器"""
    
    def __init__(self):
        """初期化"""
        # チャンネルURL判別パターン
        self.channel_patterns = [
            r'youtube\.com/channel/([^/?]+)',       # /channel/UCxxxxxxx
            r'youtube\.com/c/([^/?]+)',             # /c/channelname
            r'youtube\.com/@([^/?]+)',              # /@channelname
            r'youtube\.com/user/([^/?]+)',          # /user/username
            r'youtube\.com/([^/?]+)$',              # /channelname (直接)
        ]
        
        # 動画URL判別パターン
        self.video_patterns = [
            r'youtube\.com/watch\?.*v=([^&]+)',     # /watch?v=VIDEO_ID
            r'youtu\.be/([^?]+)',                   # youtu.be/VIDEO_ID
            r'youtube\.com/embed/([^?]+)',          # /embed/VIDEO_ID
            r'youtube\.com/v/([^?]+)',              # /v/VIDEO_ID
        ]
    
    def classify_url(self, url: str) -> URLType:
        """単一URLを分類"""
        if not url or not isinstance(url, str):
            return URLType.UNKNOWN
        
        # URLの正規化
        url = url.strip()
        
        # HTTPSでない場合は追加
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            parsed = urlparse(url)
            
            # YouTube以外のドメインは除外
            if 'youtube.com' not in parsed.netloc and 'youtu.be' not in parsed.netloc:
                return URLType.UNKNOWN
            
            # 動画URLのチェック（優先度高）
            for pattern in self.video_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    logger.debug(f"動画URLと判別: {url}")
                    return URLType.VIDEO
            
            # チャンネルURLのチェック
            for pattern in self.channel_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    logger.debug(f"チャンネルURLと判別: {url}")
                    return URLType.CHANNEL
            
            # 特殊ケース: shortsは動画として扱う
            if '/shorts/' in url:
                logger.debug(f"Shorts動画URLと判別: {url}")
                return URLType.VIDEO
            
            logger.warning(f"URLの分類ができませんでした: {url}")
            return URLType.UNKNOWN
            
        except Exception as e:
            logger.error(f"URL分類エラー {url}: {e}")
            return URLType.UNKNOWN
    
    def classify_urls(self, urls: List[str]) -> Dict[str, URLType]:
        """複数URLを分類"""
        results = {}
        for url in urls:
            results[url] = self.classify_url(url)
        return results
    
    def separate_urls(self, urls: List[str]) -> Tuple[List[str], List[str]]:
        """URLリストをチャンネルと動画に分離"""
        channel_urls = []
        video_urls = []
        
        for url in urls:
            url_type = self.classify_url(url)
            if url_type == URLType.CHANNEL:
                channel_urls.append(url)
            elif url_type == URLType.VIDEO:
                video_urls.append(url)
            else:
                logger.warning(f"不明なURL形式をスキップ: {url}")
        
        return channel_urls, video_urls
    
    def determine_processing_mode(self, urls: List[str]) -> Tuple[str, List[str], List[str]]:
        """
        処理モードを決定
        
        Args:
            urls: URL リスト
            
        Returns:
            Tuple[処理モード, チャンネルURL, 動画URL]
            処理モード: 'channel', 'video', 'mixed', 'unknown'
        """
        if not urls:
            return 'unknown', [], []
        
        # 最初のURLで判定
        first_url_type = self.classify_url(urls[0])
        
        # 全URLを分類
        channel_urls, video_urls = self.separate_urls(urls)
        
        # 処理モード決定
        if first_url_type == URLType.CHANNEL:
            if video_urls:
                logger.warning("最初がチャンネルURLですが、動画URLも含まれています。チャンネルモードで処理します。")
                logger.info(f"動画URLは無視されます: {video_urls}")
            return 'channel', channel_urls, []
        elif first_url_type == URLType.VIDEO:
            if channel_urls:
                logger.warning("最初が動画URLですが、チャンネルURLも含まれています。動画モードで処理します。")
                logger.info(f"チャンネルURLは無視されます: {channel_urls}")
            return 'video', [], video_urls
        else:
            logger.error(f"最初のURLが不明な形式です: {urls[0]}")
            return 'unknown', [], []
    
    def extract_video_id(self, video_url: str) -> Optional[str]:
        """動画URLから動画IDを抽出"""
        if self.classify_url(video_url) != URLType.VIDEO:
            return None
        
        # パターンマッチング
        for pattern in self.video_patterns:
            match = re.search(pattern, video_url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def extract_channel_identifier(self, channel_url: str) -> Optional[str]:
        """チャンネルURLからチャンネル識別子を抽出"""
        if self.classify_url(channel_url) != URLType.CHANNEL:
            return None
        
        # パターンマッチング
        for pattern in self.channel_patterns:
            match = re.search(pattern, channel_url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None


def test_url_classifier():
    """URL分類器のテスト"""
    classifier = URLClassifier()
    
    # テストケース
    test_urls = [
        # チャンネルURL
        'https://www.youtube.com/channel/UCxxxxxxx',
        'https://www.youtube.com/c/channelname',
        'https://www.youtube.com/@channelname',
        'https://www.youtube.com/user/username',
        
        # 動画URL
        'https://www.youtube.com/watch?v=VIDEO_ID',
        'https://youtu.be/VIDEO_ID',
        'https://www.youtube.com/embed/VIDEO_ID',
        'https://www.youtube.com/shorts/VIDEO_ID',
        
        # 不明
        'https://example.com',
        'invalid_url',
    ]
    
    print("=== URL分類テスト ===")
    for url in test_urls:
        url_type = classifier.classify_url(url)
        print(f"{url} -> {url_type.value}")
    
    # 処理モード判定テスト
    print("\n=== 処理モード判定テスト ===")
    test_cases = [
        ['https://www.youtube.com/channel/UCxxxxxxx', 'https://www.youtube.com/channel/UCyyyyyyy'],
        ['https://www.youtube.com/watch?v=VIDEO1', 'https://www.youtube.com/watch?v=VIDEO2'],
        ['https://www.youtube.com/channel/UCxxxxxxx', 'https://www.youtube.com/watch?v=VIDEO1'],
        ['https://www.youtube.com/watch?v=VIDEO1', 'https://www.youtube.com/channel/UCxxxxxxx'],
    ]
    
    for urls in test_cases:
        mode, channels, videos = classifier.determine_processing_mode(urls)
        print(f"{urls} -> モード: {mode}, チャンネル: {len(channels)}, 動画: {len(videos)}")


if __name__ == "__main__":
    test_url_classifier()