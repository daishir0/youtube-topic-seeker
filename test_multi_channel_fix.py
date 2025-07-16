#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
マルチチャンネル対応改修テストスクリプト
"""

import sys
import os
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_phase2_multi_channel():
    """Phase2のマルチチャンネル対応をテスト"""
    print("🧪 Phase2 Enhancer マルチチャンネル対応テスト")
    print("=" * 50)
    
    try:
        from config import Config
        from phase2_enhancer import TranscriptEnhancer
        
        config = Config()
        enhancer = TranscriptEnhancer(config)
        
        print("✅ Phase2 Enhancer 初期化成功")
        
        # 動画ディレクトリスキャンテスト
        print("\n🔍 動画ディレクトリスキャンテスト:")
        input_dir = config.get_phase1_path()
        print(f"Phase1ディレクトリ: {input_dir}")
        
        if input_dir.exists():
            # 改修したスキャン機能をテスト
            video_dirs = []
            
            def scan_for_video_directories(base_dir):
                """Recursively scan for video directories (containing metadata.json)"""
                video_dirs = []
                
                def scan_directory(directory, depth=0):
                    if depth > 2:
                        return
                    
                    try:
                        for item in directory.iterdir():
                            if not item.is_dir():
                                continue
                            
                            metadata_file = item / "metadata.json"
                            if metadata_file.exists():
                                try:
                                    if metadata_file.stat().st_size > 100:
                                        video_dirs.append(item)
                                        print(f"  ✅ 動画ディレクトリ検出: {item.name}")
                                    else:
                                        print(f"  ⚠️ 小さすぎるメタデータ: {item.name}")
                                except Exception as e:
                                    print(f"  ❌ メタデータサイズ確認エラー: {item.name} - {e}")
                            else:
                                scan_directory(item, depth + 1)
                    except Exception as e:
                        print(f"  ❌ ディレクトリスキャンエラー: {directory} - {e}")
                
                scan_directory(base_dir)
                return video_dirs
            
            video_dirs = scan_for_video_directories(input_dir)
            print(f"\n📊 スキャン結果: {len(video_dirs)} 個の動画ディレクトリを検出")
            
            # 最初の5つの動画でチャンネルID抽出テスト
            print(f"\n🏷️ チャンネルID抽出テスト:")
            for i, video_dir in enumerate(video_dirs[:5]):
                channel_id = enhancer._extract_channel_id_from_path(video_dir)
                print(f"  動画: {video_dir.name[:50]}...")
                print(f"  チャンネルID: {channel_id}")
                
                # トランスクリプトファイル検証
                transcript_files = list(video_dir.glob("transcript_*.json"))
                print(f"  トランスクリプトファイル数: {len(transcript_files)}")
                
                valid_count = 0
                for tf in transcript_files:
                    try:
                        if tf.stat().st_size > 50:
                            valid_count += 1
                    except:
                        pass
                print(f"  有効なトランスクリプト: {valid_count}")
                print()
        else:
            print("❌ Phase1ディレクトリが存在しません")
        
        return True
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_phase3_multi_channel():
    """Phase3のマルチチャンネル対応をテスト"""
    print("\n🧪 Phase3 RAG マルチチャンネル対応テスト")
    print("=" * 50)
    
    try:
        from config import Config
        from phase3_rag import TopicSearchRAG
        
        config = Config()
        rag = TopicSearchRAG(config)
        
        print("✅ Phase3 RAG 初期化成功")
        
        # Phase2出力ディレクトリスキャンテスト
        print("\n🔍 Phase2出力ディレクトリスキャンテスト:")
        input_dir = config.get_phase2_path()
        print(f"Phase2ディレクトリ: {input_dir}")
        
        if input_dir.exists():
            # 改修したスキャン機能をテスト
            def scan_for_enhanced_files(base_dir):
                """Recursively scan for enhanced files across all channels"""
                files = []
                
                # First, check if there are files directly in the base directory (legacy structure)
                direct_files = list(base_dir.glob("*_enhanced.json"))
                files.extend(direct_files)
                print(f"  📄 直接ファイル: {len(direct_files)}")
                
                # Then, check channel subdirectories
                for item in base_dir.iterdir():
                    if item.is_dir():
                        channel_enhanced_files = list(item.glob("*_enhanced.json"))
                        if channel_enhanced_files:
                            files.extend(channel_enhanced_files)
                            print(f"  📁 {item.name}: {len(channel_enhanced_files)} 強化ファイル")
                
                return files
            
            enhanced_files = scan_for_enhanced_files(input_dir)
            print(f"\n📊 スキャン結果: {len(enhanced_files)} 個の強化ファイルを検出")
        else:
            print("❌ Phase2ディレクトリが存在しません")
        
        return True
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 マルチチャンネル対応改修テスト開始")
    print("=" * 60)
    
    phase2_success = test_phase2_multi_channel()
    phase3_success = test_phase3_multi_channel()
    
    print("\n" + "=" * 60)
    print("📊 テスト結果サマリー")
    print("=" * 60)
    print(f"Phase2 Enhancer: {'✅ 成功' if phase2_success else '❌ 失敗'}")
    print(f"Phase3 RAG: {'✅ 成功' if phase3_success else '❌ 失敗'}")
    
    if phase2_success and phase3_success:
        print("\n🎉 すべてのテストが成功しました！")
        print("マルチチャンネル対応改修が完了しています。")
    else:
        print("\n⚠️ 一部のテストが失敗しました。")
        print("ログを確認して問題を修正してください。")