#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube Topic Seeker - Main Interactive Interface

A comprehensive system for downloading YouTube videos, enhancing transcripts,
and searching for topics with timestamp-precise results.
"""

import sys
import logging
import argparse
from pathlib import Path
from typing import Optional
import smtplib
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import Config
from phase1_downloader import YouTubeDownloader
from phase2_enhancer import TranscriptEnhancer
from phase3_rag import TopicSearchRAG
from channel_manager import ChannelManager
from data_migrator import DataMigrator

class YouTubeTopicSeeker:
    """Main application class for YouTube topic searching"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the application"""
        try:
            self.config = Config(config_path)
            self.config.setup_logging()
            self.logger = logging.getLogger(__name__)
            
            # Initialize components
            self.downloader = YouTubeDownloader(self.config)
            self.enhancer = TranscriptEnhancer(self.config)
            self.rag = TopicSearchRAG(self.config)
            self.channel_manager = ChannelManager(self.config)
            self.data_migrator = DataMigrator(self.config)
            
            self.logger.info("YouTube Topic Seeker initialized successfully")
            
        except Exception as e:
            print(f"Failed to initialize application: {e}")
            sys.exit(1)
    
    def run_interactive(self, send_email: bool = False):
        """Run interactive mode"""
        print("\\n" + "="*60)
        print("🎯 YouTube Topic Seeker - Interactive Mode")
        print("="*60)
        
        while True:
            try:
                choice = self._show_main_menu()
                
                if choice == '1':
                    self._run_phase1_interactive()
                elif choice == '2':
                    self._run_phase2_interactive()
                elif choice == '3':
                    self._run_phase3_interactive()
                elif choice == '4':
                    self._run_full_pipeline_interactive()
                elif choice == '5':
                    self._search_topics_interactive()
                elif choice == '6':
                    self._show_status()
                elif choice == '7':
                    self._channel_management_interactive()
                elif choice == '8':
                    self._data_migration_interactive()
                elif choice == '9':
                    if send_email:
                        self._send_completion_email("Interactive session completed")
                    print("\\n👋 Thanks for using YouTube Topic Seeker!")
                    break
                else:
                    print("❌ Invalid choice. Please try again.")
                    
            except KeyboardInterrupt:
                print("\\n\\n🛑 Operation interrupted by user.")
                if send_email:
                    self._send_completion_email("Session interrupted by user")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in interactive mode: {e}")
                print(f"❌ Unexpected error: {e}")
    
    def run_automatic(self, channel_url: str, send_email: bool = False):
        """Run automatic processing for a specific channel"""
        print("="*60)
        print("🎯 YouTube Topic Seeker - Automatic Mode")
        print("="*60)
        print(f"📺 Processing channel: {channel_url}")
        
        try:
            # Phase 1: Download channel data
            print("📥 Phase 1: Downloading videos...")
            results1 = self.downloader.process_channel(channel_url, incremental=True)
            if results1.get('success_rate', 0) == 0:
                print("❌ Phase 1 failed, stopping pipeline")
                return
            
            new_videos = len(results1['processed_videos'])
            print(f"✅ Phase 1 completed: {new_videos} new videos processed")
            
            if new_videos == 0:
                print("ℹ️ No new videos found, pipeline completed")
                return
            
            # Phase 2: Enhance transcripts
            print("✨ Phase 2: Enhancing transcripts...")
            results2 = self.enhancer.process_all_videos(incremental=True)
            if results2.get('success_count', 0) == 0:
                print("❌ Phase 2 failed, stopping pipeline")
                return
            
            print(f"✅ Phase 2 completed: {results2['success_count']} enhanced transcripts")
            
            # Phase 3: Build vector store
            print("🏗️ Phase 3: Building vector store...")
            results3 = self.rag.build_vectorstore(incremental=True)
            if not results3.get('success'):
                print(f"❌ Phase 3 failed: {results3.get('error')}")
                return
            
            print("✅ Phase 3 completed: Vector store updated")
            print("🎉 Full pipeline completed successfully!")
            print("🔍 You can now search for topics in your videos.")
            
            if send_email:
                self._send_completion_email(f"Automatic processing of {channel_url} completed")
                
        except Exception as e:
            self.logger.error(f"Automatic processing failed: {e}")
            print(f"❌ Automatic processing failed: {e}")
            if send_email:
                self._send_completion_email(f"Automatic processing of {channel_url} failed: {e}")
    
    def _show_main_menu(self) -> str:
        """Show main menu and get user choice"""
        print("\\n" + "-"*40)
        print("📋 Main Menu")
        print("-"*40)
        print("1. 📥 Phase 1: Download YouTube Data")
        print("2. ✨ Phase 2: Enhance Transcripts") 
        print("3. 🏗️  Phase 3: Build Vector Store")
        print("4. 🚀 Run Full Pipeline")
        print("5. 🔍 Search Topics")
        print("6. 📊 Show Status")
        print("7. 📺 Channel Management")
        print("8. 🔄 Data Migration")
        print("9. 🚪 Exit")
        print("-"*40)
        
        return input("\\n➤ Choose an option (1-9): ").strip()
    
    def _run_phase1_interactive(self):
        """Interactive Phase 1 execution"""
        print("\\n" + "="*50)
        print("📥 Phase 1: YouTube Data Download")
        print("="*50)
        
        channel_url = input("\\n➤ Enter YouTube channel URL: ").strip()
        if not channel_url:
            print("❌ Channel URL is required")
            return
        
        print("\\n🔄 Starting download process...")
        print("⏱️  This may take several minutes depending on channel size...")
        
        try:
            results = self.downloader.process_channel(channel_url, incremental=True)
            
            if results.get('success_rate', 0) > 0:
                print(f"\\n✅ Download completed!")
                if results.get('incremental_mode', False):
                    print(f"📊 New videos processed: {len(results['processed_videos'])}")
                    print(f"📈 Success rate: {results['success_rate']:.1%}")
                    if results.get('skipped_videos'):
                        print(f"⏭️  Existing videos skipped: {len(results['skipped_videos'])}")
                else:
                    print(f"📊 Processed: {len(results['processed_videos'])}/{results['total_videos']} videos")
                    print(f"📈 Success rate: {results['success_rate']:.1%}")
                
                if results['failed_videos']:
                    print(f"⚠️  Failed videos: {len(results['failed_videos'])}")
            else:
                print("❌ Download failed. Check logs for details.")
                
        except Exception as e:
            self.logger.error(f"Phase 1 failed: {e}")
            print(f"❌ Download failed: {e}")
    
    def _run_phase2_interactive(self):
        """Interactive Phase 2 execution"""
        print("\\n" + "="*50)
        print("✨ Phase 2: Transcript Enhancement")
        print("="*50)
        
        # Check if Phase 1 data exists
        if not any(self.config.get_phase1_path().glob("*")):
            print("❌ No Phase 1 data found. Please run Phase 1 first.")
            return
        
        confirm = input("\\n➤ Enhance all downloaded transcripts? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Enhancement cancelled")
            return
        
        print("\\n🔄 Starting transcript enhancement...")
        print("⏱️  This may take several minutes and will use OpenAI API...")
        
        try:
            results = self.enhancer.process_all_videos(incremental=True)
            
            if results.get('success_count', 0) > 0:
                print(f"\\n✅ Enhancement completed!")
                if results.get('incremental_mode', False):
                    print(f"📊 New videos enhanced: {results['success_count']}")
                    print(f"📈 Success rate: {results['success_rate']:.1%}")
                else:
                    print(f"📊 Enhanced: {results['success_count']}/{results['total_videos']} videos")
                    print(f"📈 Success rate: {results['success_rate']:.1%}")
                
                if results['failed_videos']:
                    print(f"⚠️  Failed videos: {len(results['failed_videos'])}")
                if results['skipped_videos']:
                    print(f"⏭️  Skipped videos: {len(results['skipped_videos'])}")
            else:
                print("❌ Enhancement failed. Check logs for details.")
                
        except Exception as e:
            self.logger.error(f"Phase 2 failed: {e}")
            print(f"❌ Enhancement failed: {e}")
    
    def _run_phase3_interactive(self):
        """Interactive Phase 3 execution"""
        print("\\n" + "="*50)
        print("🏗️ Phase 3: Build Vector Store")
        print("="*50)
        
        # Check if Phase 2 data exists
        enhanced_files = list(self.config.get_phase2_path().glob("*_enhanced.json"))
        if not enhanced_files:
            print("❌ No enhanced transcripts found. Please run Phase 2 first.")
            return
        
        print(f"📁 Found {len(enhanced_files)} enhanced transcript files")
        confirm = input("\\n➤ Build vector store for search? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Vector store build cancelled")
            return
        
        print("\\n🔄 Building vector store...")
        print("⏱️  This may take several minutes...")
        
        try:
            results = self.rag.build_vectorstore(incremental=True)
            
            if results.get('success'):
                build_info = results['build_info']
                print(f"\\n✅ Vector store built successfully!")
                if results.get('incremental_mode', False):
                    print(f"📊 New videos added: {build_info['new_videos_count']}")
                    print(f"📄 New chunks: {build_info['total_chunks']}")
                    print(f"🧩 New segments: {build_info['total_segments']}")
                else:
                    print(f"📊 Videos: {build_info['total_videos']}")
                    print(f"📄 Chunks: {build_info['total_chunks']}")
                    print(f"🧩 Segments: {build_info['total_segments']}")
            else:
                print(f"❌ Vector store build failed: {results.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Phase 3 failed: {e}")
            print(f"❌ Vector store build failed: {e}")
    
    def _run_full_pipeline_interactive(self):
        """Run the complete pipeline interactively"""
        print("\\n" + "="*50)
        print("🚀 Full Pipeline: All Phases")
        print("="*50)
        
        channel_url = input("\\n➤ Enter YouTube channel URL: ").strip()
        if not channel_url:
            print("❌ Channel URL is required")
            return
        
        confirm = input("\\n➤ Run complete pipeline? This will take significant time and API usage (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Pipeline cancelled")
            return
        
        print("\\n🔄 Starting full pipeline...")
        
        # Phase 1
        print("\\n📥 Phase 1: Downloading videos...")
        try:
            results1 = self.downloader.process_channel(channel_url, incremental=True)
            if results1.get('success_rate', 0) == 0:
                print("❌ Phase 1 failed, stopping pipeline")
                return
            new_videos = len(results1['processed_videos'])
            print(f"✅ Phase 1 completed: {new_videos} new videos processed")
            
            if new_videos == 0:
                print("ℹ️  No new videos found, pipeline completed")
                return
                
        except Exception as e:
            print(f"❌ Phase 1 failed: {e}")
            return
        
        # Phase 2
        print("\\n✨ Phase 2: Enhancing transcripts...")
        try:
            results2 = self.enhancer.process_all_videos(incremental=True)
            if results2.get('success_count', 0) == 0:
                print("❌ Phase 2 failed, stopping pipeline")
                return
            print(f"✅ Phase 2 completed: {results2['success_count']} enhanced transcripts")
        except Exception as e:
            print(f"❌ Phase 2 failed: {e}")
            return
        
        # Phase 3
        print("\\n🏗️ Phase 3: Building vector store...")
        try:
            results3 = self.rag.build_vectorstore(incremental=True)
            if not results3.get('success'):
                print(f"❌ Phase 3 failed: {results3.get('error')}")
                return
            print("✅ Phase 3 completed: Vector store updated")
        except Exception as e:
            print(f"❌ Phase 3 failed: {e}")
            return
        
        print("\\n🎉 Full pipeline completed successfully!")
        print("🔍 You can now search for topics in your videos.")
    
    def _search_topics_interactive(self):
        """Interactive topic search with unified and channel-specific options"""
        print("\\n" + "="*50)
        print("🔍 Topic Search")
        print("="*50)
        
        # Check if we have any channels configured
        enabled_channels = self.channel_manager.get_enabled_channels()
        
        if not enabled_channels:
            # Fall back to legacy single vector store search
            print("📥 Loading vector store...")
            if not self.rag.load_vectorstore():
                print("❌ No vector store found. Please run Phase 3 first.")
                return
            
            self._legacy_search_interactive()
            return
        
        # Show search options
        print("\\n" + "-"*40)
        print("Search Options:")
        print("-"*40)
        print("1. 🌐 Unified Search (All Channels)")
        print("2. 📺 Channel-Specific Search")
        print("3. 🔙 Back to Main Menu")
        print("-"*40)
        
        choice = input("\\n➤ Choose search type (1-3): ").strip()
        
        if choice == '1':
            self._unified_search_interactive()
        elif choice == '2':
            self._channel_search_interactive()
        elif choice == '3':
            return
        else:
            print("❌ Invalid choice.")
    
    def _unified_search_interactive(self):
        """Interactive unified search across all channels"""
        print("\\n" + "="*50)
        print("🌐 Unified Search (All Channels)")
        print("="*50)
        
        enabled_channels = self.channel_manager.get_enabled_channels()
        print(f"\\n📺 Searching across {len(enabled_channels)} enabled channels:")
        for channel in enabled_channels:
            print(f"  • {channel.name}")
        
        while True:
            query = input("\\n➤ Enter your search query (or 'back' to return): ").strip()
            if not query or query.lower() == 'back':
                break
            
            max_results = input("➤ Maximum results (default 5): ").strip()
            try:
                max_results = int(max_results) if max_results else 5
                max_results = max(1, min(max_results, 20))
            except ValueError:
                max_results = 5
            
            print(f"\\n🔄 Searching across all channels for: '{query}'...")
            
            try:
                results = self.rag.search_unified(query, max_results)
                
                if results:
                    print(f"\\n✅ Found {len(results)} relevant results:")
                    print("="*60)
                    
                    for i, result in enumerate(results, 1):
                        print(f"\\n{i}. 📹 {result['title']}")
                        print(f"   📺 Channel: {result.get('channel_name', 'Unknown')}")
                        print(f"   👤 {result['uploader']}")
                        print(f"   📝 {result['topic_summary']}")
                        print(f"   🔗 {result['timestamp_url']}")
                        print(f"   📊 Relevance: {result['relevance_score']:.1%}")
                        print(f"   ⏰ Starts at: {result['start_time']}")
                        
                        if self.config.get_verbosity() >= 3:
                            print(f"   👁️  Preview: {result['content_preview']}")
                else:
                    print(f"\\n❌ No relevant results found for '{query}'")
                    print("💡 Try different keywords or check if your data is properly processed")
                    
            except Exception as e:
                self.logger.error(f"Unified search failed: {e}")
                print(f"❌ Search failed: {e}")
    
    def _channel_search_interactive(self):
        """Interactive channel-specific search"""
        channels = self.channel_manager.get_enabled_channels()
        if not channels:
            print("\\n❌ No enabled channels found.")
            return
        
        print("\\n" + "="*50)
        print("📺 Channel-Specific Search")
        print("="*50)
        
        # Show channels
        print("\\nSelect channel to search:")
        for i, channel in enumerate(channels, 1):
            print(f"  {i}. {channel.name} ({channel.video_count} videos)")
        
        try:
            choice = input("\\n➤ Enter channel number: ").strip()
            channel_index = int(choice) - 1
            
            if 0 <= channel_index < len(channels):
                channel = channels[channel_index]
                
                # Check if vector store exists
                vectorstore_path = self.config.get_channel_vectorstore_path(channel.id)
                if not vectorstore_path.exists():
                    print(f"❌ No vector store found for channel '{channel.name}'.")
                    print("💡 Please run Phase 3 first to build the vector store.")
                    return
                
                print(f"\\n🔍 Searching in channel: {channel.name}")
                
                # Perform search
                while True:
                    query = input(f"\\n➤ Enter search query for '{channel.name}' (or 'back' to return): ").strip()
                    if not query or query.lower() == 'back':
                        break
                    
                    max_results = input("➤ Maximum results (default 5): ").strip()
                    try:
                        max_results = int(max_results) if max_results else 5
                        max_results = max(1, min(max_results, 20))
                    except ValueError:
                        max_results = 5
                    
                    print(f"\\n🔄 Searching in '{channel.name}' for: '{query}'...")
                    
                    try:
                        results = self.rag.search_topics(query, max_results, channel.id)
                        
                        if results:
                            print(f"\\n✅ Found {len(results)} relevant results in '{channel.name}':")
                            print("="*60)
                            
                            for i, result in enumerate(results, 1):
                                print(f"\\n{i}. 📹 {result['title']}")
                                print(f"   👤 {result['uploader']}")
                                print(f"   📝 {result['topic_summary']}")
                                print(f"   🔗 {result['timestamp_url']}")
                                print(f"   📊 Relevance: {result['relevance_score']:.1%}")
                                print(f"   ⏰ Starts at: {result['start_time']}")
                                
                                if self.config.get_verbosity() >= 3:
                                    print(f"   👁️  Preview: {result['content_preview']}")
                        else:
                            print(f"\\n❌ No relevant results found for '{query}' in '{channel.name}'")
                            print("💡 Try different keywords or check if the channel data is properly processed")
                            
                    except Exception as e:
                        self.logger.error(f"Channel search failed: {e}")
                        print(f"❌ Search failed: {e}")
                    
            else:
                print("❌ Invalid channel number.")
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
    
    def _legacy_search_interactive(self):
        """Legacy search for single vector store"""
        while True:
            query = input("\\n➤ Enter your search query (or 'back' to return): ").strip()
            if not query or query.lower() == 'back':
                break
            
            max_results = input("➤ Maximum results (default 5): ").strip()
            try:
                max_results = int(max_results) if max_results else 5
                max_results = max(1, min(max_results, 20))
            except ValueError:
                max_results = 5
            
            print(f"\\n🔄 Searching for: '{query}'...")
            
            try:
                results = self.rag.search_topics(query, max_results)
                
                if results:
                    print(f"\\n✅ Found {len(results)} relevant results:")
                    print("="*60)
                    
                    for i, result in enumerate(results, 1):
                        print(f"\\n{i}. 📹 {result['title']}")
                        print(f"   👤 {result['uploader']}")
                        print(f"   📝 {result['topic_summary']}")
                        print(f"   🔗 {result['timestamp_url']}")
                        print(f"   📊 Relevance: {result['relevance_score']:.1%}")
                        print(f"   ⏰ Starts at: {result['start_time']}")
                        
                        if self.config.get_verbosity() >= 3:
                            print(f"   👁️  Preview: {result['content_preview']}")
                else:
                    print(f"\\n❌ No relevant results found for '{query}'")
                    print("💡 Try different keywords or check if your data is properly processed")
                    
            except Exception as e:
                self.logger.error(f"Search failed: {e}")
                print(f"❌ Search failed: {e}")
    
    def _show_status(self):
        """Show system status"""
        print("="*50)
        print("📊 System Status")
        print("="*50)
        
        # Channel status
        enabled_channels = self.channel_manager.get_enabled_channels()
        if enabled_channels:
            print(f"📺 Multi-Channel Mode: {len(enabled_channels)} enabled channels")
            
            for channel in enabled_channels:
                print(f"  📺 {channel.name} ({channel.id})")
                
                # Phase 1 status for this channel
                phase1_path = self.config.get_channel_phase1_path(channel.id)
                phase1_videos = len([d for d in phase1_path.glob("*") if d.is_dir()]) if phase1_path.exists() else 0
                print(f"     📥 Phase 1: {phase1_videos} video directories")
                
                # Phase 2 status for this channel
                phase2_path = self.config.get_channel_phase2_path(channel.id)
                phase2_files = len(list(phase2_path.glob("*_enhanced.json"))) if phase2_path.exists() else 0
                print(f"     ✨ Phase 2: {phase2_files} enhanced transcripts")
                
                # Phase 3 status for this channel
                vectorstore_path = self.config.get_channel_vectorstore_path(channel.id)
                build_info_file = vectorstore_path / "build_info.json"
                
                if vectorstore_path.exists() and build_info_file.exists():
                    try:
                        import json
                        with open(build_info_file, 'r') as f:
                            build_info = json.load(f)
                        print(f"     🏗️ Phase 3: Ready ({build_info.get('total_chunks', 0)} chunks)")
                    except:
                        print("     🏗️ Phase 3: Exists (details unavailable)")
                else:
                    print("     🏗️ Phase 3: Not built")
        else:
            # Legacy single-channel mode
            print("📺 Legacy Single-Channel Mode")
            
            # Phase 1 status
            phase1_dirs = list(self.config.get_phase1_path().glob("*"))
            phase1_videos = len([d for d in phase1_dirs if d.is_dir()])
            print(f"📥 Phase 1 (Raw Data): {phase1_videos} video directories")
            
            # Phase 2 status
            phase2_files = list(self.config.get_phase2_path().glob("*_enhanced.json"))
            print(f"✨ Phase 2 (Enhanced): {len(phase2_files)} enhanced transcripts")
            
            # Phase 3 status
            vectorstore_path = self.config.get_vectorstore_path()
            vectorstore_exists = vectorstore_path.exists()
            build_info_file = vectorstore_path / "build_info.json"
            
            if vectorstore_exists and build_info_file.exists():
                try:
                    import json
                    with open(build_info_file, 'r') as f:
                        build_info = json.load(f)
                    print(f"🏗️ Phase 3 (Vector Store): Ready ({build_info.get('total_chunks', 0)} chunks)")
                    print(f"   📅 Built: {build_info.get('built_at', 'Unknown')}")
                except:
                    print("🏗️ Phase 3 (Vector Store): Exists (details unavailable)")
            else:
                print("🏗️ Phase 3 (Vector Store): Not built")
        
        # Configuration status
        print(f"⚙️ Configuration:")
        print(f"   🤖 OpenAI Model: {self.config.openai.model}")
        print(f"   📁 Data Directory: {self.config.get_phase1_path()}")
        print(f"   🐛 Debug Mode: {self.config.general.debug}")
        print(f"   🌐 Proxy Enabled: {self.config.proxy.enabled}")
        if self.config.proxy.enabled:
            print(f"   🔀 Proxy: {self.config.proxy.type}://{self.config.proxy.host}:{self.config.proxy.port}")
        print(f"   📧 Email Notifications: {self.config.email.enabled}")
    
    def _send_completion_email(self, message: str):
        """Send completion notification email"""
        if not self.config.email.enabled:
            return
        
        try:
            from email.mime.text import MimeText
            from email.mime.multipart import MimeMultipart
            
            msg = MimeMultipart()
            msg['From'] = self.config.email.username
            msg['To'] = self.config.email.recipient
            msg['Subject'] = "YouTube Topic Seeker - Process Complete"
            
            body = f"""
YouTube Topic Seeker Notification

Status: {message}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

This is an automated notification from YouTube Topic Seeker.
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            server = smtplib.SMTP(self.config.email.smtp_server, self.config.email.smtp_port)
            server.starttls()
            server.login(self.config.email.username, self.config.email.password)
            server.send_message(msg)
            server.quit()
            
            self.logger.info("Completion email sent successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
    
    def _channel_management_interactive(self):
        """Interactive channel management"""
        while True:
            print("="*50)
            print("📺 Channel Management")
            print("="*50)
            
            # Show current channels
            channels = self.channel_manager.list_channels()
            if channels:
                print(f"📋 Current Channels ({len(channels)}):")
                for i, channel in enumerate(channels, 1):
                    status = "✅ Enabled" if channel.enabled else "❌ Disabled"
                    video_count = f"({channel.video_count} videos)" if channel.video_count > 0 else ""
                    print(f"  {i}. {channel.name} - {status} {video_count}")
                    print(f"     📺 {channel.url}")
            else:
                print("📋 No channels configured yet.")
            
            # Show menu
            print("-"*40)
            print("Channel Management Options:")
            print("-"*40)
            print("1. ➕ Add New Channel")
            print("2. ❌ Remove Channel")
            print("3. 🔄 Enable/Disable Channel")
            print("4. 📊 Show Channel Statistics")
            print("5. 🚀 Process All Channels")
            print("6. 🔍 Search Specific Channel")
            print("7. 🔙 Back to Main Menu")
            print("-"*40)
            
            choice = input("➤ Choose an option (1-7): ").strip()
            
            if choice == '1':
                self._add_channel_interactive()
            elif choice == '2':
                self._remove_channel_interactive()
            elif choice == '3':
                self._toggle_channel_interactive()
            elif choice == '4':
                self._show_channel_statistics()
            elif choice == '5':
                self._process_all_channels_interactive()
            elif choice == '6':
                self._search_channel_interactive()
            elif choice == '7':
                break
            else:
                print("❌ Invalid choice. Please try again.")
    
    def _add_channel_interactive(self):
        """Interactive channel addition"""
        print("="*50)
        print("➕ Add New Channel")
        print("="*50)
        
        channel_url = input("➤ Enter YouTube channel URL: ").strip()
        if not channel_url:
            print("❌ Channel URL is required")
            return
        
        channel_name = input("➤ Enter channel name (optional): ").strip()
        
        print("🔄 Adding channel...")
        
        try:
            channel_id = self.channel_manager.add_channel(channel_url, channel_name)
            if channel_id:
                print(f"✅ Channel added successfully!")
                print(f"📺 Channel ID: {channel_id}")
                print(f"📝 Name: {channel_name or channel_id}")
            else:
                print("❌ Failed to add channel. Please check the URL.")
        except Exception as e:
            print(f"❌ Error adding channel: {e}")
    
    def _remove_channel_interactive(self):
        """Interactive channel removal"""
        channels = self.channel_manager.list_channels()
        if not channels:
            print("❌ No channels to remove.")
            return
        
        print("="*50)
        print("❌ Remove Channel")
        print("="*50)
        
        # Show channels
        print("Select channel to remove:")
        for i, channel in enumerate(channels, 1):
            print(f"  {i}. {channel.name} ({channel.id})")
        
        try:
            choice = input("➤ Enter channel number: ").strip()
            channel_index = int(choice) - 1
            
            if 0 <= channel_index < len(channels):
                channel = channels[channel_index]
                
                # Confirm deletion
                print(f"⚠️  Are you sure you want to remove '{channel.name}'?")
                delete_data = input("➤ Delete associated data too? (y/N): ").strip().lower() == 'y'
                confirm = input("➤ Confirm removal (y/N): ").strip().lower() == 'y'
                
                if confirm:
                    if self.channel_manager.remove_channel(channel.id, delete_data):
                        print(f"✅ Channel '{channel.name}' removed successfully!")
                        if delete_data:
                            print("🗑️  Associated data deleted.")
                    else:
                        print("❌ Failed to remove channel.")
                else:
                    print("❌ Removal cancelled.")
            else:
                print("❌ Invalid channel number.")
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
    
    def _toggle_channel_interactive(self):
        """Interactive channel enable/disable"""
        channels = self.channel_manager.list_channels()
        if not channels:
            print("❌ No channels to toggle.")
            return
        
        print("="*50)
        print("🔄 Enable/Disable Channel")
        print("="*50)
        
        # Show channels
        print("Select channel to toggle:")
        for i, channel in enumerate(channels, 1):
            status = "✅ Enabled" if channel.enabled else "❌ Disabled"
            print(f"  {i}. {channel.name} - {status}")
        
        try:
            choice = input("➤ Enter channel number: ").strip()
            channel_index = int(choice) - 1
            
            if 0 <= channel_index < len(channels):
                channel = channels[channel_index]
                new_status = not channel.enabled
                
                self.channel_manager.enable_channel(channel.id, new_status)
                status_text = "enabled" if new_status else "disabled"
                print(f"✅ Channel '{channel.name}' {status_text}!")
            else:
                print("❌ Invalid channel number.")
        except ValueError:
            print("❌ Invalid input. Please enter a number.")
    
    def _show_channel_statistics(self):
        """Show channel statistics"""
        print("="*50)
        print("📊 Channel Statistics")
        print("="*50)
        
        stats = self.channel_manager.get_channel_statistics()
        
        print(f"📺 Total Channels: {stats['total_channels']}")
        print(f"✅ Enabled: {stats['enabled_channels']}")
        print(f"❌ Disabled: {stats['disabled_channels']}")
        print(f"🎥 Total Videos: {stats['total_videos']}")
        
        if stats['last_updated']:
            print(f"🕒 Last Updated: {stats['last_updated']}")
        
        # Show individual channel stats
        channels = self.channel_manager.list_channels()
        if channels:
            print("📋 Individual Channel Details:")
            for channel in channels:
                status = "✅" if channel.enabled else "❌"
                print(f"  {status} {channel.name}")
                print(f"     🎥 Videos: {channel.video_count}")
                if channel.last_updated:
                    print(f"     🕒 Last Updated: {channel.last_updated}")
    
    def _process_all_channels_interactive(self):
        """Interactive processing of all channels"""
        print("="*50)
        print("🚀 Process All Channels")
        print("="*50)
        
        enabled_channels = self.channel_manager.get_enabled_channels()
        if not enabled_channels:
            print("❌ No enabled channels found.")
            return
        
        print(f"📺 Found {len(enabled_channels)} enabled channels:")
        for channel in enabled_channels:
            print(f"  • {channel.name}")
        
        # Show processing options
        print("-"*40)
        print("Processing Options:")
        print("-"*40)
        print("1. 📥 Phase 1: Download All Channels")
        print("2. ✨ Phase 2: Enhance All Channels")
        print("3. 🏗️  Phase 3: Build Vector Stores")
        print("4. 🚀 Full Pipeline All Channels")
        print("5. 🔙 Back")
        print("-"*40)
        
        choice = input("➤ Choose processing option (1-5): ").strip()
        
        if choice == '1':
            self._process_all_channels_phase1()
        elif choice == '2':
            self._process_all_channels_phase2()
        elif choice == '3':
            self._process_all_channels_phase3()
        elif choice == '4':
            self._process_all_channels_full_pipeline()
        elif choice == '5':
            return
        else:
            print("❌ Invalid choice.")
    
    def _process_all_channels_phase1(self):
        """Process all channels - Phase 1"""
        print("🔄 Starting Phase 1 for all channels...")
        
        try:
            results = self.downloader.process_all_channels(incremental=True)
            
            if results.get('success_rate', 0) > 0:
                print(f"✅ Phase 1 completed for all channels!")
                print(f"📊 Processed: {len(results['processed_channels'])}/{results['total_channels']} channels")
                print(f"📈 Success rate: {results['success_rate']:.1%}")
                
                # Show summary for each channel
                for channel_result in results['processed_channels']:
                    print(f"  📺 {channel_result.get('channel_name', 'Unknown')}: {len(channel_result['processed_videos'])} videos")
                
                if results['failed_channels']:
                    print(f"⚠️  Failed channels: {len(results['failed_channels'])}")
                    for failed in results['failed_channels']:
                        print(f"  ❌ {failed['channel_name']}: {failed['error']}")
            else:
                print("❌ Phase 1 failed for all channels.")
                
        except Exception as e:
            print(f"❌ Phase 1 processing failed: {e}")
    
    def _process_all_channels_phase2(self):
        """Process all channels - Phase 2"""
        print("🔄 Starting Phase 2 for all channels...")
        
        try:
            results = self.enhancer.process_all_channels(incremental=True)
            
            if results.get('success_rate', 0) > 0:
                print(f"✅ Phase 2 completed for all channels!")
                print(f"📊 Processed: {len(results['processed_channels'])}/{results['total_channels']} channels")
                print(f"📈 Success rate: {results['success_rate']:.1%}")
                
                # Show summary for each channel
                for channel_result in results['processed_channels']:
                    print(f"  📺 {channel_result.get('channel_name', 'Unknown')}: {channel_result['success_count']} enhanced")
                
                if results['failed_channels']:
                    print(f"⚠️  Failed channels: {len(results['failed_channels'])}")
            else:
                print("❌ Phase 2 failed for all channels.")
                
        except Exception as e:
            print(f"❌ Phase 2 processing failed: {e}")
    
    def _process_all_channels_phase3(self):
        """Process all channels - Phase 3"""
        print("🔄 Starting Phase 3 for all channels...")
        
        try:
            results = self.rag.build_all_channels(incremental=True)
            
            if results.get('success_rate', 0) > 0:
                print(f"✅ Phase 3 completed for all channels!")
                print(f"📊 Processed: {len(results['processed_channels'])}/{results['total_channels']} channels")
                print(f"📈 Success rate: {results['success_rate']:.1%}")
                
                # Show summary for each channel
                for channel_result in results['processed_channels']:
                    build_info = channel_result.get('build_info', {})
                    print(f"  📺 {channel_result.get('channel_name', 'Unknown')}: {build_info.get('total_chunks', 0)} chunks")
                
                if results['failed_channels']:
                    print(f"⚠️  Failed channels: {len(results['failed_channels'])}")
            else:
                print("❌ Phase 3 failed for all channels.")
                
        except Exception as e:
            print(f"❌ Phase 3 processing failed: {e}")
    
    def _process_all_channels_full_pipeline(self):
        """Process all channels - Full Pipeline"""
        print("🔄 Starting full pipeline for all channels...")
        print("⚠️  This will take significant time and API usage!")
        
        confirm = input("➤ Continue with full pipeline? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ Pipeline cancelled.")
            return
        
        try:
            # Phase 1
            print("📥 Phase 1: Downloading all channels...")
            results1 = self.downloader.process_all_channels(incremental=True)
            if results1.get('success_rate', 0) == 0:
                print("❌ Phase 1 failed, stopping pipeline")
                return
            print(f"✅ Phase 1 completed: {len(results1['processed_channels'])} channels")
            
            # Phase 2
            print("✨ Phase 2: Enhancing all channels...")
            results2 = self.enhancer.process_all_channels(incremental=True)
            if results2.get('success_rate', 0) == 0:
                print("❌ Phase 2 failed, stopping pipeline")
                return
            print(f"✅ Phase 2 completed: {len(results2['processed_channels'])} channels")
            
            # Phase 3
            print("🏗️ Phase 3: Building vector stores...")
            results3 = self.rag.build_all_channels(incremental=True)
            if results3.get('success_rate', 0) == 0:
                print("❌ Phase 3 failed, stopping pipeline")
                return
            print("✅ Phase 3 completed: Vector stores updated")
            
            print("🎉 Full pipeline completed successfully for all channels!")
            print("🔍 You can now search across all channels.")
            
        except Exception as e:
            print(f"❌ Full pipeline failed: {e}")
    
    def _search_channel_interactive(self):
        """Interactive channel-specific search"""
        channels = self.channel_manager.get_enabled_channels()
        if not channels:
            print("❌ No enabled channels found.")
            return
        
        print("="*50)
        print("🔍 Search Specific Channel")
        print("="*50)
        
        # Show channels
        print("Select channel to search:")
        for i, channel in enumerate(channels, 1):
            print(f"  {i}. {channel.name} ({channel.video_count} videos)")
        
        try:
            choice = input("➤ Enter channel number: ").strip()
            channel_index = int(choice) - 1
            
            if 0 <= channel_index < len(channels):
                channel = channels[channel_index]
                
                # Load channel-specific vector store
                vectorstore_path = self.config.get_channel_vectorstore_path(channel.id)
                if not vectorstore_path.exists():
                    print(f"❌ No vector store found for channel '{channel.name}'.")
                    print("💡 Please run Phase 3 first to build the vector store.")
                    return
                
                # Perform search
                while True:
                    query = input(f"🔍 Enter search query for '{channel.name}' (or 'back' to return): ").strip()
                    if not query or query.lower() == 'back':
                        break
                    
                    max_results = input("➤ Maximum results (default 5): ").strip()
                    try:
                        max_results = int(max_results) if max_results else 5
                        max_results = max(1, min(max_results, 20))
                    except ValueError:
                        max_results = 5
                    
                    print(f"🔄 Searching in '{channel.name}' for: '{query}'...")
                    
                    try:
                        results = self.rag.search_topics(query, max_results, channel.id)
                        
                        if results:
                            print(f"✅ Found {len(results)} relevant results in '{channel.name}':")
                            print("="*60)
                            
                            for i, result in enumerate(results, 1):
                                print(f"{i}. 📹 {result['title']}")
                                print(f"   👤 {result['uploader']}")
                                print(f"   📝 {result['topic_summary']}")
                                print(f"   🔗 {result['timestamp_url']}")
                                print(f"   📊 Relevance: {result['relevance_score']:.1%}")
                                print(f"   ⏰ Starts at: {result['start_time']}")
                                
                                if self.config.get_verbosity() >= 3:
                                    print(f"   👁️  Preview: {result['content_preview']}")
                        else:
                            print(f"❌ No relevant results found for '{query}' in '{channel.name}'")
                            print("💡 Try different keywords or check if the channel data is properly processed")
                            
                    except Exception as e:
                        self.logger.error(f"Channel search failed: {e}")
                        print(f"❌ Search failed: {e}")
                    
            else:
                print("❌ Invalid channel number.")
        except ValueError:
            print("❌ Invalid input. Please enter a number.")

    def _data_migration_interactive(self):
        """Interactive data migration"""
        print("="*50)
        print("🔄 Data Migration Tool")
        print("="*50)
        print("This tool migrates existing single-channel data to multi-channel structure.")
        print("⚠️  It's recommended to backup your data before migration.")
        
        while True:
            print("-"*40)
            print("Migration Options:")
            print("-"*40)
            print("1. 📊 Analyze Existing Data")
            print("2. 📋 Create Migration Plan")
            print("3. 🔄 Execute Migration")
            print("4. ✅ Verify Migration")
            print("5. 📄 Generate Report")
            print("6. 🔙 Back to Main Menu")
            print("-"*40)
            
            choice = input("➤ Choose migration option (1-6): ").strip()
            
            if choice == '1':
                self._analyze_existing_data()
            elif choice == '2':
                self._create_migration_plan()
            elif choice == '3':
                self._execute_migration()
            elif choice == '4':
                self._verify_migration()
            elif choice == '5':
                self._generate_migration_report()
            elif choice == '6':
                break
            else:
                print("❌ Invalid choice. Please try again.")
    
    def _analyze_existing_data(self):
        """Analyze existing data structure"""
        print("🔍 Analyzing existing data structure...")
        
        try:
            analysis = self.data_migrator.analyze_existing_data()
            
            print("📊 Analysis Results:")
            print("=" * 40)
            
            # Phase 1 analysis
            phase1 = analysis['phase1']
            print(f"📥 Phase 1 Data:")
            print(f"  Path: {phase1['path']}")
            print(f"  Exists: {'✅' if phase1['exists'] else '❌'}")
            if phase1['exists']:
                print(f"  Videos: {phase1['total_videos']}")
                print(f"  Channel Info: {'✅' if phase1.get('channel_info') else '❌'}")
            
            # Phase 2 analysis
            phase2 = analysis['phase2']
            print(f"✨ Phase 2 Data:")
            print(f"  Path: {phase2['path']}")
            print(f"  Exists: {'✅' if phase2['exists'] else '❌'}")
            if phase2['exists']:
                print(f"  Enhanced Files: {phase2['total_enhanced']}")
                print(f"  Summaries: {'✅' if phase2['has_summaries'] else '❌'}")
            
            # Phase 3 analysis
            phase3 = analysis['phase3']
            print(f"🏗️  Phase 3 Data:")
            print(f"  Path: {phase3['path']}")
            print(f"  Exists: {'✅' if phase3['exists'] else '❌'}")
            if phase3['exists']:
                print(f"  Build Info: {'✅' if phase3['has_build_info'] else '❌'}")
                print(f"  Vector Files: {len(phase3['vector_files'])}")
            
            # Save analysis for later use
            self._last_analysis = analysis
            
        except Exception as e:
            self.logger.error(f"Data analysis failed: {e}")
            print(f"❌ Analysis failed: {e}")
    
    def _create_migration_plan(self):
        """Create migration plan"""
        if not hasattr(self, '_last_analysis'):
            print("❌ Please run data analysis first.")
            return
        
        print("📋 Creating migration plan...")
        
        try:
            plan = self.data_migrator.create_migration_plan(self._last_analysis)
            
            print("📋 Migration Plan:")
            print("=" * 40)
            print(f"Target Channel: {plan['target_channel']['name']} ({plan['target_channel']['id']})")
            print(f"Estimated Items: {plan['estimated_items']}")
            print(f"Backup Required: {'✅' if plan['backup_required'] else '❌'}")
            
            print("📝 Migration Steps:")
            for i, step in enumerate(plan['migration_steps'], 1):
                print(f"{i}. {step['description']}")
                print(f"   Source: {step['source_path']}")
                print(f"   Target: {step['target_path']}")
                print(f"   Items: {step['items_count']}")
            
            # Save plan for later use
            self._migration_plan = plan
            
        except Exception as e:
            self.logger.error(f"Migration plan creation failed: {e}")
            print(f"❌ Plan creation failed: {e}")
    
    def _execute_migration(self):
        """Execute migration"""
        if not hasattr(self, '_migration_plan'):
            print("❌ Please create migration plan first.")
            return
        
        print("⚠️  IMPORTANT: This operation will modify your data structure.")
        print("It's highly recommended to backup your data before proceeding.")
        
        confirm = input("➤ Do you want to proceed with migration? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Migration cancelled.")
            return
        
        create_backup = input("➤ Create backup before migration? (yes/no): ").strip().lower()
        backup = create_backup == 'yes'
        
        print("🔄 Executing migration...")
        print("⏱️  This may take several minutes...")
        
        try:
            summary = self.data_migrator.execute_migration(self._migration_plan, backup)
            
            print("📊 Migration Summary:")
            print("=" * 40)
            print(f"Total Items: {summary.total_items}")
            print(f"Successful: {summary.successful_items}")
            print(f"Failed: {summary.failed_items}")
            if summary.total_items > 0:
                success_rate = (summary.successful_items / summary.total_items) * 100
                print(f"Success Rate: {success_rate:.1f}%")
            
            print(f"Target Channel: {summary.default_channel_id}")
            print(f"Started: {summary.started_at}")
            print(f"Completed: {summary.completed_at}")
            
            if summary.failed_items > 0:
                print(f"⚠️  {summary.failed_items} items failed. Check logs for details.")
            
            # Save summary for verification
            self._migration_summary = summary
            
        except Exception as e:
            self.logger.error(f"Migration execution failed: {e}")
            print(f"❌ Migration failed: {e}")
    
    def _verify_migration(self):
        """Verify migration integrity"""
        if not hasattr(self, '_migration_summary'):
            print("❌ Please execute migration first.")
            return
        
        print("✅ Verifying migration integrity...")
        
        try:
            verification = self.data_migrator.verify_migration(self._migration_summary)
            
            print("🔍 Verification Results:")
            print("=" * 40)
            print(f"Overall Success: {'✅' if verification['overall_success'] else '❌'}")
            print(f"Channel ID: {verification['channel_id']}")
            
            for phase in ['phase1', 'phase2', 'phase3']:
                phase_verify = verification[f'{phase}_verification']
                if 'verified_items' in phase_verify:
                    status = '✅' if phase_verify['success'] else '❌'
                    print(f"{phase.upper()}: {status} {phase_verify['verified_items']}/{phase_verify['total_items']} verified")
                else:
                    print(f"{phase.upper()}: {phase_verify.get('message', 'No data')}")
            
            print(f"Verified at: {verification['verified_at']}")
            
            # Save verification for report
            self._verification_result = verification
            
        except Exception as e:
            self.logger.error(f"Migration verification failed: {e}")
            print(f"❌ Verification failed: {e}")
    
    def _generate_migration_report(self):
        """Generate migration report"""
        if not hasattr(self, '_migration_summary') or not hasattr(self, '_verification_result'):
            print("❌ Please execute migration and verification first.")
            return
        
        print("📄 Generating migration report...")
        
        try:
            report = self.data_migrator.generate_migration_report(
                self._migration_summary,
                self._verification_result
            )
            
            print(report)
            
            # Save report to file
            report_file = Path("./data/migration_report.txt")
            report_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"📄 Report saved to: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Report generation failed: {e}")
            print(f"❌ Report generation failed: {e}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='YouTube Topic Seeker')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--email', action='store_true', help='Send email notifications')
    parser.add_argument('channel_url', nargs='?', help='YouTube channel URL to process automatically')
    
    args = parser.parse_args()
    
    try:
        app = YouTubeTopicSeeker(args.config)
        if args.channel_url:
            # 自動処理モード
            app.run_automatic(args.channel_url, args.email)
        else:
            # 対話モード
            app.run_interactive(args.email)
    except KeyboardInterrupt:
        print("🛑 Application interrupted by user")
    except Exception as e:
        print(f"❌ Application failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()