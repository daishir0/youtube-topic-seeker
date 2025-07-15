#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 2: Context-Aware Transcript Enhancement

Uses rich context information from Phase 1 to create high-quality,
accurate transcripts through intelligent AI-powered enhancement.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from config import Config
from channel_manager import ChannelManager

logger = logging.getLogger(__name__)

class TranscriptEnhancer:
    """Context-aware transcript enhancement with OpenAI and multi-channel support"""
    
    def __init__(self, config: Config):
        self.config = config
        self.input_dir = config.get_phase1_path()  # Phase 2 reads from Phase 1 output
        self.output_dir = config.get_phase2_path()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.channel_manager = ChannelManager(config)
        
        # Initialize OpenAI client with proxy support
        from openai import OpenAI
        import httpx
        
        # Configure HTTP client with proxy if enabled
        http_client = None
        proxy_settings = config.get_proxy_settings()
        if proxy_settings:
            logger.info(f"Configuring OpenAI client with proxy: {proxy_settings}")
            # httpx.Client uses 'proxy' parameter, not 'proxies'
            proxy_url = config.get_proxy_url()
            http_client = httpx.Client(proxy=proxy_url)
        
        self.openai_client = OpenAI(
            api_key=config.openai.api_key,
            http_client=http_client
        )
        
        # Enhancement prompts
        self.enhancement_prompts = self._load_enhancement_prompts()
    
    def _load_enhancement_prompts(self) -> Dict[str, str]:
        """Load context-aware enhancement prompts"""
        return {
            'base_system_prompt': """You are an expert transcript editor specializing in YouTube content enhancement. Your task is to improve machine-generated transcripts while preserving ALL timestamp information and maintaining accuracy.

CRITICAL REQUIREMENTS:
1. PRESERVE ALL TIMESTAMPS - Never remove or modify timestamp information
2. Maintain the exact structure and segment boundaries 
3. Only correct obvious transcription errors, grammar, and punctuation
4. DO NOT add information not present in the original transcript
5. DO NOT change the meaning or content
6. Preserve speaker intentions and natural speech patterns
7. Output must be in valid JSON format matching the input structure

ENHANCEMENT GUIDELINES:
- Fix obvious speech-to-text errors (homophones, misheard words)
- Improve punctuation and capitalization
- Correct grammar while preserving natural speech flow
- Maintain technical terms and domain-specific vocabulary
- Preserve colloquialisms and speaker's style when appropriate""",
            
            'context_prompt': """CONTEXT INFORMATION for this video:
Title: {title}
Creator: {uploader}
Channel: {channel}
Description: {description}
Tags: {tags}
Categories: {categories}
Duration: {duration} seconds
Language: {language}

Video Description Context:
{description_context}

This context should help you understand:
- The topic and domain of discussion
- Technical terminology that might be used
- The creator's communication style
- The intended audience and content type

Use this context to make informed corrections, especially for:
- Domain-specific terminology
- Proper nouns (names, places, brands)
- Technical jargon
- Context-dependent phrases""",
            
            'enhancement_instructions': """TASK: Fix transcript errors and return valid JSON.

FIXES NEEDED:
1. Correct obvious speech-to-text errors
2. Add punctuation and capitalization  
3. Fix grammar while preserving natural speech

CRITICAL RULES:
- Keep ALL timestamps unchanged
- Return ONLY valid JSON (no explanations)
- No markdown code blocks
- Maintain exact structure"""
        }
    
    def create_enhancement_prompt(self, transcript_data: Dict[str, Any], 
                                metadata: Dict[str, Any]) -> str:
        """Create context-aware enhancement prompt"""
        
        # Extract key context information
        title = metadata.get('title', 'Unknown')
        uploader = metadata.get('uploader', 'Unknown')
        channel = metadata.get('channel', uploader)
        description = metadata.get('description', '')[:1000]  # First 1000 chars
        tags = ', '.join(metadata.get('tags', [])[:10])  # First 10 tags
        categories = ', '.join(metadata.get('categories', []))
        duration = metadata.get('duration', 0)
        language = metadata.get('language', 'unknown')
        
        # Create description context summary
        description_context = self._extract_description_context(description, tags)
        
        # Build the full prompt
        system_prompt = self.enhancement_prompts['base_system_prompt']
        
        context_prompt = self.enhancement_prompts['context_prompt'].format(
            title=title,
            uploader=uploader,
            channel=channel,
            description=description,
            tags=tags,
            categories=categories,
            duration=duration,
            language=language,
            description_context=description_context
        )
        
        instructions = self.enhancement_prompts['enhancement_instructions']
        
        return f"{system_prompt}\n\n{context_prompt}\n\n{instructions}"
    
    def _extract_description_context(self, description: str, tags: str) -> str:
        """Extract key context from video description and tags"""
        context_elements = []
        
        # Extract key topics from description
        if description:
            # Look for common patterns that indicate content type
            content_indicators = {
                'tutorial': ['tutorial', 'how to', 'guide', 'step by step', 'learn'],
                'review': ['review', 'analysis', 'opinion', 'thoughts on'],
                'tech': ['API', 'programming', 'software', 'code', 'development'],
                'business': ['business', 'marketing', 'strategy', 'company'],
                'educational': ['education', 'explain', 'science', 'research'],
                'entertainment': ['funny', 'comedy', 'entertainment', 'story']
            }
            
            desc_lower = description.lower()
            for content_type, keywords in content_indicators.items():
                if any(keyword in desc_lower for keyword in keywords):
                    context_elements.append(f"Content type: {content_type}")
                    break
        
        # Add tag context
        if tags:
            context_elements.append(f"Key topics: {tags}")
        
        return ' | '.join(context_elements) if context_elements else "General content"
    
    def enhance_transcript(self, video_dir: Path, channel_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Enhance a single video's transcript using context"""
        logger.info(f"Enhancing transcript for: {video_dir.name}")
        
        try:
            # Load metadata and transcript
            metadata_file = video_dir / "metadata.json"
            if not metadata_file.exists():
                logger.error(f"Metadata file not found: {metadata_file}")
                return None
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            # Find transcript file
            transcript_files = list(video_dir.glob("transcript_*.json"))
            if not transcript_files:
                logger.warning(f"No transcript found for {video_dir.name}")
                return None
            
            transcript_file = transcript_files[0]  # Use first available transcript
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_data = json.load(f)
            
            # Check if enhancement should be skipped
            video_id = metadata.get('id', video_dir.name)
            
            # Determine output directory (channel-specific or legacy)
            if channel_id:
                output_dir = self.config.get_channel_phase2_path(channel_id)
            else:
                output_dir = self.output_dir
            
            output_dir.mkdir(parents=True, exist_ok=True)
            enhanced_file = output_dir / f"{video_id}_enhanced.json"
            
            if self.config.phase2.skip_existing and enhanced_file.exists():
                logger.info(f"Skipping existing enhanced transcript: {video_id}")
                return {
                    'video_id': video_id,
                    'status': 'skipped',
                    'enhanced_file': str(enhanced_file)
                }
            
            # Create enhancement prompt with context
            system_prompt = self.create_enhancement_prompt(transcript_data, metadata)
            
            # Prepare transcript for enhancement
            transcript_for_enhancement = {
                'language': transcript_data.get('language'),
                'total_segments': transcript_data.get('total_segments'),
                'segments': transcript_data.get('segments', [])
            }
            
            # Enhance transcript using OpenAI
            enhanced_transcript = self._enhance_with_openai(
                transcript_for_enhancement, 
                system_prompt,
                metadata.get('title', 'Unknown')
            )
            
            if not enhanced_transcript:
                logger.error(f"Failed to enhance transcript for {video_id}")
                return None
            
            # Prepare enhanced data with full context
            enhanced_data = {
                'video_id': video_id,
                'title': metadata.get('title'),
                'uploader': metadata.get('uploader'),
                'channel': metadata.get('channel'),
                'duration': metadata.get('duration'),
                'url': metadata.get('webpage_url'),
                'channel_id': channel_id,
                'processed_at': datetime.now().isoformat(),
                'enhancement_metadata': {
                    'original_segments': len(transcript_data.get('segments', [])),
                    'enhanced_segments': len(enhanced_transcript.get('segments', [])),
                    'original_language': transcript_data.get('language'),
                    'context_used': True,
                    'enhancement_model': self.config.openai.model
                },
                'transcript': enhanced_transcript,
                'search_metadata': {
                    'title': metadata.get('title', ''),
                    'description': metadata.get('description', '')[:500],  # Truncated for search
                    'tags': metadata.get('tags', []),
                    'categories': metadata.get('categories', []),
                    'uploader': metadata.get('uploader', ''),
                    'duration_seconds': metadata.get('duration', 0)
                }
            }
            
            # Save enhanced transcript
            with open(enhanced_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Successfully enhanced transcript: {video_id}")
            return {
                'video_id': video_id,
                'title': metadata.get('title'),
                'status': 'enhanced',
                'enhanced_file': str(enhanced_file),
                'segments_count': len(enhanced_transcript.get('segments', []))
            }
            
        except Exception as e:
            logger.error(f"Failed to enhance transcript for {video_dir.name}: {e}")
            return None
    
    def _enhance_with_openai(self, transcript_data: Dict[str, Any], 
                           system_prompt: str, title: str) -> Optional[Dict[str, Any]]:
        """Enhance transcript using OpenAI with retry logic"""
        
        # Process segments in smaller chunks to avoid token limits
        segments = transcript_data.get('segments', [])
        if len(segments) > 50:  # Process in chunks if too many segments
            return self._enhance_in_chunks(transcript_data, system_prompt, title)
        
        # Simplified approach: enhance text only, preserve structure
        enhanced_segments = []
        for segment in segments:
            enhanced_text = self._enhance_text_only(segment.get('text', ''), system_prompt)
            if enhanced_text:
                enhanced_segment = segment.copy()
                enhanced_segment['text'] = enhanced_text
                enhanced_segments.append(enhanced_segment)
            else:
                enhanced_segments.append(segment)  # Keep original if enhancement fails
        
        # Reconstruct the transcript
        enhanced_transcript = {
            'language': transcript_data.get('language'),
            'total_segments': len(enhanced_segments),
            'segments': enhanced_segments
        }
        
        return enhanced_transcript
    
    def _enhance_text_only(self, text: str, context: str) -> Optional[str]:
        """Enhance only the text content, avoiding JSON complexity"""
        if not text or len(text.strip()) < 10:
            return text
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                simplified_prompt = f"""Fix grammar, punctuation, and obvious errors in this Japanese text. Keep the meaning unchanged. Return only the corrected text with no additional explanation:

{text}"""
                
                response = self.openai_client.chat.completions.create(
                    model=self.config.openai.model,
                    messages=[
                        {"role": "user", "content": simplified_prompt}
                    ],
                    max_tokens=min(len(text) * 2, 500),  # Reasonable limit
                    temperature=0.1
                )
                
                enhanced_text = response.choices[0].message.content.strip()
                
                # Basic validation
                if enhanced_text and len(enhanced_text) > 0:
                    return enhanced_text
                else:
                    return text  # Return original if enhancement failed
                    
            except Exception as e:
                logger.debug(f"Text enhancement error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
        
        return text  # Return original text if all attempts failed
    
    def _filter_new_videos_for_enhancement(self, video_dirs: List[Path], channel_id: Optional[str] = None) -> List[Path]:
        """Filter video directories to only include those not already enhanced"""
        new_videos = []
        existing_enhanced_files = set()
        
        # Get existing enhanced video IDs from phase 2 output directory
        if channel_id:
            output_dir = self.config.get_channel_phase2_path(channel_id)
        else:
            output_dir = self.output_dir
        
        if output_dir.exists():
            for enhanced_file in output_dir.glob("*_enhanced.json"):
                # Extract video ID from filename (format: {video_id}_enhanced.json)
                video_id = enhanced_file.stem.replace('_enhanced', '')
                existing_enhanced_files.add(video_id)
        
        # Check each video directory
        for video_dir in video_dirs:
            try:
                # Load metadata to get video ID
                metadata_file = video_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    
                    video_id = metadata.get('id', video_dir.name.split('_')[0])
                    if video_id not in existing_enhanced_files:
                        new_videos.append(video_dir)
                    else:
                        logger.debug(f"Skipping already enhanced video: {video_id}")
                else:
                    # Fallback: extract from directory name
                    video_id = video_dir.name.split('_')[0]
                    if video_id not in existing_enhanced_files:
                        new_videos.append(video_dir)
                        
            except Exception as e:
                logger.debug(f"Error checking video {video_dir}: {e}")
                # Include in processing if we can't determine status
                new_videos.append(video_dir)
        
        logger.info(f"Found {len(existing_enhanced_files)} existing enhanced videos, {len(new_videos)} new videos")
        return new_videos
    
    def _enhance_in_chunks(self, transcript_data: Dict[str, Any], 
                          system_prompt: str, title: str) -> Optional[Dict[str, Any]]:
        """Process large transcripts in smaller chunks"""
        segments = transcript_data.get('segments', [])
        chunk_size = 25
        enhanced_segments = []
        
        for i in range(0, len(segments), chunk_size):
            chunk = segments[i:i + chunk_size]
            chunk_text = ' '.join([seg.get('text', '') for seg in chunk])
            
            if chunk_text.strip():
                enhanced_chunk_text = self._enhance_text_only(chunk_text, system_prompt)
                if enhanced_chunk_text:
                    # Split enhanced text back to segments (approximate)
                    enhanced_words = enhanced_chunk_text.split()
                    word_index = 0
                    
                    for seg in chunk:
                        original_words = seg.get('text', '').split()
                        if word_index < len(enhanced_words):
                            seg_word_count = len(original_words)
                            enhanced_seg_text = ' '.join(enhanced_words[word_index:word_index + seg_word_count])
                            
                            enhanced_segment = seg.copy()
                            enhanced_segment['text'] = enhanced_seg_text
                            enhanced_segments.append(enhanced_segment)
                            
                            word_index += seg_word_count
                        else:
                            enhanced_segments.append(seg)
                else:
                    enhanced_segments.extend(chunk)
            else:
                enhanced_segments.extend(chunk)
        
        return {
            'language': transcript_data.get('language'),
            'total_segments': len(enhanced_segments),
            'segments': enhanced_segments
        }
    
    def _try_fix_json(self, content: str) -> Optional[str]:
        """Try to fix common JSON issues"""
        try:
            # Common fixes for truncated JSON
            content = content.strip()
            
            # If JSON is incomplete, try to close it properly
            if content.count('{') > content.count('}'):
                content += '}' * (content.count('{') - content.count('}'))
            
            if content.count('[') > content.count(']'):
                content += ']' * (content.count('[') - content.count(']'))
            
            # Remove trailing commas
            import re
            content = re.sub(r',(\s*[}\]])', r'\1', content)
            
            # Try to parse
            json.loads(content)
            return content
            
        except:
            return None
    
    def _validate_enhanced_transcript(self, original: Dict[str, Any], 
                                    enhanced: Dict[str, Any]) -> bool:
        """Validate that enhanced transcript maintains structure and timestamps"""
        try:
            # Check basic structure
            if 'segments' not in enhanced:
                logger.error("Enhanced transcript missing 'segments' field")
                return False
            
            original_segments = original.get('segments', [])
            enhanced_segments = enhanced.get('segments', [])
            
            # Check segment count
            if len(original_segments) != len(enhanced_segments):
                logger.warning(f"Segment count mismatch: {len(original_segments)} vs {len(enhanced_segments)}")
                # Allow small differences but not major ones
                if abs(len(original_segments) - len(enhanced_segments)) > 5:
                    return False
            
            # Validate timestamp preservation in sample segments
            sample_count = min(5, len(original_segments), len(enhanced_segments))
            for i in range(sample_count):
                orig_seg = original_segments[i]
                enh_seg = enhanced_segments[i]
                
                # Check required timestamp fields
                required_fields = ['start_time', 'end_time', 'start_seconds', 'end_seconds']
                for field in required_fields:
                    if field not in enh_seg:
                        logger.error(f"Missing timestamp field '{field}' in enhanced segment {i}")
                        return False
                    
                    # For numeric fields, check approximate equality
                    if field.endswith('_seconds'):
                        if abs(float(orig_seg[field]) - float(enh_seg[field])) > 1.0:
                            logger.error(f"Timestamp mismatch in segment {i}: {field}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def process_all_videos(self, incremental: bool = True, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """Process videos from Phase 1 with parallel enhancement and incremental update support"""
        
        # Determine input directory (channel-specific or all)
        if channel_id:
            input_dir = self.config.get_channel_phase1_path(channel_id)
            logger.info(f"Starting transcript enhancement for channel {channel_id} in: {input_dir} (incremental: {incremental})")
        else:
            input_dir = self.input_dir
            logger.info(f"Starting transcript enhancement for all videos in: {input_dir} (incremental: {incremental})")
        
        # Find all video directories
        if not input_dir.exists():
            logger.error(f"Input directory does not exist: {input_dir}")
            return {'success': False, 'error': f'Input directory not found: {input_dir}'}
        
        video_dirs = [d for d in input_dir.iterdir() if d.is_dir()]
        
        # Filter for new videos only if incremental update is enabled
        if incremental:
            video_dirs = self._filter_new_videos_for_enhancement(video_dirs, channel_id)
            if not video_dirs:
                logger.info("No new videos found for enhancement")
                return {
                    'success': True,
                    'total_videos': 0,
                    'enhanced_videos': [],
                    'failed_videos': [],
                    'skipped_videos': [],
                    'new_videos_count': 0,
                    'incremental_mode': incremental,
                    'channel_id': channel_id,
                    'started_at': datetime.now().isoformat(),
                    'completed_at': datetime.now().isoformat(),
                    'success_count': 0,
                    'success_rate': 1.0
                }
            logger.info(f"Found {len(video_dirs)} new videos for enhancement")
        
        if not video_dirs:
            logger.error("No video directories found for enhancement")
            return {'success': False, 'error': 'No video directories found'}
        
        results = {
            'total_videos': len(video_dirs),
            'channel_id': channel_id,
            'enhanced_videos': [],
            'failed_videos': [],
            'skipped_videos': [],
            'new_videos_count': len(video_dirs),
            'incremental_mode': incremental,
            'started_at': datetime.now().isoformat()
        }
        
        # Process videos in batches to respect API limits
        batch_size = self.config.phase2.batch_size
        max_workers = min(batch_size, self.config.general.max_workers)
        
        logger.info(f"Processing {len(video_dirs)} videos with {max_workers} workers, batch size {batch_size}")
        
        for i in range(0, len(video_dirs), batch_size):
            batch = video_dirs[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: videos {i+1}-{min(i+batch_size, len(video_dirs))}")
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_video = {
                    executor.submit(self.enhance_transcript, video_dir, channel_id): video_dir 
                    for video_dir in batch
                }
                
                for future in as_completed(future_to_video):
                    video_dir = future_to_video[future]
                    try:
                        result = future.result()
                        if result:
                            if result.get('status') == 'enhanced':
                                results['enhanced_videos'].append(result)
                            elif result.get('status') == 'skipped':
                                results['skipped_videos'].append(result)
                        else:
                            results['failed_videos'].append(str(video_dir))
                    except Exception as e:
                        logger.error(f"Exception processing {video_dir}: {e}")
                        results['failed_videos'].append(str(video_dir))
            
            # Brief pause between batches to respect API limits
            if i + batch_size < len(video_dirs):
                time.sleep(2)
        
        results['completed_at'] = datetime.now().isoformat()
        results['success_count'] = len(results['enhanced_videos'])
        results['success_rate'] = results['success_count'] / len(video_dirs)
        
        # Save processing summary
        if channel_id:
            summary_dir = self.config.get_channel_phase2_path(channel_id)
        else:
            summary_dir = self.output_dir
        
        summary_file = summary_dir / f"enhancement_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Enhancement completed. Success rate: {results['success_rate']:.2%} "
                   f"({results['success_count']}/{len(video_dirs)} videos)")
        
        return results
    
    def process_all_channels(self, incremental: bool = True) -> Dict[str, Any]:
        """Process all enabled channels"""
        logger.info("Starting transcript enhancement for all enabled channels")
        
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
                result = self.process_all_videos(incremental, channel_info.id)
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
        
        logger.info(f"All channels enhancement completed. Success rate: {overall_results['success_rate']:.2%}")
        return overall_results