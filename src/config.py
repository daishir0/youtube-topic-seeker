#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Configuration management for YouTube Topic Seeker
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

@dataclass
class OpenAIConfig:
    """OpenAI API configuration"""
    api_key: str
    model: str = "gpt-4o-mini"
    max_tokens: int = 2000
    temperature: float = 0.3
    max_retries: int = 3

@dataclass
class YouTubeConfig:
    """YouTube download configuration"""
    subtitle_languages: List[str] = field(default_factory=lambda: ["ja", "en", "auto"])
    quality: str = "bestvideo+bestaudio"
    max_videos_per_channel: int = 0
    max_age_days: int = 0
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    sleep_interval: int = 2
    random_sleep: bool = True
    max_sleep: int = 5

@dataclass
class Phase1Config:
    """Phase 1 data download configuration"""
    output_dir: str = "./data/1-plain"
    include_metadata: bool = True
    include_description: bool = True
    include_tags: bool = True
    include_channel_info: bool = True
    preserve_timestamps: bool = True

@dataclass
class Phase2Config:
    """Phase 2 transcript enhancement configuration"""
    input_dir: str = "./data/1-plain"
    output_dir: str = "./data/2-target"
    use_context_prompt: bool = True
    batch_size: int = 5
    skip_existing: bool = True

@dataclass
class RAGConfig:
    """RAG configuration"""
    input_dir: str = "./data/2-target"
    vectorstore_dir: str = "./data/vectorstore"
    embedding_model: str = "text-embedding-ada-002"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retrieval_k: int = 5
    similarity_threshold: float = 0.7
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1

@dataclass
class GeneralConfig:
    """General application configuration"""
    debug: bool = False
    verbosity: int = 2
    max_workers: int = 4

@dataclass
class EmailConfig:
    """Email notification configuration"""
    enabled: bool = False
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    recipient: str = ""

@dataclass
class ChannelDefaultSettings:
    """Default channel processing settings"""
    enabled: bool = True
    max_videos: int = 0
    max_age_days: int = 0

@dataclass
class UnifiedSearchConfig:
    """Unified search configuration"""
    enabled: bool = True
    default_scope: str = "all"

@dataclass
class ChannelsConfig:
    """Multi-channel configuration"""
    management_file: str = "./data/channels.json"
    default_settings: ChannelDefaultSettings = field(default_factory=ChannelDefaultSettings)
    unified_search: UnifiedSearchConfig = field(default_factory=UnifiedSearchConfig)

@dataclass
class ProxyConfig:
    """Proxy configuration for SSH SOCKS proxy"""
    enabled: bool = False
    type: str = "socks5"  # socks5 or http
    host: str = "127.0.0.1"
    port: int = 1080

@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: str = "./logs/app.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    max_size_mb: int = 10
    backup_count: int = 5

class Config:
    """Main configuration class"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration from YAML file"""
        self.config_path = config_path or "config.yaml"
        self._config_data = self._load_config()
        
        # Initialize sub-configurations
        self.openai = self._init_openai_config()
        self.youtube = self._init_youtube_config()
        self.phase1 = self._init_phase1_config()
        self.phase2 = self._init_phase2_config()
        self.rag = self._init_rag_config()
        self.general = self._init_general_config()
        self.proxy = self._init_proxy_config()
        self.email = self._init_email_config()
        self.logging = self._init_logging_config()
        self.channels = self._init_channels_config()
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}\n"
                f"Please copy config.yaml.sample to config.yaml and modify settings."
            )
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML configuration: {e}")
    
    def _init_openai_config(self) -> OpenAIConfig:
        """Initialize OpenAI configuration"""
        openai_config = self._config_data.get('openai', {})
        
        # Get API key from config or environment
        api_key = openai_config.get('api_key') or os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError(
                "OpenAI API key not found. Set it in config.yaml or as environment variable OPENAI_API_KEY"
            )
        
        return OpenAIConfig(
            api_key=api_key,
            model=openai_config.get('model', 'gpt-4o-mini'),
            max_tokens=openai_config.get('max_tokens', 2000),
            temperature=openai_config.get('temperature', 0.3),
            max_retries=openai_config.get('max_retries', 3)
        )
    
    def _init_youtube_config(self) -> YouTubeConfig:
        """Initialize YouTube configuration"""
        youtube_config = self._config_data.get('youtube', {})
        return YouTubeConfig(
            subtitle_languages=youtube_config.get('subtitle_languages', ['ja', 'en', 'auto']),
            quality=youtube_config.get('quality', 'bestvideo+bestaudio'),
            max_videos_per_channel=youtube_config.get('max_videos_per_channel', 0),
            max_age_days=youtube_config.get('max_age_days', 0),
            user_agent=youtube_config.get('user_agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
            sleep_interval=youtube_config.get('sleep_interval', 2),
            random_sleep=youtube_config.get('random_sleep', True),
            max_sleep=youtube_config.get('max_sleep', 5)
        )
    
    def _init_phase1_config(self) -> Phase1Config:
        """Initialize Phase 1 configuration"""
        phase1_config = self._config_data.get('phase1', {})
        return Phase1Config(
            output_dir=phase1_config.get('output_dir', './data/1-plain'),
            include_metadata=phase1_config.get('include_metadata', True),
            include_description=phase1_config.get('include_description', True),
            include_tags=phase1_config.get('include_tags', True),
            include_channel_info=phase1_config.get('include_channel_info', True),
            preserve_timestamps=phase1_config.get('preserve_timestamps', True)
        )
    
    def _init_phase2_config(self) -> Phase2Config:
        """Initialize Phase 2 configuration"""
        phase2_config = self._config_data.get('phase2', {})
        return Phase2Config(
            input_dir=phase2_config.get('input_dir', './data/1-plain'),
            output_dir=phase2_config.get('output_dir', './data/2-target'),
            use_context_prompt=phase2_config.get('use_context_prompt', True),
            batch_size=phase2_config.get('batch_size', 5),
            skip_existing=phase2_config.get('skip_existing', True)
        )
    
    def _init_rag_config(self) -> RAGConfig:
        """Initialize RAG configuration"""
        rag_config = self._config_data.get('rag', {})
        return RAGConfig(
            input_dir=rag_config.get('input_dir', './data/2-target'),
            vectorstore_dir=rag_config.get('vectorstore_dir', './data/vectorstore'),
            embedding_model=rag_config.get('embedding_model', 'text-embedding-ada-002'),
            chunk_size=rag_config.get('chunk_size', 1000),
            chunk_overlap=rag_config.get('chunk_overlap', 200),
            retrieval_k=rag_config.get('retrieval_k', 5),
            similarity_threshold=rag_config.get('similarity_threshold', 0.7),
            llm_model=rag_config.get('llm_model', 'gpt-4o-mini'),
            llm_temperature=rag_config.get('llm_temperature', 0.1)
        )
    
    def _init_general_config(self) -> GeneralConfig:
        """Initialize general configuration"""
        general_config = self._config_data.get('general', {})
        return GeneralConfig(
            debug=general_config.get('debug', False),
            verbosity=general_config.get('verbosity', 2),
            max_workers=general_config.get('max_workers', 4)
        )
    
    def _init_proxy_config(self) -> ProxyConfig:
        """Initialize proxy configuration"""
        proxy_config = self._config_data.get('proxy', {})
        return ProxyConfig(
            enabled=proxy_config.get('enabled', False),
            type=proxy_config.get('type', 'socks5'),
            host=proxy_config.get('host', '127.0.0.1'),
            port=proxy_config.get('port', 1080)
        )
    
    def _init_email_config(self) -> EmailConfig:
        """Initialize email configuration"""
        email_config = self._config_data.get('email', {})
        return EmailConfig(
            enabled=email_config.get('enabled', False),
            smtp_server=email_config.get('smtp_server', 'smtp.gmail.com'),
            smtp_port=email_config.get('smtp_port', 587),
            username=email_config.get('username', ''),
            password=email_config.get('password', ''),
            recipient=email_config.get('recipient', '')
        )
    
    def _init_logging_config(self) -> LoggingConfig:
        """Initialize logging configuration"""
        logging_config = self._config_data.get('logging', {})
        return LoggingConfig(
            level=logging_config.get('level', 'INFO'),
            file=logging_config.get('file', './logs/app.log'),
            format=logging_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s'),
            max_size_mb=logging_config.get('max_size_mb', 10),
            backup_count=logging_config.get('backup_count', 5)
        )
    
    def _init_channels_config(self) -> ChannelsConfig:
        """Initialize channels configuration"""
        channels_config = self._config_data.get('channels', {})
        
        # Default settings
        default_settings_config = channels_config.get('default_settings', {})
        default_settings = ChannelDefaultSettings(
            enabled=default_settings_config.get('enabled', True),
            max_videos=default_settings_config.get('max_videos', 0),
            max_age_days=default_settings_config.get('max_age_days', 0)
        )
        
        # Unified search settings
        unified_search_config = channels_config.get('unified_search', {})
        unified_search = UnifiedSearchConfig(
            enabled=unified_search_config.get('enabled', True),
            default_scope=unified_search_config.get('default_scope', 'all')
        )
        
        return ChannelsConfig(
            management_file=channels_config.get('management_file', './data/channels.json'),
            default_settings=default_settings,
            unified_search=unified_search
        )
    
    def _ensure_directories(self):
        """Ensure all required directories exist"""
        directories = [
            self.phase1.output_dir,
            self.phase2.output_dir,
            self.rag.vectorstore_dir,
            os.path.dirname(self.logging.file),
            os.path.dirname(self.channels.management_file)
        ]
        
        for directory in directories:
            if directory:
                # Convert to Path object for cross-platform compatibility
                path_obj = Path(directory).resolve()
                path_obj.mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self):
        """Setup logging configuration"""
        from logging.handlers import RotatingFileHandler
        
        # Convert log level string to logging constant
        level = getattr(logging, self.logging.level.upper(), logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(self.logging.format)
        
        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if self.logging.file:
            file_handler = RotatingFileHandler(
                self.logging.file,
                maxBytes=self.logging.max_size_mb * 1024 * 1024,
                backupCount=self.logging.backup_count
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
    
    def get_debug_mode(self) -> bool:
        """Get debug mode status"""
        return self.general.debug
    
    def get_verbosity(self) -> int:
        """Get verbosity level"""
        return self.general.verbosity
    
    def get_proxy_settings(self) -> Optional[Dict[str, str]]:
        """Get proxy settings for HTTP requests"""
        if not self.proxy.enabled:
            return None
        
        proxy_url = f"{self.proxy.type}://{self.proxy.host}:{self.proxy.port}"
        return {
            'http': proxy_url,
            'https': proxy_url
        }
    
    def get_proxy_url(self) -> Optional[str]:
        """Get proxy URL for yt-dlp and other tools"""
        if not self.proxy.enabled:
            return None
        return f"{self.proxy.type}://{self.proxy.host}:{self.proxy.port}"
    
    def get_phase1_path(self) -> Path:
        """Get Phase 1 output directory as Path object"""
        return Path(self.phase1.output_dir).resolve()
    
    def get_phase2_path(self) -> Path:
        """Get Phase 2 output directory as Path object"""
        return Path(self.phase2.output_dir).resolve()
    
    def get_vectorstore_path(self) -> Path:
        """Get vector store directory as Path object"""
        return Path(self.rag.vectorstore_dir).resolve()
    
    def get_channels_file_path(self) -> Path:
        """Get channels management file path as Path object"""
        return Path(self.channels.management_file).resolve()
    
    def get_channel_phase1_path(self, channel_id: str) -> Path:
        """Get Phase 1 output directory for specific channel"""
        return Path(self.phase1.output_dir).resolve() / channel_id
    
    def get_channel_phase2_path(self, channel_id: str) -> Path:
        """Get Phase 2 output directory for specific channel"""
        return Path(self.phase2.output_dir).resolve() / channel_id
    
    def get_channel_vectorstore_path(self, channel_id: str) -> Path:
        """Get vector store directory for specific channel"""
        return Path(self.rag.vectorstore_dir).resolve() / channel_id