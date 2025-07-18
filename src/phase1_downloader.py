#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1: Enhanced YouTube Video Data Downloader with Rich Context Information

Downloads YouTube videos with comprehensive metadata and timestamped transcripts
to provide maximum context for Phase 2 enhancement.
"""

import os
import re
import json
import logging
import time
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs
import yt_dlp
from config import Config
from channel_manager import ChannelManager

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    """Enhanced YouTube downloader with rich context extraction and multi-channel support"""
    
    def __init__(self, config: Config):
        self.config = config
        self.output_dir = config.get_phase1_path()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.channel_manager = ChannelManager(config)
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage with length limit"""
        # Remove invalid characters
        sanitized = re.sub(r'[\\/*?:"<>|]', "", filename).strip()
        
        # Limit filename length to prevent Windows path length issues
        # Windows has a 260 character path limit, so we limit filename to 100 characters
        # to leave room for directory path and extensions
        max_length = 100
        if len(sanitized) > max_length:
            # Truncate but try to keep meaningful part
            sanitized = sanitized[:max_length-3] + "..."
        
        return sanitized
    
    def _get_date_filter_option(self) -> Optional[str]:
        """Generate yt-dlp date filter option based on configuration"""
        date_config = self.config.phase1.date_filter
        
        if not date_config.enabled:
            if self.config.general.debug:
                logger.info("[DEBUG] Date filter is disabled")
            return None
            
        if date_config.mode == "all":
            if self.config.general.debug:
                logger.info("[DEBUG] Date filter mode: all (no filtering)")
            return None
        elif date_config.mode == "recent":
            # Calculate date N months ago
            from datetime import datetime, timedelta
            import calendar
            
            today = datetime.now()
            months_ago = date_config.default_months
            
            # Calculate target date approximately N months ago
            target_year = today.year
            target_month = today.month - months_ago
            
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            
            # Get the last day of the target month to ensure we include the whole month
            last_day = calendar.monthrange(target_year, target_month)[1]
            target_date = datetime(target_year, target_month, last_day)
            
            # Format as YYYYMMDD for yt-dlp
            date_filter = target_date.strftime("%Y%m%d")
            
            if self.config.general.debug:
                logger.info(f"[DEBUG] Date filter mode: recent ({months_ago} months ago)")
                logger.info(f"[DEBUG] Filter date: {target_date.strftime('%Y-%m-%d')} (yt-dlp format: {date_filter})")
                logger.info(f"[DEBUG] Videos uploaded after {target_date.strftime('%Y-%m-%d')} will be included")
            
            return date_filter
            
        elif date_config.mode == "since" and date_config.since_date:
            try:
                # Parse YYYY-MM-DD format
                from datetime import datetime
                target_date = datetime.strptime(date_config.since_date, "%Y-%m-%d")
                date_filter = target_date.strftime("%Y%m%d")
                
                if self.config.general.debug:
                    logger.info(f"[DEBUG] Date filter mode: since {date_config.since_date}")
                    logger.info(f"[DEBUG] Filter date: {date_config.since_date} (yt-dlp format: {date_filter})")
                
                return date_filter
            except ValueError:
                logger.warning(f"Invalid since_date format: {date_config.since_date}. Expected YYYY-MM-DD")
                return None
        
        return None
    
    def extract_channel_id(self, url: str) -> Optional[str]:
        """Extract channel ID or handle from URL"""
        if '/channel/' in url:
            return url.split('/channel/')[-1].split('/')[0]
        elif '/@' in url:
            return url.split('/@')[-1].split('/')[0]
        elif '/c/' in url:
            return url.split('/c/')[-1].split('/')[0]
        elif '/user/' in url:
            return url.split('/user/')[-1].split('/')[0]
        return None
    
    def get_channel_videos(self, channel_url: str) -> List[str]:
        """Get all video URLs from a channel"""
        logger.info(f"Fetching videos from channel: {channel_url}")
        
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # まず動画リストを取得
            'playlistend': self.config.youtube.max_videos_per_channel or None,
        }
        
        # Add date filter if configured
        date_after = self._get_date_filter_option()
        if date_after:
            ydl_opts['dateafter'] = date_after
            logger.info(f"Applying date filter: videos after {date_after}")
        
        # Add proxy settings if enabled
        proxy_url = self.config.get_proxy_url()
        if proxy_url:
            ydl_opts['proxy'] = proxy_url
            logger.info(f"Using proxy: {proxy_url}")
        
        logger.debug(f"Using User-Agent: {self.config.youtube.user_agent[:50]}...")
        
        video_urls = []
        
        # Try multiple approaches for maximum compatibility
        approaches = [
            # Approach 1: Standard extraction
            lambda: self._extract_with_standard_method(ydl_opts, channel_url),
            # Approach 2: Fallback with minimal options
            lambda: self._extract_with_fallback_method(channel_url),
        ]
        
        for i, approach in enumerate(approaches, 1):
            try:
                logger.debug(f"Trying extraction approach {i}")
                video_urls = approach()
                if video_urls:
                    logger.info(f"Successfully extracted videos using approach {i}")
                    break
            except Exception as e:
                logger.debug(f"Approach {i} failed: {e}")
                continue
        
        if not video_urls:
            logger.error(f"All extraction approaches failed for {channel_url}")
            
        logger.info(f"Found {len(video_urls)} videos to download")
        
        if self.config.general.debug and video_urls:
            logger.info(f"[DEBUG] Total videos found: {len(video_urls)}")
            logger.info(f"[DEBUG] Max videos per channel setting: {self.config.youtube.max_videos_per_channel}")
            logger.info(f"[DEBUG] Date filter enabled: {self.config.phase1.date_filter.enabled}")
            if self.config.phase1.date_filter.enabled:
                logger.info(f"[DEBUG] Date filter mode: {self.config.phase1.date_filter.mode}")
                if self.config.phase1.date_filter.mode == 'recent':
                    logger.info(f"[DEBUG] Recent months: {self.config.phase1.date_filter.default_months}")
        
        return video_urls
    
    def _extract_with_standard_method(self, ydl_opts: dict, channel_url: str) -> List[str]:
        """Standard extraction method with full options"""
        video_urls = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try different channel URL formats
            for url_format in [
                f"{channel_url}/videos",
                f"{channel_url}/streams",
                channel_url
            ]:
                try:
                    logger.debug(f"Trying URL format: {url_format}")
                    info = ydl.extract_info(url_format, download=False)
                    
                    if 'entries' in info:
                        # First, collect all video IDs
                        video_entries = []
                        for entry in info['entries']:
                            if entry and 'id' in entry:
                                video_entries.append({
                                    'id': entry['id'],
                                    'title': entry.get('title', 'Unknown Title'),
                                    'url': f"https://www.youtube.com/watch?v={entry['id']}"
                                })
                        
                        # Apply date filter by checking individual videos
                        video_urls = self._apply_date_filter_to_videos(video_entries)
                        break  # Success, no need to try other formats
                except Exception as e:
                    logger.debug(f"Failed with {url_format}: {e}")
                    continue
        return video_urls
    
    def _extract_with_fallback_method(self, channel_url: str) -> List[str]:
        """Fallback extraction method with minimal options"""
        video_urls = []
        
        # Minimal options for maximum compatibility
        minimal_opts = {
            'quiet': True,
            'extract_flat': True,  # フラット抽出で動画リストを取得
            'force_ipv4': True,
            'socket_timeout': 30,
            'retries': 3,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['dash', 'hls', 'translated_subs'],
                    'player_skip': ['js', 'configs', 'webpage']
                }
            }
        }
        
        # Add proxy if available
        proxy_url = self.config.get_proxy_url()
        if proxy_url:
            minimal_opts['proxy'] = proxy_url
        
        try:
            with yt_dlp.YoutubeDL(minimal_opts) as ydl:
                # Try only the main channel URL
                info = ydl.extract_info(f"{channel_url}/videos", download=False)
                
                if 'entries' in info:
                    # Collect video entries for fallback method
                    video_entries = []
                    for entry in info['entries']:
                        if entry and 'id' in entry:
                            video_entries.append({
                                'id': entry['id'],
                                'title': entry.get('title', 'Unknown Title'),
                                'url': f"https://www.youtube.com/watch?v={entry['id']}"
                            })
                            
                            # Limit to prevent overwhelming in fallback mode
                            if len(video_entries) >= 20:
                                break
                    
                    # Apply date filter to collected videos
                    video_urls = self._apply_date_filter_to_videos(video_entries)
        except Exception as e:
            logger.debug(f"Fallback method failed: {e}")
            
        return video_urls
    
    def _apply_date_filter_to_videos(self, video_entries: List[Dict[str, str]]) -> List[str]:
        """Apply date filter by checking individual videos"""
        filtered_urls = []
        date_filter = self._get_date_filter_option()
        
        if not date_filter:
            # No date filter, return all videos
            return [entry['url'] for entry in video_entries]
        
        # Convert date filter to datetime for comparison
        try:
            cutoff_date = datetime.strptime(date_filter, '%Y%m%d')
        except:
            logger.warning(f"Invalid date filter format: {date_filter}")
            return [entry['url'] for entry in video_entries]
        
        if self.config.general.debug:
            logger.info(f"[DEBUG] Checking {len(video_entries)} videos against date filter: {cutoff_date.strftime('%Y-%m-%d')}")
        
        # Check each video individually (with rate limiting)
        for i, entry in enumerate(video_entries):
            try:
                # Add delay to avoid rate limiting
                if i > 0:
                    time.sleep(0.5)  # 500ms delay between requests
                
                # Get video details
                video_info = self._get_video_details(entry['url'])
                if video_info and 'upload_date' in video_info:
                    upload_date_str = video_info['upload_date']
                    upload_date = datetime.strptime(upload_date_str, '%Y%m%d')
                    
                    if self.config.general.debug:
                        logger.info(f"[DEBUG] Video: {entry['title'][:50]}... | Upload Date: {upload_date.strftime('%Y-%m-%d')} | Video ID: {entry['id']}")
                    
                    # Check if video is newer than cutoff date
                    if upload_date >= cutoff_date:
                        filtered_urls.append(entry['url'])
                    else:
                        if self.config.general.debug:
                            logger.info(f"[DEBUG] Skipping old video: {entry['id']} (uploaded: {upload_date.strftime('%Y-%m-%d')})")
                else:
                    # If we can't get upload date, include the video (conservative approach)
                    if self.config.general.debug:
                        logger.info(f"[DEBUG] Video: {entry['title'][:50]}... | Upload Date: Unknown | Video ID: {entry['id']} (including)")
                    filtered_urls.append(entry['url'])
                    
            except Exception as e:
                if self.config.general.debug:
                    logger.info(f"[DEBUG] Error checking video {entry['id']}: {e} (including)")
                # If error occurs, include the video (conservative approach)
                filtered_urls.append(entry['url'])
        
        if self.config.general.debug:
            logger.info(f"[DEBUG] Date filter result: {len(filtered_urls)}/{len(video_entries)} videos passed")
        
        return filtered_urls
    
    def _get_video_details(self, video_url: str) -> Optional[Dict]:
        """Get detailed information for a single video"""
        try:
            ydl_opts = {
                'quiet': True,
                'skip_download': True,
                'writeinfojson': False,
                'extract_flat': False,
            }
            
            # Add proxy if available
            proxy_url = self.config.get_proxy_url()
            if proxy_url:
                ydl_opts['proxy'] = proxy_url
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(video_url, download=False)
                
        except Exception as e:
            logger.debug(f"Failed to get details for {video_url}: {e}")
            return None
    
    def _is_too_old(self, upload_date: str) -> bool:
        """Check if video is too old based on config"""
        try:
            video_date = datetime.strptime(upload_date, '%Y%m%d')
            cutoff_date = datetime.now() - timedelta(days=self.config.youtube.max_age_days)
            is_old = video_date < cutoff_date
            
            if self.config.general.debug:
                logger.info(f"[DEBUG] Age check: Video date {video_date.strftime('%Y-%m-%d')} vs cutoff {cutoff_date.strftime('%Y-%m-%d')} (max_age_days: {self.config.youtube.max_age_days}) -> {'TOO OLD' if is_old else 'OK'}")
            
            return is_old
        except Exception as e:
            if self.config.general.debug:
                logger.info(f"[DEBUG] Age check failed for upload_date '{upload_date}': {e}")
            return False
    
    def download_video_data(self, video_url: str, channel_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Download comprehensive video data with rich context"""
        logger.info(f"Processing video: {video_url}")
        
        # Add random sleep to avoid being detected as bot
        if self.config.youtube.random_sleep:
            sleep_time = random.uniform(self.config.youtube.min_sleep, self.config.youtube.max_sleep)
            logger.debug(f"Random sleep: {sleep_time:.1f} seconds")
            time.sleep(sleep_time)
        
        # Retry mechanism for bot detection errors
        for attempt in range(self.config.youtube.max_retries):
            try:
                # First, extract comprehensive video metadata
                metadata = self._extract_video_metadata(video_url)
                if not metadata:
                    if attempt < self.config.youtube.max_retries - 1:
                        logger.warning(f"Failed to extract metadata for {video_url}, retrying in {self.config.youtube.retry_sleep} seconds (attempt {attempt + 1}/{self.config.youtube.max_retries})")
                        time.sleep(self.config.youtube.retry_sleep)
                        continue
                    else:
                        logger.error(f"Failed to extract metadata for {video_url} after {self.config.youtube.max_retries} attempts")
                        return None
                
                break  # Success, exit retry loop
                
            except Exception as e:
                error_msg = str(e).lower()
                if ('sign in to confirm' in error_msg or 'bot' in error_msg or
                    'failed to extract any player response' in error_msg or
                    'getaddrinfo failed' in error_msg):
                    if attempt < self.config.youtube.max_retries - 1:
                        retry_sleep = self.config.youtube.retry_sleep * (attempt + 1)  # Exponential backoff
                        logger.warning(f"YouTube access issue for {video_url}, retrying in {retry_sleep} seconds (attempt {attempt + 1}/{self.config.youtube.max_retries})")
                        if 'failed to extract any player response' in error_msg:
                            logger.info("Hint: Consider updating yt-dlp with: pip install --upgrade yt-dlp")
                        time.sleep(retry_sleep)
                        continue
                    else:
                        logger.error(f"YouTube access error persists for {video_url} after {self.config.youtube.max_retries} attempts: {e}")
                        if 'failed to extract any player response' in error_msg:
                            logger.error("This may be due to YouTube changes. Try updating yt-dlp: pip install --upgrade yt-dlp")
                        return None
                else:
                    logger.error(f"Unexpected error processing {video_url}: {e}")
                    return None
        
        try:
            
            video_id = metadata['id']
            safe_title = self.sanitize_filename(metadata['title'])
            
            # Determine output directory (channel-specific or legacy)
            if channel_id:
                output_dir = self.config.get_channel_phase1_path(channel_id)
            else:
                output_dir = self.output_dir
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Create video-specific directory
            video_dir = output_dir / f"{video_id}_{safe_title}"
            video_dir.mkdir(exist_ok=True)
            
            # Save comprehensive metadata
            metadata_file = video_dir / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)
            
            # Download timestamped transcript
            transcript_data = self._download_timestamped_transcript(video_url, video_dir)
            
            # Save processing summary
            summary = {
                'video_id': video_id,
                'title': metadata['title'],
                'url': video_url,
                'channel_id': channel_id,
                'processed_at': datetime.now().isoformat(),
                'has_transcript': transcript_data is not None,
                'transcript_language': transcript_data.get('language') if transcript_data else None,
                'metadata_fields': list(metadata.keys()),
                'file_paths': {
                    'metadata': str(metadata_file),
                    'transcript': str(transcript_data.get('file_path')) if transcript_data else None
                }
            }
            
            summary_file = video_dir / "summary.json"
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            # Safe logging with encoding handling
            try:
                logger.info(f"Successfully processed: {metadata['title']}")
            except UnicodeEncodeError:
                # Fallback for Windows console encoding issues
                safe_title = metadata['title'].encode('utf-8', errors='replace').decode('utf-8')
                logger.info(f"Successfully processed: {safe_title}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to process video {video_url}: {e}")
            return None
    
    def _extract_video_metadata(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Extract comprehensive video metadata for context"""
        ydl_opts = {
            'quiet': True,
        }
        
        # Add proxy settings if enabled
        proxy_url = self.config.get_proxy_url()
        if proxy_url:
            ydl_opts['proxy'] = proxy_url
        
        for attempt in range(self.config.youtube.max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    
                    # Extract comprehensive metadata
                    metadata = {
                        'id': info.get('id'),
                        'title': info.get('title'),
                        'description': info.get('description', ''),
                        'uploader': info.get('uploader'),
                        'uploader_id': info.get('uploader_id'),
                        'upload_date': info.get('upload_date'),
                        'duration': info.get('duration'),
                        'view_count': info.get('view_count'),
                        'like_count': info.get('like_count'),
                        'tags': info.get('tags', []),
                        'categories': info.get('categories', []),
                        'thumbnail': info.get('thumbnail'),
                        'webpage_url': info.get('webpage_url'),
                        'language': info.get('language'),
                        'age_limit': info.get('age_limit'),
                        'availability': info.get('availability'),
                        'live_status': info.get('live_status'),
                        'release_timestamp': info.get('release_timestamp'),
                        'chapters': info.get('chapters', []),
                        'automatic_captions': list(info.get('automatic_captions', {}).keys()),
                        'subtitles': list(info.get('subtitles', {}).keys())
                    }
                    
                    # Add channel information if enabled
                    if self.config.phase1.include_channel_info:
                        metadata.update({
                            'channel': info.get('channel'),
                            'channel_id': info.get('channel_id'),
                            'channel_url': info.get('channel_url'),
                            'channel_follower_count': info.get('channel_follower_count'),
                            'uploader_url': info.get('uploader_url')
                        })
                    
                    # Add format information for context
                    formats = info.get('formats', [])
                    if formats:
                        metadata['available_formats'] = [
                            {
                                'format_id': f.get('format_id'),
                                'ext': f.get('ext'),
                                'quality': f.get('quality'),
                                'language': f.get('language'),
                                'acodec': f.get('acodec'),
                                'vcodec': f.get('vcodec')
                            }
                            for f in formats[:5]  # Keep first 5 formats for context
                        ]
                    
                    return metadata
                    
            except Exception as e:
                error_msg = str(e).lower()
                if ('sign in to confirm' in error_msg or 'bot' in error_msg or
                    'failed to extract any player response' in error_msg or
                    'getaddrinfo failed' in error_msg):
                    if attempt < self.config.youtube.max_retries - 1:
                        retry_sleep = self.config.youtube.retry_sleep * (attempt + 1)
                        logger.warning(f"YouTube access issue detected, retrying in {retry_sleep} seconds (attempt {attempt + 1}/{self.config.youtube.max_retries})")
                        if 'failed to extract any player response' in error_msg:
                            logger.info("Hint: Consider updating yt-dlp with: pip install --upgrade yt-dlp")
                        time.sleep(retry_sleep)
                        continue
                    else:
                        logger.error(f"Failed to extract metadata after {self.config.youtube.max_retries} attempts: {e}")
                        if 'failed to extract any player response' in error_msg:
                            logger.error("This may be due to YouTube changes. Try updating yt-dlp: pip install --upgrade yt-dlp")
                        return None
                else:
                    logger.error(f"Failed to extract metadata: {e}")
                    return None
        
        return None
    
    def _download_timestamped_transcript(self, video_url: str, output_dir: Path) -> Optional[Dict[str, Any]]:
        """Download transcript with preserved timestamp information using fallback strategy"""
        logger.debug(f"Downloading timestamped transcript with fallback strategy")
        
        # Try each language in fallback order
        for lang in self.config.youtube.subtitle_fallback_languages:
            logger.debug(f"Attempting to download subtitles in language: {lang}")
            
            # Add sleep between language attempts
            if lang != self.config.youtube.subtitle_fallback_languages[0]:
                time.sleep(self.config.youtube.subtitle_sleep_interval)
            
            result = self._download_subtitle_for_language(video_url, output_dir, lang)
            if result:
                logger.info(f"Successfully downloaded subtitles in language: {lang}")
                return result
            
        logger.warning(f"No subtitles found for {video_url} in any fallback language")
        return None
    
    def _download_subtitle_for_language(self, video_url: str, output_dir: Path, language: str) -> Optional[Dict[str, Any]]:
        """Download subtitle for a specific language with 429 error handling"""
        
        # Configure subtitle options - only automatic subtitles to reduce requests
        ydl_opts = {
            'writeautomaticsub': True,  # Only automatic subtitles
            'subtitleslangs': [language],  # Single language only
            'skip_download': True,
            'outtmpl': str(output_dir / 'subtitle.%(ext)s'),  # Use simple filename to match existing pattern
            'subtitlesformat': 'vtt',  # VTT preserves timestamps
            'quiet': True,
        }
        
        # Add proxy settings if enabled
        proxy_url = self.config.get_proxy_url()
        if proxy_url:
            ydl_opts['proxy'] = proxy_url
        
        # Retry mechanism for 429 errors
        for attempt in range(self.config.youtube.subtitle_max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=True)
                    
                    # Find the downloaded subtitle file - match existing pattern
                    for pattern in [f"subtitle.{language}.vtt", f"subtitle.{language}-auto.vtt"]:
                        subtitle_path = output_dir / pattern
                        if subtitle_path.exists():
                            # Process VTT to extract timestamped transcript
                            return self._process_vtt_transcript(subtitle_path, language)
                    
                    # If no file found, this language is not available
                    logger.debug(f"No subtitles available for language: {language}")
                    return None
                    
            except Exception as e:
                error_msg = str(e).lower()
                
                # Handle 429 errors specifically
                if '429' in error_msg or 'too many requests' in error_msg:
                    if attempt < self.config.youtube.subtitle_max_retries - 1:
                        wait_time = self.config.youtube.subtitle_429_retry_sleep * (attempt + 1)
                        logger.warning(f"429 error for subtitles in {language}, waiting {wait_time} seconds (attempt {attempt + 1}/{self.config.youtube.subtitle_max_retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"429 error persists for subtitles in {language} after {self.config.youtube.subtitle_max_retries} attempts")
                        return None
                else:
                    # Other errors - log and try next language
                    logger.debug(f"Failed to download subtitles for {language}: {e}")
                    return None
        
        return None
    
    def _process_vtt_transcript(self, vtt_path: Path, language: str) -> Dict[str, Any]:
        """Process VTT file to create timestamped transcript with enhanced context"""
        logger.debug(f"Processing VTT transcript: {vtt_path}")
        
        transcript_segments = []
        raw_text_lines = []
        
        try:
            with open(vtt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            current_segment = None
            
            for line in lines:
                line = line.strip()
                
                # Skip VTT headers and empty lines
                if (not line or line.startswith('WEBVTT') or 
                    line.startswith('NOTE') or line.startswith('Kind:') or 
                    line.startswith('Language:')):
                    continue
                
                # Timestamp line (e.g., "00:01:30.500 --> 00:01:33.200")
                if '-->' in line:
                    if current_segment:
                        transcript_segments.append(current_segment)
                    
                    # Parse timestamps
                    times = line.split(' --> ')
                    start_time = self._parse_timestamp(times[0])
                    end_time = self._parse_timestamp(times[1])
                    
                    current_segment = {
                        'start_time': start_time,
                        'end_time': end_time,
                        'start_seconds': self._timestamp_to_seconds(start_time),
                        'end_seconds': self._timestamp_to_seconds(end_time),
                        'text': ''
                    }
                
                # Text content line
                elif current_segment is not None and not re.match(r'^\\d+$', line):
                    # Clean text (remove VTT formatting tags)
                    clean_text = re.sub(r'<[^>]*>', '', line)
                    if clean_text.strip():
                        if current_segment['text']:
                            current_segment['text'] += ' '
                        current_segment['text'] += clean_text.strip()
                        raw_text_lines.append(clean_text.strip())
            
            # Add final segment
            if current_segment:
                transcript_segments.append(current_segment)
            
            # Create processed transcript file
            transcript_file = vtt_path.parent / f"transcript_{language}.json"
            
            # Prepare enhanced transcript data
            transcript_data = {
                'language': language,
                'source_file': str(vtt_path),
                'processed_at': datetime.now().isoformat(),
                'total_segments': len(transcript_segments),
                'total_duration_seconds': transcript_segments[-1]['end_seconds'] if transcript_segments else 0,
                'segments': transcript_segments,
                'full_text': ' '.join(raw_text_lines),
                'context_metadata': {
                    'has_timestamps': True,
                    'segment_count': len(transcript_segments),
                    'average_segment_length': sum(len(s['text']) for s in transcript_segments) / len(transcript_segments) if transcript_segments else 0,
                    'language_detected': language
                }
            }
            
            # Save processed transcript
            with open(transcript_file, 'w', encoding='utf-8') as f:
                json.dump(transcript_data, f, ensure_ascii=False, indent=2)
            
            # Clean up original VTT file
            vtt_path.unlink()
            
            logger.debug(f"Processed {len(transcript_segments)} transcript segments")
            return {
                'language': language,
                'file_path': transcript_file,
                'segments_count': len(transcript_segments),
                'has_timestamps': True
            }
            
        except Exception as e:
            logger.error(f"Failed to process VTT transcript: {e}")
            return None
    
    def _parse_timestamp(self, timestamp: str) -> str:
        """Parse and clean timestamp format"""
        return timestamp.strip()
    
    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert timestamp to seconds for easier processing"""
        try:
            # Handle format: HH:MM:SS.mmm or MM:SS.mmm
            parts = timestamp.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + float(seconds)
            else:
                return float(parts[0])
        except:
            return 0.0
    
    def _filter_new_videos(self, video_urls: List[str], channel_id: Optional[str] = None) -> List[str]:
        """Filter video URLs to only include new videos not already processed"""
        new_videos = []
        existing_video_ids = set()
        
        # Determine which directory to check for existing videos
        if channel_id:
            check_dir = self.config.get_channel_phase1_path(channel_id)
        else:
            check_dir = self.output_dir
        
        # Get existing video IDs from phase 1 output directory
        if check_dir.exists():
            for video_dir in check_dir.iterdir():
                if video_dir.is_dir():
                    # Extract video ID from directory name (format: {video_id}_{title})
                    dir_name = video_dir.name
                    if '_' in dir_name:
                        # YouTube video IDs are 11 characters long
                        # Find the first underscore after a valid video ID length
                        parts = dir_name.split('_')
                        if len(parts[0]) == 11:
                            # Standard case: 11-character video ID
                            video_id = parts[0]
                        else:
                            # Handle video IDs with underscores (like dS6_6_48SEc)
                            # Look for the pattern where title starts (usually with Japanese characters or brackets)
                            for i in range(1, len(parts)):
                                potential_id = '_'.join(parts[:i+1])
                                if len(potential_id) == 11:
                                    video_id = potential_id
                                    break
                            else:
                                # Fallback: assume first part is video ID
                                video_id = parts[0]
                        existing_video_ids.add(video_id)
        
        # Check each video URL
        for video_url in video_urls:
            video_id = self._extract_video_id(video_url)
            if video_id and video_id not in existing_video_ids:
                new_videos.append(video_url)
            else:
                logger.debug(f"Skipping existing video: {video_id}")
        
        logger.info(f"Found {len(existing_video_ids)} existing videos, {len(new_videos)} new videos")
        return new_videos
    
    def _extract_video_id(self, video_url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        try:
            from urllib.parse import parse_qs, urlparse
            parsed = urlparse(video_url)
            
            if 'youtube.com' in parsed.netloc:
                if 'watch' in parsed.path:
                    return parse_qs(parsed.query).get('v', [None])[0]
                elif '/embed/' in parsed.path:
                    return parsed.path.split('/embed/')[-1].split('?')[0]
            elif 'youtu.be' in parsed.netloc:
                return parsed.path.lstrip('/')
            
            return None
        except Exception as e:
            logger.debug(f"Failed to extract video ID from {video_url}: {e}")
            return None
    
    def process_channel(self, channel_url: str, incremental: bool = True) -> Dict[str, Any]:
        """Process videos from a YouTube channel with incremental update support"""
        logger.info(f"Starting channel processing: {channel_url} (incremental: {incremental})")
        
        # Extract and register/update channel information
        channel_id = self.channel_manager.extract_channel_id(channel_url)
        if not channel_id:
            logger.error(f"Could not extract channel ID from URL: {channel_url}")
            return {'success': False, 'error': 'Invalid channel URL'}
        
        # Register channel if not already registered
        if not self.channel_manager.get_channel(channel_id):
            self.channel_manager.add_channel(channel_url, channel_id)
        
        # Get all video URLs from channel
        video_urls = self.get_channel_videos(channel_url)
        
        if not video_urls:
            logger.error("No videos found in channel")
            return {'success': False, 'error': 'No videos found'}
        
        # Filter for new videos only if incremental update is enabled
        if incremental:
            new_video_urls = self._filter_new_videos(video_urls, channel_id)
            if not new_video_urls:
                logger.info("No new videos found for processing")
                return {
                    'success': True,
                    'channel_url': channel_url,
                    'channel_id': channel_id,
                    'total_videos': len(video_urls),
                    'processed_videos': [],
                    'failed_videos': [],
                    'skipped_videos': video_urls,
                    'new_videos_count': 0,
                    'started_at': datetime.now().isoformat(),
                    'completed_at': datetime.now().isoformat(),
                    'success_rate': 1.0
                }
            video_urls = new_video_urls
            logger.info(f"Found {len(video_urls)} new videos to process")
        
        # Process each video
        results = {
            'channel_url': channel_url,
            'channel_id': channel_id,
            'total_videos': len(video_urls),
            'processed_videos': [],
            'failed_videos': [],
            'skipped_videos': [],
            'new_videos_count': len(video_urls),
            'incremental_mode': incremental,
            'started_at': datetime.now().isoformat()
        }
        
        for i, video_url in enumerate(video_urls, 1):
            logger.info(f"Processing video {i}/{len(video_urls)}: {video_url}")
            
            try:
                result = self.download_video_data(video_url, channel_id)
                if result:
                    results['processed_videos'].append(result)
                else:
                    results['failed_videos'].append(video_url)
            except Exception as e:
                logger.error(f"Failed to process {video_url}: {e}")
                results['failed_videos'].append(video_url)
        
        results['completed_at'] = datetime.now().isoformat()
        results['success_rate'] = len(results['processed_videos']) / len(video_urls) if video_urls else 0
        
        # Update channel status
        if results['processed_videos']:
            last_video_id = results['processed_videos'][-1]['video_id']
            self.channel_manager.update_channel_status(
                channel_id, 
                len(results['processed_videos']), 
                last_video_id
            )
        
        # Save channel processing summary
        if channel_id:
            output_dir = self.config.get_channel_phase1_path(channel_id)
        else:
            output_dir = self.output_dir
        
        summary_file = output_dir / f"channel_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Channel processing completed. Success rate: {results['success_rate']:.2%}")
        return results
    
    def process_videos(self, video_urls: List[str], incremental: bool = True) -> Dict[str, Any]:
        """Process individual video URLs with channel auto-detection"""
        logger.info(f"Starting video processing: {len(video_urls)} video(s) (incremental: {incremental})")
        
        results = {
            'total_videos': len(video_urls),
            'processed_videos': [],
            'failed_videos': [],
            'skipped_videos': [],
            'started_at': datetime.now().isoformat(),
            'channel_registrations': []
        }
        
        # Process each video URL
        for i, video_url in enumerate(video_urls, 1):
            logger.info(f"Processing video {i}/{len(video_urls)}: {video_url}")
            
            try:
                # Extract video ID for duplicate check
                video_id = self._extract_video_id(video_url)
                if not video_id:
                    logger.error(f"Could not extract video ID from {video_url}")
                    results['failed_videos'].append({
                        'url': video_url,
                        'error': 'Could not extract video ID'
                    })
                    continue
                
                # Check if video already exists (incremental mode)
                if incremental and self._is_video_already_processed(video_id):
                    logger.info(f"Video {video_id} already processed, skipping")
                    results['skipped_videos'].append(video_url)
                    continue
                
                # Extract channel information from video metadata
                channel_info = self._extract_channel_info_from_video(video_url)
                if not channel_info:
                    logger.error(f"Could not extract channel info from {video_url}")
                    results['failed_videos'].append({
                        'url': video_url,
                        'error': 'Could not extract channel info'
                    })
                    continue
                
                # Register/update channel if needed
                channel_id = self._register_channel_from_video(channel_info)
                if not channel_id:
                    logger.error(f"Could not register channel for {video_url}")
                    results['failed_videos'].append({
                        'url': video_url,
                        'error': 'Could not register channel'
                    })
                    continue
                
                # Download video data
                video_data = self.download_video_data(video_url, channel_id)
                if video_data:
                    results['processed_videos'].append({
                        'url': video_url,
                        'video_id': video_id,
                        'channel_id': channel_id,
                        'title': video_data.get('title', 'Unknown'),
                        'output_dir': video_data.get('output_dir')
                    })
                    logger.info(f"Successfully processed video: {video_id}")
                else:
                    results['failed_videos'].append({
                        'url': video_url,
                        'error': 'Failed to download video data'
                    })
                    logger.error(f"Failed to download video data for {video_url}")
                
                # Track channel registration
                if channel_id not in [c['channel_id'] for c in results['channel_registrations']]:
                    results['channel_registrations'].append({
                        'channel_id': channel_id,
                        'channel_name': channel_info.get('name', 'Unknown'),
                        'channel_url': channel_info.get('url', 'Unknown')
                    })
                
            except Exception as e:
                logger.error(f"Error processing video {video_url}: {e}")
                results['failed_videos'].append({
                    'url': video_url,
                    'error': str(e)
                })
        
        # Calculate results
        results['completed_at'] = datetime.now().isoformat()
        results['success_rate'] = len(results['processed_videos']) / len(video_urls) if video_urls else 0
        results['new_videos_count'] = len(results['processed_videos'])
        results['incremental_mode'] = incremental
        
        # Save summary
        output_dir = self.output_dir
        summary_file = output_dir / f"videos_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Video processing completed. Success rate: {results['success_rate']:.2%}")
        logger.info(f"Registered/updated {len(results['channel_registrations'])} channels")
        
        return results
    
    def _extract_channel_info_from_video(self, video_url: str) -> Optional[Dict[str, Any]]:
        """Extract channel information from video metadata"""
        try:
            # Use existing metadata extraction method
            metadata = self._extract_video_metadata(video_url)
            if not metadata:
                return None
            
            # Extract channel information
            channel_info = {
                'name': metadata.get('uploader') or metadata.get('channel', 'Unknown'),
                'id': metadata.get('uploader_id') or metadata.get('channel_id', ''),
                'url': metadata.get('channel_url', ''),
                'description': metadata.get('description', ''),
                'subscriber_count': metadata.get('subscriber_count', 0)
            }
            
            # Generate channel URL if not present
            if not channel_info['url'] and channel_info['id']:
                if channel_info['id'].startswith('@'):
                    channel_info['url'] = f"https://www.youtube.com/{channel_info['id']}"
                elif channel_info['id'].startswith('UC'):
                    channel_info['url'] = f"https://www.youtube.com/channel/{channel_info['id']}"
                else:
                    channel_info['url'] = f"https://www.youtube.com/user/{channel_info['id']}"
            
            logger.debug(f"Extracted channel info: {channel_info['name']} ({channel_info['id']})")
            return channel_info
            
        except Exception as e:
            logger.error(f"Error extracting channel info from {video_url}: {e}")
            return None
    
    def _register_channel_from_video(self, channel_info: Dict[str, Any]) -> Optional[str]:
        """Register or update channel from video metadata"""
        try:
            channel_id = channel_info.get('id')
            channel_name = channel_info.get('name', 'Unknown')
            channel_url = channel_info.get('url', '')
            
            if not channel_id:
                logger.error("No channel ID found in channel info")
                return None
            
            # Check if channel already exists
            existing_channel = self.channel_manager.get_channel(channel_id)
            if existing_channel:
                logger.debug(f"Channel {channel_id} already exists, updating if needed")
                # Update channel info if needed
                if existing_channel.name != channel_name:
                    # Update channel name if different
                    logger.info(f"Updating channel name: {existing_channel.name} -> {channel_name}")
                return channel_id
            
            # Register new channel
            logger.info(f"Registering new channel: {channel_name} ({channel_id})")
            registered_id = self.channel_manager.add_channel(channel_url, channel_name)
            
            if registered_id:
                logger.info(f"Successfully registered channel: {channel_name}")
                return registered_id
            else:
                logger.error(f"Failed to register channel: {channel_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error registering channel: {e}")
            return None
    
    def _is_video_already_processed(self, video_id: str) -> bool:
        """Check if video has already been processed"""
        # Check in all channel directories
        for channel_dir in self.output_dir.iterdir():
            if not channel_dir.is_dir():
                continue
                
            for video_dir in channel_dir.iterdir():
                if not video_dir.is_dir():
                    continue
                    
                # Check if directory name contains video ID
                if video_id in video_dir.name:
                    metadata_file = video_dir / "metadata.json"
                    if metadata_file.exists():
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata = json.load(f)
                            if metadata.get('id') == video_id:
                                return True
                        except Exception:
                            continue
        
        return False
    
    def process_all_channels(self, incremental: bool = True) -> Dict[str, Any]:
        """Process all enabled channels"""
        logger.info("Starting processing of all enabled channels")
        
        enabled_channels = self.channel_manager.get_enabled_channels()
        if not enabled_channels:
            logger.warning("No enabled channels found")
            return {'success': False, 'error': 'No enabled channels found'}
        
        overall_results = {
            'total_channels': len(enabled_channels),
            'processed_channels': [],
            'failed_channels': [],
            'started_at': datetime.now().isoformat()
        }
        
        for channel_info in enabled_channels:
            logger.info(f"Processing channel: {channel_info.name} ({channel_info.id})")
            
            try:
                result = self.process_channel(channel_info.url, incremental)
                result['channel_name'] = channel_info.name
                
                if result.get('success', True):
                    overall_results['processed_channels'].append(result)
                else:
                    overall_results['failed_channels'].append({
                        'channel_id': channel_info.id,
                        'channel_name': channel_info.name,
                        'error': result.get('error', 'Unknown error')
                    })
            except Exception as e:
                logger.error(f"Failed to process channel {channel_info.name}: {e}")
                overall_results['failed_channels'].append({
                    'channel_id': channel_info.id,
                    'channel_name': channel_info.name,
                    'error': str(e)
                })
        
        overall_results['completed_at'] = datetime.now().isoformat()
        overall_results['success_rate'] = len(overall_results['processed_channels']) / len(enabled_channels)
        
        logger.info(f"All channels processing completed. Success rate: {overall_results['success_rate']:.2%}")
        return overall_results