#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3: RAG-based Topic Search for YouTube Videos

Implements intelligent topic search with timestamp-aware retrieval
and ranked results by relevance.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import re
from urllib.parse import quote

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import BaseRetriever

from config import Config
from channel_manager import ChannelManager

logger = logging.getLogger(__name__)

class TopicSearchRAG:
    """RAG-based topic search with timestamp-aware results and multi-channel support"""
    
    def __init__(self, config: Config):
        self.config = config
        self.input_dir = config.get_phase2_path()  # Phase 3 reads from Phase 2 output
        self.vectorstore_dir = config.get_vectorstore_path()
        self.vectorstore_dir.mkdir(parents=True, exist_ok=True)
        self.channel_manager = ChannelManager(config)
        
        # Initialize components with proxy support
        import httpx
        
        # Configure HTTP client with proxy if enabled
        http_client = None
        proxy_settings = config.get_proxy_settings()
        if proxy_settings:
            logger.info(f"Configuring LangChain OpenAI with proxy: {proxy_settings}")
            # httpx.Client uses 'proxy' parameter, not 'proxies'
            proxy_url = config.get_proxy_url()
            http_client = httpx.Client(proxy=proxy_url)
        
        self.llm = ChatOpenAI(
            model=config.rag.llm_model,
            temperature=config.rag.llm_temperature,
            openai_api_key=config.openai.api_key,
            http_client=http_client
        )
        
        self.embeddings = OpenAIEmbeddings(
            model=config.rag.embedding_model,
            openai_api_key=config.openai.api_key,
            http_client=http_client
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.rag.chunk_size,
            chunk_overlap=config.rag.chunk_overlap,
            separators=["\\n\\n", "\\n", ". ", " "]
        )
        
        self.vectorstore = None
        self.video_metadata = {}  # Cache for video metadata
    
    def _filter_new_enhanced_files(self, enhanced_files: List[Path], channel_id: Optional[str] = None) -> List[Path]:
        """Filter enhanced files to only include new ones not already in vector store"""
        new_files = []
        
        # Check if vector store exists and has build info
        if channel_id:
            build_info_file = self.config.get_channel_vectorstore_path(channel_id) / "build_info.json"
        else:
            build_info_file = self.vectorstore_dir / "build_info.json"
        
        processed_video_ids = set()
        
        if build_info_file.exists():
            try:
                with open(build_info_file, 'r', encoding='utf-8') as f:
                    build_info = json.load(f)
                
                # Get processed video IDs from previous builds
                if 'processed_video_ids' in build_info:
                    processed_video_ids = set(build_info['processed_video_ids'])
                else:
                    # Legacy support: reconstruct from existing vector store
                    vectorstore_dir = build_info_file.parent
                    if vectorstore_dir.exists():
                        try:
                            temp_vectorstore = Chroma(
                                persist_directory=str(vectorstore_dir),
                                embedding_function=self.embeddings
                            )
                            # Get all documents and extract video IDs
                            all_docs = temp_vectorstore.get()
                            for metadata in all_docs['metadatas']:
                                if 'video_id' in metadata:
                                    processed_video_ids.add(metadata['video_id'])
                        except Exception as e:
                            logger.debug(f"Could not load existing vector store: {e}")
                            
            except Exception as e:
                logger.debug(f"Could not read build info: {e}")
        
        # Filter for new files
        for file_path in enhanced_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    video_data = json.load(f)
                
                video_id = video_data.get('video_id')
                if video_id and video_id not in processed_video_ids:
                    new_files.append(file_path)
                else:
                    logger.debug(f"Skipping already processed video: {video_id}")
                    
            except Exception as e:
                logger.debug(f"Error reading enhanced file {file_path}: {e}")
                # Include in processing if we can't determine status
                new_files.append(file_path)
        
        logger.info(f"Found {len(processed_video_ids)} existing videos in vector store, {len(new_files)} new videos")
        return new_files
    
    def build_vectorstore(self, incremental: bool = True, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """Build vector store from enhanced transcripts with incremental update support"""
        
        # Determine input and output directories
        if channel_id:
            input_dir = self.config.get_channel_phase2_path(channel_id)
            vectorstore_dir = self.config.get_channel_vectorstore_path(channel_id)
            logger.info(f"Building vector store for channel {channel_id} from: {input_dir} (incremental: {incremental})")
        else:
            input_dir = self.input_dir
            vectorstore_dir = self.vectorstore_dir
            logger.info(f"Building vector store from: {input_dir} (incremental: {incremental})")
        
        vectorstore_dir.mkdir(parents=True, exist_ok=True)
        
        # Load all enhanced transcripts with multi-channel support
        if not input_dir.exists():
            logger.error(f"Input directory does not exist: {input_dir}")
            return {'success': False, 'error': f'Input directory not found: {input_dir}'}
        
        # Collect enhanced files from all channels if no specific channel is specified
        enhanced_files = []
        
        if channel_id:
            # Single channel mode
            enhanced_files = list(input_dir.glob("*_enhanced.json"))
        else:
            # Multi-channel mode: scan all channel directories
            def scan_for_enhanced_files(base_dir: Path) -> List[Path]:
                """Scan for enhanced files in multi-channel structure"""
                files = []
                
                # New structure: channel subdirectories only
                for item in base_dir.iterdir():
                    if item.is_dir():
                        # Check if this directory contains enhanced files
                        channel_enhanced_files = list(item.glob("*_enhanced.json"))
                        if channel_enhanced_files:
                            files.extend(channel_enhanced_files)
                            logger.debug(f"Found {len(channel_enhanced_files)} enhanced files in channel directory: {item.name}")
                
                return files
            
            enhanced_files = scan_for_enhanced_files(input_dir)
            logger.info(f"Found {len(enhanced_files)} enhanced files across all channels")
        
        # Filter for new files only if incremental update is enabled
        if incremental:
            new_enhanced_files = self._filter_new_enhanced_files(enhanced_files, channel_id)
            if not new_enhanced_files:
                logger.info("No new enhanced files found for vector store update")
                return {
                    'success': True,
                    'incremental_mode': True,
                    'channel_id': channel_id,
                    'build_info': {
                        'total_videos': 0,
                        'total_segments': 0,
                        'total_chunks': 0,
                        'new_videos_count': 0,
                        'built_at': datetime.now().isoformat()
                    }
                }
            enhanced_files = new_enhanced_files
            logger.info(f"Found {len(enhanced_files)} new enhanced files for vector store update")
        
        if not enhanced_files:
            logger.error("No enhanced transcript files found")
            return {'success': False, 'error': 'No enhanced files found'}
        
        documents = []
        video_count = 0
        segment_count = 0
        
        for file_path in enhanced_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    video_data = json.load(f)
                
                video_docs, segments = self._process_video_for_vectorstore(video_data)
                documents.extend(video_docs)
                video_count += 1
                segment_count += segments
                
                # Cache metadata for quick lookup
                video_id = video_data.get('video_id')
                self.video_metadata[video_id] = {
                    'title': video_data.get('title'),
                    'uploader': video_data.get('uploader'),
                    'channel': video_data.get('channel'),
                    'duration': video_data.get('duration'),
                    'url': video_data.get('url')
                }
                
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                continue
        
        if not documents:
            logger.error("No documents created for vector store")
            return {'success': False, 'error': 'No documents created'}
        
        # Create vector store with batch processing for embeddings
        try:
            # Handle incremental vs full rebuild
            if incremental and vectorstore_dir.exists():
                # Load existing vector store for incremental update
                logger.info("Loading existing vector store for incremental update")
                vectorstore = Chroma(
                    persist_directory=str(vectorstore_dir),
                    embedding_function=self.embeddings
                )
            else:
                # Clear existing vector store if it exists (full rebuild)
                import shutil
                if vectorstore_dir.exists():
                    shutil.rmtree(vectorstore_dir)
                    vectorstore_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("Cleared existing vector store for full rebuild")
                
                # Initialize empty vector store first
                vectorstore = Chroma(
                    persist_directory=str(vectorstore_dir),
                    embedding_function=self.embeddings
                )
            
            # Process documents in batches to avoid token limits
            batch_size = 50  # Process 50 documents at a time to stay under token limits
            
            # Add documents in batches
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: documents {i+1}-{min(i+batch_size, len(documents))}")
                
                # Calculate approximate token count for this batch
                batch_text = ' '.join([doc.page_content for doc in batch])
                approx_tokens = len(batch_text.split()) * 1.3  # Rough estimate
                
                # If batch is still too large, reduce batch size
                if approx_tokens > 200000:  # Leave margin below 300k limit
                    smaller_batch_size = max(1, int(100 * 200000 / approx_tokens))
                    logger.warning(f"Batch too large ({approx_tokens:.0f} tokens), reducing to {smaller_batch_size} documents")
                    
                    # Process in smaller sub-batches
                    for j in range(0, len(batch), smaller_batch_size):
                        sub_batch = batch[j:j + smaller_batch_size]
                        self._add_documents_with_retry(vectorstore, sub_batch, f"sub-batch {j//smaller_batch_size + 1}")
                else:
                    self._add_documents_with_retry(vectorstore, batch, f"batch {i//batch_size + 1}")
            
            logger.info(f"Vector store created with {len(documents)} chunks from {video_count} videos")
            
            # Collect processed video IDs for incremental updates
            processed_video_ids = []
            for file_path in enhanced_files:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        video_data = json.load(f)
                    video_id = video_data.get('video_id')
                    if video_id:
                        processed_video_ids.append(video_id)
                except Exception as e:
                    logger.debug(f"Error reading video ID from {file_path}: {e}")
            
            # Load existing build info if incremental update
            existing_processed_ids = []
            build_info_file = vectorstore_dir / "build_info.json"
            if incremental and build_info_file.exists():
                try:
                    with open(build_info_file, 'r', encoding='utf-8') as f:
                        existing_build_info = json.load(f)
                    existing_processed_ids = existing_build_info.get('processed_video_ids', [])
                except Exception as e:
                    logger.debug(f"Could not load existing build info: {e}")
            
            # Combine existing and new processed IDs
            all_processed_ids = list(set(existing_processed_ids + processed_video_ids))
            
            # Save build metadata
            build_info = {
                'built_at': datetime.now().isoformat(),
                'total_videos': video_count,
                'total_segments': segment_count,
                'total_chunks': len(documents),
                'new_videos_count': len(processed_video_ids),
                'incremental_mode': incremental,
                'channel_id': channel_id,
                'processed_video_ids': all_processed_ids,
                'config': {
                    'chunk_size': self.config.rag.chunk_size,
                    'chunk_overlap': self.config.rag.chunk_overlap,
                    'embedding_model': self.config.rag.embedding_model
                }
            }
            
            build_info_file = vectorstore_dir / "build_info.json"
            with open(build_info_file, 'w', encoding='utf-8') as f:
                json.dump(build_info, f, ensure_ascii=False, indent=2)
            
            # Update the instance vectorstore if this is the legacy/default path
            if not channel_id:
                self.vectorstore = vectorstore
            
            return {'success': True, 'build_info': build_info}
            
        except Exception as e:
            logger.error(f"Failed to create vector store: {e}")
            return {'success': False, 'error': str(e)}
    
    def _add_documents_with_retry(self, vectorstore: Chroma, documents: List[Document], batch_name: str, max_retries: int = 3):
        """Add documents to vector store with retry logic for token limit errors"""
        import time
        
        for attempt in range(max_retries):
            try:
                vectorstore.add_documents(documents)
                logger.debug(f"Successfully added {batch_name}: {len(documents)} documents")
                return
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a token limit error
                if "max_tokens_per_request" in error_msg:
                    logger.warning(f"Token limit exceeded for {batch_name}, attempt {attempt + 1}/{max_retries}")
                    
                    if attempt < max_retries - 1:
                        # Split the batch in half and try again
                        mid = len(documents) // 2
                        if mid > 0:
                            logger.info(f"Splitting {batch_name} into smaller parts")
                            self._add_documents_with_retry(vectorstore, documents[:mid], f"{batch_name}_part1", max_retries - 1)
                            self._add_documents_with_retry(vectorstore, documents[mid:], f"{batch_name}_part2", max_retries - 1)
                            return
                        else:
                            logger.error(f"Cannot split {batch_name} further - single document too large")
                            continue
                    else:
                        logger.error(f"Failed to add {batch_name} after {max_retries} attempts: {error_msg}")
                        raise
                else:
                    logger.error(f"Failed to add {batch_name}: {error_msg}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    else:
                        raise
    
    def _process_video_for_vectorstore(self, video_data: Dict[str, Any]) -> Tuple[List[Document], int]:
        """Process a single video's data for vector store"""
        documents = []
        video_id = video_data.get('video_id')
        title = video_data.get('title', '')
        uploader = video_data.get('uploader', '')
        url = video_data.get('url', '')
        
        transcript = video_data.get('transcript', {})
        segments = transcript.get('segments', [])
        
        if not segments:
            logger.warning(f"No transcript segments found for video: {video_id}")
            return documents, 0
        
        # Create chunks from transcript segments with timestamp preservation
        current_chunk = ""
        current_start_time = None
        current_start_seconds = None
        chunk_segments = []
        
        for i, segment in enumerate(segments):
            segment_text = segment.get('text', '').strip()
            if not segment_text:
                continue
            
            # Start new chunk if needed
            if current_start_time is None:
                current_start_time = segment.get('start_time')
                current_start_seconds = segment.get('start_seconds', 0)
                chunk_segments = []
            
            # Add segment to current chunk
            if current_chunk:
                current_chunk += " "
            current_chunk += segment_text
            chunk_segments.append(segment)
            
            # Check if chunk should be completed
            chunk_length = len(current_chunk)
            next_segment_exists = i + 1 < len(segments)
            
            if (chunk_length >= self.config.rag.chunk_size or 
                not next_segment_exists or
                (next_segment_exists and chunk_length >= self.config.rag.chunk_size - self.config.rag.chunk_overlap)):
                
                # Create document for this chunk
                end_time = segment.get('end_time')
                end_seconds = segment.get('end_seconds', current_start_seconds)
                
                # Create YouTube URL with timestamp
                timestamp_url = self._create_timestamp_url(url, current_start_seconds)
                
                doc = Document(
                    page_content=current_chunk,
                    metadata={
                        'video_id': video_id,
                        'title': title,
                        'uploader': uploader,
                        'url': url,
                        'timestamp_url': timestamp_url,
                        'start_time': current_start_time,
                        'end_time': end_time,
                        'start_seconds': current_start_seconds,
                        'end_seconds': end_seconds,
                        'segment_count': len(chunk_segments),
                        'chunk_type': 'transcript_segment'
                    }
                )
                documents.append(doc)
                
                # Prepare for next chunk with overlap
                if next_segment_exists and self.config.rag.chunk_overlap > 0:
                    # Keep last part of current chunk for overlap
                    overlap_text = current_chunk[-self.config.rag.chunk_overlap:]
                    overlap_start_idx = max(0, len(chunk_segments) - 3)  # Keep last few segments
                    
                    current_chunk = overlap_text
                    current_start_time = chunk_segments[overlap_start_idx].get('start_time')
                    current_start_seconds = chunk_segments[overlap_start_idx].get('start_seconds', 0)
                    chunk_segments = chunk_segments[overlap_start_idx:]
                else:
                    current_chunk = ""
                    current_start_time = None
                    current_start_seconds = None
                    chunk_segments = []
        
        # Add any remaining content as final chunk
        if current_chunk.strip():
            end_segment = segments[-1] if segments else {}
            timestamp_url = self._create_timestamp_url(url, current_start_seconds)
            
            doc = Document(
                page_content=current_chunk,
                metadata={
                    'video_id': video_id,
                    'title': title,
                    'uploader': uploader,
                    'url': url,
                    'timestamp_url': timestamp_url,
                    'start_time': current_start_time,
                    'end_time': end_segment.get('end_time'),
                    'start_seconds': current_start_seconds,
                    'end_seconds': end_segment.get('end_seconds', current_start_seconds),
                    'segment_count': len(chunk_segments),
                    'chunk_type': 'transcript_segment'
                }
            )
            documents.append(doc)
        
        logger.debug(f"Created {len(documents)} chunks for video: {title}")
        return documents, len(segments)
    
    def _create_timestamp_url(self, video_url: str, start_seconds: Optional[float]) -> str:
        """Create YouTube URL with timestamp parameter"""
        if not start_seconds or start_seconds <= 0:
            return video_url
        
        # Convert seconds to YouTube's time format
        seconds = int(start_seconds)
        if '?' in video_url:
            return f"{video_url}&t={seconds}s"
        else:
            return f"{video_url}?t={seconds}s"
    
    def load_vectorstore(self) -> bool:
        """Load existing vector store"""
        try:
            if not self.vectorstore_dir.exists():
                logger.error(f"Vector store directory does not exist: {self.vectorstore_dir}")
                return False
            
            self.vectorstore = Chroma(
                persist_directory=str(self.vectorstore_dir),
                embedding_function=self.embeddings
            )
            
            # Load video metadata cache
            self._load_video_metadata()
            
            logger.info("Vector store loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load vector store: {e}")
            return False
    
    def _load_video_metadata(self):
        """Load video metadata from enhanced files for quick lookup"""
        enhanced_files = list(self.input_dir.glob("*_enhanced.json"))
        
        for file_path in enhanced_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    video_data = json.load(f)
                
                video_id = video_data.get('video_id')
                self.video_metadata[video_id] = {
                    'title': video_data.get('title'),
                    'uploader': video_data.get('uploader'),
                    'channel': video_data.get('channel'),
                    'duration': video_data.get('duration'),
                    'url': video_data.get('url')
                }
            except Exception as e:
                logger.debug(f"Could not load metadata from {file_path}: {e}")
    
    def search_topics(self, query: str, max_results: int = 10, channel_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for topics across all videos with ranked results"""
        
        # Determine which vector store to use
        if channel_id:
            # Channel-specific search
            vectorstore_path = self.config.get_channel_vectorstore_path(channel_id)
            if not vectorstore_path.exists():
                logger.error(f"No vector store found for channel: {channel_id}")
                return []
            
            vectorstore = Chroma(
                persist_directory=str(vectorstore_path),
                embedding_function=self.embeddings
            )
            logger.info(f"Searching in channel {channel_id} for topic: '{query}'")
        else:
            # Legacy single vector store or unified search
            if not self.vectorstore:
                logger.error("Vector store not loaded. Call load_vectorstore() or build_vectorstore() first.")
                return []
            vectorstore = self.vectorstore
            logger.info(f"Searching for topic: '{query}'")
        
        try:
            # Retrieve relevant documents
            docs_with_scores = vectorstore.similarity_search_with_score(
                query, 
                k=max_results * 2  # Get more results for better ranking
            )
            
            # Filter by relevance threshold
            relevant_docs = []
            for doc, score in docs_with_scores:
                # Lower score means higher similarity in Chroma
                relevance = 1.0 - score  # Convert to 0-1 where 1 is most relevant
                if relevance >= self.config.rag.similarity_threshold:
                    relevant_docs.append((doc, relevance))
            
            if not relevant_docs:
                logger.info(f"No relevant results found for query: '{query}'")
                return []
            
            # Sort by relevance (highest first)
            relevant_docs.sort(key=lambda x: x[1], reverse=True)
            
            # Take top results
            relevant_docs = relevant_docs[:max_results]
            
            # Generate topic summaries for each result
            results = []
            for doc, relevance in relevant_docs:
                try:
                    topic_summary = self._generate_topic_summary(doc.page_content, query)
                    
                    result = {
                        'title': doc.metadata.get('title', 'Unknown'),
                        'topic_summary': topic_summary,
                        'timestamp_url': doc.metadata.get('timestamp_url', doc.metadata.get('url', '')),
                        'relevance_score': round(relevance, 3),
                        'uploader': doc.metadata.get('uploader', 'Unknown'),
                        'start_time': doc.metadata.get('start_time', ''),
                        'start_seconds': doc.metadata.get('start_seconds', 0),
                        'content_preview': doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                        'channel_id': channel_id
                    }
                    results.append(result)
                    
                except Exception as e:
                    logger.error(f"Failed to process search result: {e}")
                    continue
            
            logger.info(f"Found {len(results)} relevant results for query: '{query}'")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_unified(self, query: str, max_results: int = 10, channel_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search across all channels with unified results"""
        logger.info(f"Starting unified search for: '{query}'")
        
        enabled_channels = self.channel_manager.get_enabled_channels()
        if not enabled_channels:
            logger.warning("No enabled channels found")
            return []
        
        all_results = []
        
        for channel_info in enabled_channels:
            # Skip if channel filter is specified and doesn't match
            if channel_filter and channel_filter != channel_info.id:
                continue
            
            try:
                # Search in this channel
                channel_results = self.search_topics(query, max_results * 2, channel_info.id)
                
                # Add channel information to results
                for result in channel_results:
                    result['channel_name'] = channel_info.name
                    result['channel_id'] = channel_info.id
                
                all_results.extend(channel_results)
                
            except Exception as e:
                logger.error(f"Failed to search in channel {channel_info.name}: {e}")
                continue
        
        # Sort all results by relevance
        all_results.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Take top results
        unified_results = all_results[:max_results]
        
        logger.info(f"Found {len(unified_results)} unified results across {len(enabled_channels)} channels")
        return unified_results
    
    def _generate_topic_summary(self, content: str, query: str) -> str:
        """Generate AI-powered topic summary for the content"""
        try:
            # Detect if query is in Japanese and use appropriate prompt
            import re
            has_japanese = bool(re.search(r'[あ-ん]|[ア-ン]|[一-龯]', query))
            
            if has_japanese:
                prompt = f"""以下の文字起こし内容とユーザーの質問に基づいて、質問に関連する具体的なトピックについて、1-2文で簡潔に日本語で要約してください。

ユーザーの質問: "{query}"

文字起こし内容:
{content[:1000]}  

この部分で議論されている具体的なトピック/話題の要約を日本語で提供してください:"""
            else:
                prompt = f"""Based on the following transcript content and user query, provide a concise 1-2 sentence summary of what specific topic is being discussed that relates to the query.

User Query: "{query}"

Transcript Content:
{content[:1000]}  

Provide a focused summary of the specific topic/subject being discussed in this segment:"""

            response = self.llm.invoke(prompt)
            summary = response.content.strip()
            
            # Fix encoding issues and clean up the summary
            summary = self._fix_encoding_issues(summary)
            
            # Clean up the summary
            if len(summary) > 150:
                summary = summary[:147] + "..."
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate topic summary: {e}")
            # Fallback: extract key sentences related to the query
            return self._extract_key_sentences(content, query)
    
    def _fix_encoding_issues(self, text: str) -> str:
        """Fix common encoding issues in text responses"""
        if not text:
            return text
        
        # Replace common problematic characters
        text = text.replace('��', '')  # Remove replacement characters
        
        # Fix common encoding issues
        replacements = {
            '\\u2019': "'",  # Right single quotation mark
            '\\u201c': '"',  # Left double quotation mark
            '\\u201d': '"',  # Right double quotation mark
            '\\u2013': '-',  # En dash
            '\\u2014': '-',  # Em dash
            '\\u2026': '...',  # Horizontal ellipsis
            '\\uff1a': ':',  # Fullwidth colon
            '\\uff0c': ',',  # Fullwidth comma
            '\\uff01': '!',  # Fullwidth exclamation mark
            '\\uff1f': '?',  # Fullwidth question mark
        }
        
        for old, new in replacements.items():
            text = text.replace(old, new)
        
        # Remove any remaining unprintable characters
        import re
        text = re.sub(r'[^\x20-\x7E\u3000-\u303F\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\uFF00-\uFFEF]', '', text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _extract_key_sentences(self, content: str, query: str) -> str:
        """Fallback method to extract key sentences related to the query"""
        import re
        
        # Split by Japanese and English punctuation
        sentences = re.split(r'[.!?。！？]+', content)
        
        # Check if query is in Japanese
        has_japanese = bool(re.search(r'[あ-ん]|[ア-ン]|[一-龯]', query))
        
        if has_japanese:
            # For Japanese queries, use character-based matching
            query_chars = set(query.lower())
            
            relevant_sentences = []
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 10:  # Skip very short sentences
                    continue
                    
                sentence_chars = set(sentence.lower())
                overlap = len(query_chars.intersection(sentence_chars))
                
                if overlap > 0:
                    relevant_sentences.append((sentence, overlap))
            
            if relevant_sentences:
                # Sort by character overlap and take the best sentence
                relevant_sentences.sort(key=lambda x: x[1], reverse=True)
                return self._fix_encoding_issues(relevant_sentences[0][0])
        else:
            # For English queries, use word-based matching
            query_words = set(query.lower().split())
            
            relevant_sentences = []
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 10:  # Skip very short sentences
                    continue
                    
                sentence_words = set(sentence.lower().split())
                overlap = len(query_words.intersection(sentence_words))
                
                if overlap > 0:
                    relevant_sentences.append((sentence, overlap))
            
            if relevant_sentences:
                # Sort by word overlap and take the best sentence
                relevant_sentences.sort(key=lambda x: x[1], reverse=True)
                return self._fix_encoding_issues(relevant_sentences[0][0])
        
        # Return first meaningful sentence
        for sentence in sentences:
            if len(sentence.strip()) > 20:
                return self._fix_encoding_issues(sentence.strip())
        
        result = content[:100] + "..." if len(content) > 100 else content
        return self._fix_encoding_issues(result)
    
    def build_all_channels(self, incremental: bool = True) -> Dict[str, Any]:
        """Build vector stores for all enabled channels"""
        logger.info("Starting vector store build for all enabled channels")
        
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
            logger.info(f"Building vector store for channel: {channel_info.name} ({channel_info.id})")
            
            try:
                result = self.build_vectorstore(incremental, channel_info.id)
                result['channel_name'] = channel_info.name
                
                if result.get('success'):
                    overall_results['processed_channels'].append(result)
                else:
                    overall_results['failed_channels'].append({
                        'channel_id': channel_info.id,
                        'channel_name': channel_info.name,
                        'error': result.get('error', 'Unknown error')
                    })
            except Exception as e:
                logger.error(f"Failed to build vector store for channel {channel_info.name}: {e}")
                overall_results['failed_channels'].append({
                    'channel_id': channel_info.id,
                    'channel_name': channel_info.name,
                    'error': str(e)
                })
        
        overall_results['completed_at'] = datetime.now().isoformat()
        overall_results['success_rate'] = len(overall_results['processed_channels']) / len(enabled_channels)
        
        logger.info(f"All channels vector store build completed. Success rate: {overall_results['success_rate']:.2%}")
        return overall_results