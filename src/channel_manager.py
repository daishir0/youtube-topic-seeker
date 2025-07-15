#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Channel Management for YouTube Topic Seeker

Manages multiple YouTube channels configuration, processing status, and metadata.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, parse_qs

from config import Config

logger = logging.getLogger(__name__)

@dataclass
class ChannelSettings:
    """Channel-specific settings"""
    enabled: bool = True
    max_videos: int = 0
    max_age_days: int = 0

@dataclass
class ChannelInfo:
    """Channel information and metadata"""
    id: str
    name: str
    url: str
    enabled: bool = True
    settings: ChannelSettings = None
    last_updated: Optional[str] = None
    video_count: int = 0
    last_video_id: Optional[str] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.settings is None:
            self.settings = ChannelSettings()
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

class ChannelManager:
    """Manager for multiple YouTube channels"""
    
    def __init__(self, config: Config):
        self.config = config
        self.channels_file = config.get_channels_file_path()
        self.channels: Dict[str, ChannelInfo] = {}
        self.load_channels()
    
    def load_channels(self):
        """Load channels from management file"""
        try:
            if self.channels_file.exists():
                with open(self.channels_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Load channels from JSON
                for channel_data in data.get('channels', []):
                    settings_data = channel_data.get('settings', {})
                    settings = ChannelSettings(**settings_data)
                    
                    channel_info = ChannelInfo(
                        id=channel_data['id'],
                        name=channel_data['name'],
                        url=channel_data['url'],
                        enabled=channel_data.get('enabled', True),
                        settings=settings,
                        last_updated=channel_data.get('last_updated'),
                        video_count=channel_data.get('video_count', 0),
                        last_video_id=channel_data.get('last_video_id'),
                        created_at=channel_data.get('created_at')
                    )
                    
                    self.channels[channel_info.id] = channel_info
                
                logger.info(f"Loaded {len(self.channels)} channels from {self.channels_file}")
            else:
                logger.info(f"No channels file found at {self.channels_file}, starting with empty channels")
                
        except Exception as e:
            logger.error(f"Failed to load channels: {e}")
            self.channels = {}
    
    def save_channels(self):
        """Save channels to management file"""
        try:
            # Ensure directory exists
            self.channels_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to JSON format
            channels_data = {
                'channels': [
                    {
                        'id': channel.id,
                        'name': channel.name,
                        'url': channel.url,
                        'enabled': channel.enabled,
                        'settings': asdict(channel.settings),
                        'last_updated': channel.last_updated,
                        'video_count': channel.video_count,
                        'last_video_id': channel.last_video_id,
                        'created_at': channel.created_at
                    }
                    for channel in self.channels.values()
                ]
            }
            
            with open(self.channels_file, 'w', encoding='utf-8') as f:
                json.dump(channels_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(self.channels)} channels to {self.channels_file}")
            
        except Exception as e:
            logger.error(f"Failed to save channels: {e}")
    
    def extract_channel_id(self, channel_url: str) -> Optional[str]:
        """Extract channel ID from YouTube URL"""
        try:
            parsed = urlparse(channel_url)
            
            if '/channel/' in parsed.path:
                return parsed.path.split('/channel/')[-1].split('/')[0]
            elif '/@' in parsed.path:
                # Handle @username format - we'll use the username as ID
                return parsed.path.split('/@')[-1].split('/')[0]
            elif '/c/' in parsed.path:
                return parsed.path.split('/c/')[-1].split('/')[0]
            elif '/user/' in parsed.path:
                return parsed.path.split('/user/')[-1].split('/')[0]
            
            return None
            
        except Exception as e:
            logger.debug(f"Failed to extract channel ID from {channel_url}: {e}")
            return None
    
    def add_channel(self, channel_url: str, channel_name: Optional[str] = None) -> Optional[str]:
        """Add a new channel to management"""
        try:
            channel_id = self.extract_channel_id(channel_url)
            if not channel_id:
                logger.error(f"Could not extract channel ID from URL: {channel_url}")
                return None
            
            # Check if channel already exists
            if channel_id in self.channels:
                logger.warning(f"Channel {channel_id} already exists")
                return channel_id
            
            # Use provided name or generate from URL
            if not channel_name:
                channel_name = channel_id
            
            # Create channel info with default settings
            default_settings = ChannelSettings(
                enabled=self.config.channels.default_settings.enabled,
                max_videos=self.config.channels.default_settings.max_videos,
                max_age_days=self.config.channels.default_settings.max_age_days
            )
            
            channel_info = ChannelInfo(
                id=channel_id,
                name=channel_name,
                url=channel_url,
                enabled=True,
                settings=default_settings
            )
            
            self.channels[channel_id] = channel_info
            self.save_channels()
            
            logger.info(f"Added new channel: {channel_id} ({channel_name})")
            return channel_id
            
        except Exception as e:
            logger.error(f"Failed to add channel: {e}")
            return None
    
    def remove_channel(self, channel_id: str, delete_data: bool = False) -> bool:
        """Remove a channel from management"""
        try:
            if channel_id not in self.channels:
                logger.warning(f"Channel {channel_id} not found")
                return False
            
            # Remove from channels dict
            del self.channels[channel_id]
            
            # Delete data if requested
            if delete_data:
                self._delete_channel_data(channel_id)
            
            self.save_channels()
            logger.info(f"Removed channel: {channel_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove channel {channel_id}: {e}")
            return False
    
    def _delete_channel_data(self, channel_id: str):
        """Delete all data for a specific channel"""
        try:
            import shutil
            
            # Delete Phase 1 data
            phase1_path = self.config.get_channel_phase1_path(channel_id)
            if phase1_path.exists():
                shutil.rmtree(phase1_path)
                logger.info(f"Deleted Phase 1 data for channel: {channel_id}")
            
            # Delete Phase 2 data
            phase2_path = self.config.get_channel_phase2_path(channel_id)
            if phase2_path.exists():
                shutil.rmtree(phase2_path)
                logger.info(f"Deleted Phase 2 data for channel: {channel_id}")
            
            # Delete Phase 3 data
            vectorstore_path = self.config.get_channel_vectorstore_path(channel_id)
            if vectorstore_path.exists():
                shutil.rmtree(vectorstore_path)
                logger.info(f"Deleted vector store data for channel: {channel_id}")
                
        except Exception as e:
            logger.error(f"Failed to delete data for channel {channel_id}: {e}")
    
    def get_channel(self, channel_id: str) -> Optional[ChannelInfo]:
        """Get channel information by ID"""
        return self.channels.get(channel_id)
    
    def list_channels(self, enabled_only: bool = False) -> List[ChannelInfo]:
        """List all channels"""
        channels = list(self.channels.values())
        if enabled_only:
            channels = [ch for ch in channels if ch.enabled]
        return channels
    
    def update_channel_status(self, channel_id: str, video_count: int, last_video_id: Optional[str] = None):
        """Update channel processing status"""
        if channel_id in self.channels:
            channel = self.channels[channel_id]
            channel.video_count = video_count
            channel.last_updated = datetime.now().isoformat()
            if last_video_id:
                channel.last_video_id = last_video_id
            self.save_channels()
            logger.debug(f"Updated status for channel {channel_id}: {video_count} videos")
    
    def enable_channel(self, channel_id: str, enabled: bool = True):
        """Enable or disable a channel"""
        if channel_id in self.channels:
            self.channels[channel_id].enabled = enabled
            self.save_channels()
            logger.info(f"Channel {channel_id} {'enabled' if enabled else 'disabled'}")
    
    def get_enabled_channels(self) -> List[ChannelInfo]:
        """Get list of enabled channels"""
        return [ch for ch in self.channels.values() if ch.enabled]
    
    def get_channel_statistics(self) -> Dict[str, Any]:
        """Get overall channel statistics"""
        enabled_channels = self.get_enabled_channels()
        total_videos = sum(ch.video_count for ch in self.channels.values())
        
        return {
            'total_channels': len(self.channels),
            'enabled_channels': len(enabled_channels),
            'disabled_channels': len(self.channels) - len(enabled_channels),
            'total_videos': total_videos,
            'last_updated': max(
                (ch.last_updated for ch in self.channels.values() if ch.last_updated),
                default=None
            )
        }