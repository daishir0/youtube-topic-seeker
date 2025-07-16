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
            return None
            
        if date_config.mode == "all":
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
            return target_date.strftime("%Y%m%d")
            
        elif date_config.mode == "since" and date_config.since_date:
            try:
                # Parse YYYY-MM-DD format
                from datetime import datetime
                target_date = datetime.strptime(date_config.since_date, "%Y-%m-%d")
                return target_date.strftime("%Y%m%d")
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
            'extract_flat': True,
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
                        for entry in info['entries']:
                            if entry and 'id' in entry:
                                video_id = entry['id']
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                
                                # Check age filter
                                if self.config.youtube.max_age_days > 0:
                                    upload_date = entry.get('upload_date')
                                    if upload_date and self._is_too_old(upload_date):
                                        continue
                                
                                video_urls.append(video_url)
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
            'extract_flat': True,
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
                    for entry in info['entries']:
                        if entry and 'id' in entry:
                            video_id = entry['id']
                            video_url = f"https://www.youtube.com/watch?v={video_id}"
                            video_urls.append(video_url)
                            
                            # Limit to prevent overwhelming in fallback mode
                            if len(video_urls) >= 20:
                                break
        except Exception as e:
            logger.debug(f"Fallback method failed: {e}")
            
        return video_urls
    
    def _is_too_old(self, upload_date: str) -> bool:
        """Check if video is too old based on config"""
        try:
            video_date = datetime.strptime(upload_date, '%Y%m%d')
            cutoff_date = datetime.now() - timedelta(days=self.config.youtube.max_age_days)
            return video_date < cutoff_date
        except:
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
        """Download transcript with preserved timestamp information"""
        logger.debug(f"Downloading timestamped transcript")
        
        # Configure subtitle options for maximum context preservation
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': self.config.youtube.subtitle_languages,
            'skip_download': True,
            'outtmpl': str(output_dir / 'subtitle.%(ext)s'),  # Use simple filename to avoid path length issues
            'subtitlesformat': 'vtt',  # VTT preserves timestamps
            'quiet': True,
        }
        
        # Add proxy settings if enabled
        proxy_url = self.config.get_proxy_url()
        if proxy_url:
            ydl_opts['proxy'] = proxy_url
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                
                # Find the downloaded subtitle file with simple filename
                for lang in self.config.youtube.subtitle_languages:
                    # Try different subtitle file patterns with simple filename
                    for pattern in [f"subtitle.{lang}.vtt", f"subtitle.{lang}-auto.vtt"]:
                        subtitle_path = output_dir / pattern
                        if subtitle_path.exists():
                            # Process VTT to extract timestamped transcript
                            return self._process_vtt_transcript(subtitle_path, lang)
                
                logger.warning(f"No subtitles found for {video_url}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to download transcript: {e}")
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
                        video_id = dir_name.split('_')[0]
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