#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Migration Tool for Multi-Channel Support

Migrates existing single-channel data to the new multi-channel structure.
Handles Phase 1, Phase 2, and Phase 3 data migration with integrity checks.
"""

import os
import json
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import hashlib

from config import Config
from channel_manager import ChannelManager, ChannelInfo

logger = logging.getLogger(__name__)

@dataclass
class MigrationResult:
    """Migration result for a single item"""
    success: bool
    source_path: str
    target_path: str
    error_message: Optional[str] = None
    data_type: str = "unknown"
    video_id: Optional[str] = None
    channel_id: Optional[str] = None

@dataclass
class MigrationSummary:
    """Summary of migration process"""
    total_items: int
    successful_items: int
    failed_items: int
    phase1_results: List[MigrationResult]
    phase2_results: List[MigrationResult]
    phase3_results: List[MigrationResult]
    started_at: str
    completed_at: Optional[str] = None
    default_channel_id: Optional[str] = None

class DataMigrator:
    """Tool for migrating legacy single-channel data to multi-channel structure"""
    
    def __init__(self, config: Config):
        self.config = config
        self.channel_manager = ChannelManager(config)
        
        # Migration paths
        self.legacy_phase1_path = config.get_phase1_path()
        self.legacy_phase2_path = config.get_phase2_path()
        self.legacy_vectorstore_path = config.get_vectorstore_path()
        
        # Default channel for migration
        self.default_channel_id = "migrated_legacy_data"
        self.default_channel_name = "Legacy Data (Migrated)"
        self.default_channel_url = "https://youtube.com/legacy"
    
    def analyze_existing_data(self) -> Dict[str, Any]:
        """Analyze existing data structure and content"""
        logger.info("Analyzing existing data structure...")
        
        analysis = {
            'phase1': self._analyze_phase1_data(),
            'phase2': self._analyze_phase2_data(),
            'phase3': self._analyze_phase3_data(),
            'analyzed_at': datetime.now().isoformat()
        }
        
        logger.info(f"Analysis complete: {analysis}")
        return analysis
    
    def _analyze_phase1_data(self) -> Dict[str, Any]:
        """Analyze Phase 1 data structure"""
        phase1_info = {
            'path': str(self.legacy_phase1_path),
            'exists': self.legacy_phase1_path.exists(),
            'video_directories': [],
            'total_videos': 0,
            'has_channel_summaries': False,
            'channel_info': None
        }
        
        if not self.legacy_phase1_path.exists():
            return phase1_info
        
        # Find video directories
        video_dirs = []
        collected_channel_info = {}
        
        for item in self.legacy_phase1_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a video directory (has metadata.json)
                metadata_file = item / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        video_info = {
                            'directory': item.name,
                            'video_id': metadata.get('id'),
                            'title': metadata.get('title'),
                            'uploader': metadata.get('uploader'),
                            'channel': metadata.get('channel'),
                            'channel_id': metadata.get('channel_id'),
                            'has_transcript': (item / f"transcript_{self.config.youtube.subtitle_languages[0]}.json").exists()
                        }
                        video_dirs.append(video_info)
                        
                        # Collect channel info from first video with complete data
                        if (not collected_channel_info and 
                            metadata.get('channel_id') and 
                            metadata.get('channel')):
                            collected_channel_info = {
                                'id': metadata.get('channel_id'),
                                'name': metadata.get('channel'),
                                'url': metadata.get('channel_url', ''),
                                'total_videos': 0  # Will be set later
                            }
                            
                    except Exception as e:
                        logger.debug(f"Error reading metadata from {item}: {e}")
        
        # Check for channel summaries
        channel_summaries = list(self.legacy_phase1_path.glob("channel_summary_*.json"))
        if channel_summaries:
            phase1_info['has_channel_summaries'] = True
            try:
                with open(channel_summaries[0], 'r', encoding='utf-8') as f:
                    summary = json.load(f)
                    
                # Use summary data if available, otherwise use collected info
                if summary.get('channel_url'):
                    channel_id = self._extract_channel_id_from_url(summary.get('channel_url', ''))
                    # If we have collected channel info, use the name from there
                    channel_name = (collected_channel_info.get('name') if collected_channel_info 
                                   else self.default_channel_name)
                    
                    phase1_info['channel_info'] = {
                        'url': summary.get('channel_url'),
                        'id': channel_id,
                        'name': channel_name,
                        'total_videos': summary.get('total_videos', 0)
                    }
                    
            except Exception as e:
                logger.debug(f"Error reading channel summary: {e}")
        
        # Use collected channel info if no summary available
        if not phase1_info['channel_info'] and collected_channel_info:
            collected_channel_info['total_videos'] = len(video_dirs)
            phase1_info['channel_info'] = collected_channel_info
        
        phase1_info['video_directories'] = video_dirs
        phase1_info['total_videos'] = len(video_dirs)
        
        return phase1_info
    
    def _extract_channel_id_from_url(self, url: str) -> Optional[str]:
        """Extract channel ID from YouTube URL"""
        if not url:
            return None
        
        # Handle different URL formats
        if '/channel/' in url:
            return url.split('/channel/')[-1].split('/')[0]
        elif '/@' in url:
            return url.split('/@')[-1].split('/')[0]
        elif '/c/' in url:
            return url.split('/c/')[-1].split('/')[0]
        elif '/user/' in url:
            return url.split('/user/')[-1].split('/')[0]
        
        return None
    
    def _analyze_phase2_data(self) -> Dict[str, Any]:
        """Analyze Phase 2 data structure"""
        phase2_info = {
            'path': str(self.legacy_phase2_path),
            'exists': self.legacy_phase2_path.exists(),
            'enhanced_files': [],
            'total_enhanced': 0,
            'has_summaries': False
        }
        
        if not self.legacy_phase2_path.exists():
            return phase2_info
        
        # Find enhanced files
        enhanced_files = []
        for enhanced_file in self.legacy_phase2_path.glob("*_enhanced.json"):
            try:
                with open(enhanced_file, 'r', encoding='utf-8') as f:
                    enhanced_data = json.load(f)
                
                file_info = {
                    'filename': enhanced_file.name,
                    'video_id': enhanced_data.get('video_id'),
                    'title': enhanced_data.get('title'),
                    'uploader': enhanced_data.get('uploader'),
                    'channel': enhanced_data.get('channel'),
                    'segments_count': len(enhanced_data.get('transcript', {}).get('segments', []))
                }
                enhanced_files.append(file_info)
            except Exception as e:
                logger.debug(f"Error reading enhanced file {enhanced_file}: {e}")
        
        # Check for enhancement summaries
        summaries = list(self.legacy_phase2_path.glob("enhancement_summary_*.json"))
        phase2_info['has_summaries'] = len(summaries) > 0
        
        phase2_info['enhanced_files'] = enhanced_files
        phase2_info['total_enhanced'] = len(enhanced_files)
        
        return phase2_info
    
    def _analyze_phase3_data(self) -> Dict[str, Any]:
        """Analyze Phase 3 data structure"""
        phase3_info = {
            'path': str(self.legacy_vectorstore_path),
            'exists': self.legacy_vectorstore_path.exists(),
            'has_build_info': False,
            'build_info': None,
            'vector_files': []
        }
        
        if not self.legacy_vectorstore_path.exists():
            return phase3_info
        
        # Check for build info
        build_info_file = self.legacy_vectorstore_path / "build_info.json"
        if build_info_file.exists():
            try:
                with open(build_info_file, 'r', encoding='utf-8') as f:
                    build_info = json.load(f)
                phase3_info['has_build_info'] = True
                phase3_info['build_info'] = {
                    'built_at': build_info.get('built_at'),
                    'total_videos': build_info.get('total_videos', 0),
                    'total_segments': build_info.get('total_segments', 0),
                    'total_chunks': build_info.get('total_chunks', 0)
                }
            except Exception as e:
                logger.debug(f"Error reading build info: {e}")
        
        # List vector store files
        vector_files = []
        for item in self.legacy_vectorstore_path.iterdir():
            if item.is_file():
                vector_files.append({
                    'name': item.name,
                    'size': item.stat().st_size,
                    'modified': datetime.fromtimestamp(item.stat().st_mtime).isoformat()
                })
        
        phase3_info['vector_files'] = vector_files
        
        return phase3_info
    
    def create_migration_plan(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Create migration plan based on analysis"""
        logger.info("Creating migration plan...")
        
        # Determine channel information
        channel_info = self._determine_channel_info(analysis)
        
        plan = {
            'target_channel': channel_info,
            'migration_steps': [],
            'estimated_items': 0,
            'backup_required': True,
            'created_at': datetime.now().isoformat()
        }
        
        # Phase 1 migration
        if analysis['phase1']['exists'] and analysis['phase1']['total_videos'] > 0:
            plan['migration_steps'].append({
                'phase': 'phase1',
                'description': 'Migrate Phase 1 video data to channel-specific structure',
                'source_path': str(self.legacy_phase1_path),
                'target_path': str(self.config.get_channel_phase1_path(channel_info['id'])),
                'items_count': analysis['phase1']['total_videos']
            })
            plan['estimated_items'] += analysis['phase1']['total_videos']
        
        # Phase 2 migration
        if analysis['phase2']['exists'] and analysis['phase2']['total_enhanced'] > 0:
            plan['migration_steps'].append({
                'phase': 'phase2',
                'description': 'Migrate Phase 2 enhanced data to channel-specific structure',
                'source_path': str(self.legacy_phase2_path),
                'target_path': str(self.config.get_channel_phase2_path(channel_info['id'])),
                'items_count': analysis['phase2']['total_enhanced']
            })
            plan['estimated_items'] += analysis['phase2']['total_enhanced']
        
        # Phase 3 migration
        if analysis['phase3']['exists']:
            plan['migration_steps'].append({
                'phase': 'phase3',
                'description': 'Migrate Phase 3 vector store to channel-specific structure',
                'source_path': str(self.legacy_vectorstore_path),
                'target_path': str(self.config.get_channel_vectorstore_path(channel_info['id'])),
                'items_count': 1  # Vector store is treated as one item
            })
            plan['estimated_items'] += 1
        
        return plan
    
    def _determine_channel_info(self, analysis: Dict[str, Any]) -> Dict[str, str]:
        """Determine channel information for migration"""
        # Try to extract channel info from Phase 1 data
        phase1_data = analysis.get('phase1', {})
        
        if phase1_data.get('channel_info'):
            channel_info = phase1_data['channel_info']
            channel_id = channel_info.get('id')
            # Ensure channel_id is not None or empty
            if not channel_id:
                channel_id = self.default_channel_id
            
            return {
                'id': channel_id,
                'name': self._extract_channel_name(analysis),
                'url': channel_info.get('url', self.default_channel_url)
            }
        
        # Try to extract from video metadata
        video_dirs = phase1_data.get('video_directories', [])
        if video_dirs:
            first_video = video_dirs[0]
            channel_id = first_video.get('channel_id')
            # Ensure channel_id is not None or empty
            if not channel_id:
                channel_id = self.default_channel_id
                
            channel_name = first_video.get('channel')
            if not channel_name:
                channel_name = self.default_channel_name
            
            return {
                'id': channel_id,
                'name': channel_name,
                'url': self.default_channel_url
            }
        
        # Default fallback
        return {
            'id': self.default_channel_id,
            'name': self.default_channel_name,
            'url': self.default_channel_url
        }
    
    def _extract_channel_name(self, analysis: Dict[str, Any]) -> str:
        """Extract channel name from analysis data"""
        # Try Phase 1 video data
        phase1_data = analysis.get('phase1', {})
        video_dirs = phase1_data.get('video_directories', [])
        
        if video_dirs:
            uploaders = [v.get('uploader') for v in video_dirs if v.get('uploader')]
            channels = [v.get('channel') for v in video_dirs if v.get('channel')]
            
            if channels:
                # Use most common channel name
                from collections import Counter
                most_common = Counter(channels).most_common(1)
                if most_common:
                    return most_common[0][0]
            
            if uploaders:
                # Use most common uploader name
                from collections import Counter
                most_common = Counter(uploaders).most_common(1)
                if most_common:
                    return most_common[0][0]
        
        return self.default_channel_name
    
    def execute_migration(self, plan: Dict[str, Any], create_backup: bool = True) -> MigrationSummary:
        """Execute the migration plan"""
        logger.info("Starting data migration...")
        
        summary = MigrationSummary(
            total_items=plan['estimated_items'],
            successful_items=0,
            failed_items=0,
            phase1_results=[],
            phase2_results=[],
            phase3_results=[],
            started_at=datetime.now().isoformat(),
            default_channel_id=plan['target_channel']['id']
        )
        
        try:
            # Register migration channel
            self._register_migration_channel(plan['target_channel'])
            
            # Create backup if requested
            if create_backup:
                self._create_backup()
            
            # Execute migration steps
            for step in plan['migration_steps']:
                logger.info(f"Executing migration step: {step['description']}")
                
                if step['phase'] == 'phase1':
                    results = self._migrate_phase1_data(step, plan['target_channel']['id'])
                    summary.phase1_results.extend(results)
                elif step['phase'] == 'phase2':
                    results = self._migrate_phase2_data(step, plan['target_channel']['id'])
                    summary.phase2_results.extend(results)
                elif step['phase'] == 'phase3':
                    results = self._migrate_phase3_data(step, plan['target_channel']['id'])
                    summary.phase3_results.extend(results)
            
            # Calculate final statistics
            all_results = summary.phase1_results + summary.phase2_results + summary.phase3_results
            summary.successful_items = len([r for r in all_results if r.success])
            summary.failed_items = len([r for r in all_results if not r.success])
            
            summary.completed_at = datetime.now().isoformat()
            logger.info(f"Migration completed. Success: {summary.successful_items}, Failed: {summary.failed_items}")
            
            return summary
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            summary.completed_at = datetime.now().isoformat()
            return summary
    
    def _register_migration_channel(self, channel_info: Dict[str, str]):
        """Register the migration channel"""
        logger.info(f"Registering migration channel: {channel_info['name']}")
        
        # Check if channel already exists
        existing_channel = self.channel_manager.get_channel(channel_info['id'])
        if existing_channel:
            logger.info(f"Channel {channel_info['id']} already exists, skipping registration...")
        else:
            logger.info(f"Adding new channel: {channel_info['id']}")
            # channel_manager.add_channel only accepts url and name (optional)
            self.channel_manager.add_channel(
                channel_info['url'],
                channel_info['name']
            )
    
    def _create_backup(self):
        """Create backup of existing data"""
        logger.info("Creating backup of existing data...")
        
        backup_dir = Path("./data_backup") / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup Phase 1
        if self.legacy_phase1_path.exists():
            shutil.copytree(self.legacy_phase1_path, backup_dir / "1-plain")
            logger.info(f"Phase 1 data backed up to {backup_dir / '1-plain'}")
        
        # Backup Phase 2
        if self.legacy_phase2_path.exists():
            shutil.copytree(self.legacy_phase2_path, backup_dir / "2-target")
            logger.info(f"Phase 2 data backed up to {backup_dir / '2-target'}")
        
        # Backup Phase 3
        if self.legacy_vectorstore_path.exists():
            shutil.copytree(self.legacy_vectorstore_path, backup_dir / "vectorstore")
            logger.info(f"Phase 3 data backed up to {backup_dir / 'vectorstore'}")
        
        logger.info(f"Backup completed in: {backup_dir}")
    
    def _migrate_phase1_data(self, step: Dict[str, Any], channel_id: str) -> List[MigrationResult]:
        """Migrate Phase 1 data"""
        logger.info(f"Migrating Phase 1 data to channel {channel_id}")
        
        source_path = Path(step['source_path'])
        target_path = Path(step['target_path'])
        target_path.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        # Migrate video directories
        for item in source_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                # Check if it's a video directory
                metadata_file = item / "metadata.json"
                if metadata_file.exists():
                    try:
                        # Copy entire video directory
                        target_dir = target_path / item.name
                        if target_dir.exists():
                            shutil.rmtree(target_dir)
                        shutil.copytree(item, target_dir)
                        
                        # Read video ID for result
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        results.append(MigrationResult(
                            success=True,
                            source_path=str(item),
                            target_path=str(target_dir),
                            data_type="phase1_video",
                            video_id=metadata.get('id'),
                            channel_id=channel_id
                        ))
                        
                        logger.debug(f"Migrated video directory: {item.name}")
                        
                    except Exception as e:
                        logger.error(f"Failed to migrate video directory {item.name}: {e}")
                        results.append(MigrationResult(
                            success=False,
                            source_path=str(item),
                            target_path=str(target_path / item.name),
                            error_message=str(e),
                            data_type="phase1_video",
                            channel_id=channel_id
                        ))
        
        # Migrate channel summaries
        for summary_file in source_path.glob("channel_summary_*.json"):
            try:
                target_file = target_path / summary_file.name
                shutil.copy2(summary_file, target_file)
                
                results.append(MigrationResult(
                    success=True,
                    source_path=str(summary_file),
                    target_path=str(target_file),
                    data_type="phase1_summary",
                    channel_id=channel_id
                ))
                
                logger.debug(f"Migrated channel summary: {summary_file.name}")
                
            except Exception as e:
                logger.error(f"Failed to migrate channel summary {summary_file.name}: {e}")
                results.append(MigrationResult(
                    success=False,
                    source_path=str(summary_file),
                    target_path=str(target_path / summary_file.name),
                    error_message=str(e),
                    data_type="phase1_summary",
                    channel_id=channel_id
                ))
        
        return results
    
    def _migrate_phase2_data(self, step: Dict[str, Any], channel_id: str) -> List[MigrationResult]:
        """Migrate Phase 2 data"""
        logger.info(f"Migrating Phase 2 data to channel {channel_id}")
        
        source_path = Path(step['source_path'])
        target_path = Path(step['target_path'])
        target_path.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        # Migrate enhanced files
        for enhanced_file in source_path.glob("*_enhanced.json"):
            try:
                target_file = target_path / enhanced_file.name
                
                # Read and update enhanced data with channel ID
                with open(enhanced_file, 'r', encoding='utf-8') as f:
                    enhanced_data = json.load(f)
                
                # Add channel ID to the enhanced data
                enhanced_data['channel_id'] = channel_id
                
                # Write updated data to target
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
                
                results.append(MigrationResult(
                    success=True,
                    source_path=str(enhanced_file),
                    target_path=str(target_file),
                    data_type="phase2_enhanced",
                    video_id=enhanced_data.get('video_id'),
                    channel_id=channel_id
                ))
                
                logger.debug(f"Migrated enhanced file: {enhanced_file.name}")
                
            except Exception as e:
                logger.error(f"Failed to migrate enhanced file {enhanced_file.name}: {e}")
                results.append(MigrationResult(
                    success=False,
                    source_path=str(enhanced_file),
                    target_path=str(target_path / enhanced_file.name),
                    error_message=str(e),
                    data_type="phase2_enhanced",
                    channel_id=channel_id
                ))
        
        # Migrate enhancement summaries
        for summary_file in source_path.glob("enhancement_summary_*.json"):
            try:
                target_file = target_path / summary_file.name
                shutil.copy2(summary_file, target_file)
                
                results.append(MigrationResult(
                    success=True,
                    source_path=str(summary_file),
                    target_path=str(target_file),
                    data_type="phase2_summary",
                    channel_id=channel_id
                ))
                
                logger.debug(f"Migrated enhancement summary: {summary_file.name}")
                
            except Exception as e:
                logger.error(f"Failed to migrate enhancement summary {summary_file.name}: {e}")
                results.append(MigrationResult(
                    success=False,
                    source_path=str(summary_file),
                    target_path=str(target_path / summary_file.name),
                    error_message=str(e),
                    data_type="phase2_summary",
                    channel_id=channel_id
                ))
        
        return results
    
    def _migrate_phase3_data(self, step: Dict[str, Any], channel_id: str) -> List[MigrationResult]:
        """Migrate Phase 3 data"""
        logger.info(f"Migrating Phase 3 data to channel {channel_id}")
        
        source_path = Path(step['source_path'])
        target_path = Path(step['target_path'])
        target_path.mkdir(parents=True, exist_ok=True)
        
        results = []
        
        try:
            # Copy entire vector store directory
            for item in source_path.iterdir():
                if item.is_file():
                    target_file = target_path / item.name
                    shutil.copy2(item, target_file)
                elif item.is_dir():
                    target_dir = target_path / item.name
                    if target_dir.exists():
                        shutil.rmtree(target_dir)
                    shutil.copytree(item, target_dir)
            
            # Update build info with channel ID
            build_info_file = target_path / "build_info.json"
            if build_info_file.exists():
                with open(build_info_file, 'r', encoding='utf-8') as f:
                    build_info = json.load(f)
                
                build_info['channel_id'] = channel_id
                build_info['migrated_at'] = datetime.now().isoformat()
                build_info['migration_source'] = str(source_path)
                
                with open(build_info_file, 'w', encoding='utf-8') as f:
                    json.dump(build_info, f, ensure_ascii=False, indent=2)
            
            results.append(MigrationResult(
                success=True,
                source_path=str(source_path),
                target_path=str(target_path),
                data_type="phase3_vectorstore",
                channel_id=channel_id
            ))
            
            logger.debug(f"Migrated vector store to channel {channel_id}")
            
        except Exception as e:
            logger.error(f"Failed to migrate vector store: {e}")
            results.append(MigrationResult(
                success=False,
                source_path=str(source_path),
                target_path=str(target_path),
                error_message=str(e),
                data_type="phase3_vectorstore",
                channel_id=channel_id
            ))
        
        return results
    
    def verify_migration(self, summary: MigrationSummary) -> Dict[str, Any]:
        """Verify migration integrity"""
        logger.info("Verifying migration integrity...")
        
        verification = {
            'channel_id': summary.default_channel_id,
            'phase1_verification': self._verify_phase1_migration(summary),
            'phase2_verification': self._verify_phase2_migration(summary),
            'phase3_verification': self._verify_phase3_migration(summary),
            'verified_at': datetime.now().isoformat()
        }
        
        # Overall verification status
        verification['overall_success'] = all([
            verification['phase1_verification']['success'],
            verification['phase2_verification']['success'],
            verification['phase3_verification']['success']
        ])
        
        return verification
    
    def _verify_phase1_migration(self, summary: MigrationSummary) -> Dict[str, Any]:
        """Verify Phase 1 migration"""
        phase1_results = [r for r in summary.phase1_results if r.success]
        
        if not phase1_results:
            return {'success': False, 'message': 'No Phase 1 data to verify - migration not executed'}
        
        channel_id = summary.default_channel_id
        target_path = self.config.get_channel_phase1_path(channel_id)
        
        verified_count = 0
        for result in phase1_results:
            if result.data_type == "phase1_video":
                # Verify video directory structure
                video_dir = Path(result.target_path)
                if (video_dir.exists() and 
                    (video_dir / "metadata.json").exists() and
                    (video_dir / "summary.json").exists()):
                    verified_count += 1
        
        return {
            'success': verified_count == len([r for r in phase1_results if r.data_type == "phase1_video"]),
            'verified_items': verified_count,
            'total_items': len([r for r in phase1_results if r.data_type == "phase1_video"]),
            'target_path': str(target_path)
        }
    
    def _verify_phase2_migration(self, summary: MigrationSummary) -> Dict[str, Any]:
        """Verify Phase 2 migration"""
        phase2_results = [r for r in summary.phase2_results if r.success]
        
        if not phase2_results:
            return {'success': False, 'message': 'No Phase 2 data to verify - migration not executed'}
        
        channel_id = summary.default_channel_id
        target_path = self.config.get_channel_phase2_path(channel_id)
        
        verified_count = 0
        for result in phase2_results:
            if result.data_type == "phase2_enhanced":
                # Verify enhanced file exists and has channel_id
                enhanced_file = Path(result.target_path)
                if enhanced_file.exists():
                    try:
                        with open(enhanced_file, 'r', encoding='utf-8') as f:
                            enhanced_data = json.load(f)
                        if enhanced_data.get('channel_id') == channel_id:
                            verified_count += 1
                    except Exception:
                        pass
        
        return {
            'success': verified_count == len([r for r in phase2_results if r.data_type == "phase2_enhanced"]),
            'verified_items': verified_count,
            'total_items': len([r for r in phase2_results if r.data_type == "phase2_enhanced"]),
            'target_path': str(target_path)
        }
    
    def _verify_phase3_migration(self, summary: MigrationSummary) -> Dict[str, Any]:
        """Verify Phase 3 migration"""
        phase3_results = [r for r in summary.phase3_results if r.success]
        
        if not phase3_results:
            return {'success': False, 'message': 'No Phase 3 data to verify - migration not executed'}
        
        channel_id = summary.default_channel_id
        target_path = self.config.get_channel_vectorstore_path(channel_id)
        
        # Verify vector store structure
        success = (target_path.exists() and 
                  (target_path / "build_info.json").exists() and
                  (target_path / "chroma.sqlite3").exists())
        
        return {
            'success': success,
            'verified_items': 1 if success else 0,
            'total_items': 1,
            'target_path': str(target_path)
        }
    
    def generate_migration_report(self, summary: MigrationSummary, verification: Dict[str, Any]) -> str:
        """Generate detailed migration report"""
        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("DATA MIGRATION REPORT")
        report_lines.append("=" * 60)
        report_lines.append(f"Started: {summary.started_at}")
        report_lines.append(f"Completed: {summary.completed_at}")
        report_lines.append(f"Target Channel: {summary.default_channel_id}")
        report_lines.append("")
        
        # Summary
        report_lines.append("SUMMARY")
        report_lines.append("-" * 20)
        report_lines.append(f"Total Items: {summary.total_items}")
        report_lines.append(f"Successful: {summary.successful_items}")
        report_lines.append(f"Failed: {summary.failed_items}")
        report_lines.append(f"Success Rate: {(summary.successful_items / summary.total_items * 100):.1f}%" if summary.total_items > 0 else "N/A")
        report_lines.append("")
        
        # Phase details
        for phase, results in [
            ("Phase 1", summary.phase1_results),
            ("Phase 2", summary.phase2_results),
            ("Phase 3", summary.phase3_results)
        ]:
            if results:
                report_lines.append(f"{phase.upper()}")
                report_lines.append("-" * 20)
                successful = len([r for r in results if r.success])
                report_lines.append(f"Successful: {successful}/{len(results)}")
                
                failed_results = [r for r in results if not r.success]
                if failed_results:
                    report_lines.append("Failed items:")
                    for result in failed_results:
                        report_lines.append(f"  - {result.source_path}: {result.error_message}")
                report_lines.append("")
        
        # Verification
        report_lines.append("VERIFICATION")
        report_lines.append("-" * 20)
        report_lines.append(f"Overall Success: {verification['overall_success']}")
        for phase in ['phase1', 'phase2', 'phase3']:
            phase_verify = verification[f'{phase}_verification']
            if 'verified_items' in phase_verify:
                report_lines.append(f"{phase.upper()}: {phase_verify['verified_items']}/{phase_verify['total_items']} verified")
        
        return "\n".join(report_lines)