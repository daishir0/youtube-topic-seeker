#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データ構造調査スクリプト - トランスクリプトが認識されない問題の調査
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def investigate_data_structure():
    """データ構造を詳細に調査"""
    print("=" * 60)
    print("🔍 YouTube Topic Seeker - データ構造調査")
    print("=" * 60)
    print(f"調査日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # データディレクトリのパス
    data_dir = Path("./data")
    phase1_dir = data_dir / "1-plain"
    phase2_dir = data_dir / "2-target"
    
    print("📁 ディレクトリ構造:")
    print(f"  Data Directory: {data_dir.absolute()}")
    print(f"  Phase 1: {phase1_dir.absolute()}")
    print(f"  Phase 2: {phase2_dir.absolute()}")
    print()
    
    # Phase 1データの調査
    print("📥 Phase 1 データ調査:")
    if not phase1_dir.exists():
        print("  ❌ Phase 1ディレクトリが存在しません")
        return
    
    # Phase 1の動画ディレクトリ一覧
    video_dirs = [d for d in phase1_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    print(f"  📺 動画ディレクトリ数: {len(video_dirs)}")
    
    if not video_dirs:
        print("  ❌ 動画ディレクトリが見つかりません")
        return
    
    # 最初の5つの動画ディレクトリを詳細調査
    print("\n  🔍 詳細調査（最初の5つの動画）:")
    for i, video_dir in enumerate(video_dirs[:5]):
        print(f"\n  📹 動画 {i+1}: {video_dir.name}")
        
        # ディレクトリ内のファイル一覧
        files = list(video_dir.iterdir())
        print(f"    📄 ファイル数: {len(files)}")
        
        for file in files:
            print(f"    - {file.name} ({file.stat().st_size} bytes)")
            
            # transcript_ja.jsonの詳細調査
            if file.name == "transcript_ja.json":
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        transcript_data = json.load(f)
                    
                    print(f"      📝 トランスクリプト詳細:")
                    print(f"        - キー: {list(transcript_data.keys())}")
                    
                    if 'segments' in transcript_data:
                        segments = transcript_data['segments']
                        print(f"        - セグメント数: {len(segments)}")
                        if segments:
                            first_segment = segments[0]
                            print(f"        - 最初のセグメント: {first_segment}")
                    
                    if 'text' in transcript_data:
                        text = transcript_data['text']
                        print(f"        - テキスト長: {len(text)} 文字")
                        print(f"        - 最初の100文字: {text[:100]}...")
                        
                except Exception as e:
                    print(f"      ❌ トランスクリプト読み込みエラー: {e}")
    
    # Phase 2データの調査
    print(f"\n✨ Phase 2 データ調査:")
    if not phase2_dir.exists():
        print("  ❌ Phase 2ディレクトリが存在しません")
        phase2_dir.mkdir(parents=True, exist_ok=True)
        print("  ✅ Phase 2ディレクトリを作成しました")
    
    # Phase 2の動画ディレクトリ一覧
    phase2_video_dirs = [d for d in phase2_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
    print(f"  📺 Phase 2 動画ディレクトリ数: {len(phase2_video_dirs)}")
    
    # トランスクリプト認識テスト
    print(f"\n🧪 トランスクリプト認識テスト:")
    test_transcript_recognition()

def test_transcript_recognition():
    """Phase2 EnhancerがPhase1のトランスクリプトを正しく認識するかテスト"""
    try:
        from config import Config
        from phase2_enhancer import TranscriptEnhancer
        
        print("  🔧 設定とEnhancerを初期化中...")
        config = Config()
        enhancer = TranscriptEnhancer(config)
        
        # Phase1ディレクトリのスキャン
        phase1_dir = Path("./data/1-plain")
        print(f"  📂 Phase1ディレクトリ: {phase1_dir.absolute()}")
        
        # enhancerが使用する内部メソッドを直接テスト
        print("  🔍 Enhancerの内部メソッドをテスト中...")
        
        # Phase1の動画ディレクトリを取得
        video_dirs = [d for d in phase1_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        print(f"  📺 検出された動画ディレクトリ: {len(video_dirs)}")
        
        if video_dirs:
            # 最初の動画ディレクトリで詳細テスト
            test_dir = video_dirs[0]
            print(f"  🎯 テスト対象: {test_dir.name}")
            
            # transcript_ja.jsonの存在確認
            transcript_file = test_dir / "transcript_ja.json"
            print(f"  📄 transcript_ja.json: {'✅ 存在' if transcript_file.exists() else '❌ 不存在'}")
            
            if transcript_file.exists():
                # ファイルサイズと読み込みテスト
                file_size = transcript_file.stat().st_size
                print(f"  📊 ファイルサイズ: {file_size} bytes")
                
                try:
                    with open(transcript_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    print(f"  ✅ JSON読み込み成功")
                    print(f"  🔑 JSONキー: {list(data.keys())}")
                    
                    # enhancerが期待する形式かチェック
                    if 'segments' in data:
                        segments = data['segments']
                        print(f"  📝 セグメント数: {len(segments)}")
                        if segments and isinstance(segments, list):
                            print(f"  ✅ セグメント形式正常")
                            sample_segment = segments[0]
                            print(f"  📋 サンプルセグメント: {sample_segment}")
                        else:
                            print(f"  ❌ セグメント形式異常")
                    else:
                        print(f"  ⚠️ segmentsキーが存在しません")
                        
                except Exception as e:
                    print(f"  ❌ JSON読み込みエラー: {e}")
        
        # enhancerの設定確認
        print("\n  ⚙️ Enhancer設定:")
        print(f"  - Phase1 path: {enhancer.phase1_dir}")
        print(f"  - Phase2 path: {enhancer.phase2_dir}")
        print(f"  - OpenAI enabled: {hasattr(enhancer, 'openai_client')}")
        
    except Exception as e:
        print(f"  ❌ Enhancerテストエラー: {e}")
        import traceback
        traceback.print_exc()

def investigate_specific_videos():
    """ログに出ているエラー対象の動画を詳細調査"""
    print(f"\n🎯 特定動画の詳細調査:")
    
    # ログから確認できる問題のある動画ID
    problem_videos = [
        "-Lcry_RWRNY_【いさ進一】201466 衆議院安全保障委員会",
        "-Yi5ZepP24s_【告知】企画が整いましたのでアカウントをリニューアルしTikTokのチャンネルを再開させます！【 ノウハウ  攻め企画  CM  お知らせ  ご報告】",
        "3OUuPQTXGGc_【いさ進一】20191019  第3回日中私立大学学長シンポジウム",
        "742PrMfHMpk_【お金のニュース】103万円の壁は存在しない!手取りを増やすの核心に迫る！わかりやすく解説します！",
        "9nJcmhVB5lw_【公明党に物申す】 今の政治に疑問をもつ20代の若者とのガチンコトークで貴重な生の声を聞いてきました！【 本音トーク  ガチトーク  マジ話】"
    ]
    
    phase1_dir = Path("./data/1-plain")
    
    for video_name in problem_videos:
        print(f"\n  📹 {video_name}:")
        video_dir = phase1_dir / video_name
        
        if not video_dir.exists():
            print(f"    ❌ ディレクトリが存在しません: {video_dir}")
            continue
        
        print(f"    ✅ ディレクトリ存在")
        
        # ファイル一覧
        files = list(video_dir.iterdir())
        print(f"    📄 ファイル一覧:")
        for file in files:
            print(f"      - {file.name} ({file.stat().st_size} bytes)")
        
        # transcript_ja.jsonの詳細確認
        transcript_file = video_dir / "transcript_ja.json"
        if transcript_file.exists():
            print(f"    📝 transcript_ja.json詳細:")
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"      ✅ JSON読み込み成功")
                print(f"      📊 データ構造: {type(data)}")
                print(f"      🔑 キー: {list(data.keys()) if isinstance(data, dict) else 'リスト形式'}")
                
                if isinstance(data, dict):
                    if 'segments' in data:
                        segments = data['segments']
                        print(f"      📝 セグメント数: {len(segments) if segments else 0}")
                        print(f"      📝 セグメント型: {type(segments)}")
                        if segments:
                            print(f"      📝 最初のセグメント: {segments[0] if len(segments) > 0 else 'なし'}")
                    
                    if 'text' in data:
                        text = data['text']
                        print(f"      📄 テキスト長: {len(text) if text else 0}")
                
            except Exception as e:
                print(f"      ❌ JSON読み込みエラー: {e}")
        else:
            print(f"    ❌ transcript_ja.jsonが存在しません")

if __name__ == "__main__":
    investigate_data_structure()
    investigate_specific_videos()
    
    print(f"\n" + "=" * 60)
    print("🎯 調査完了")
    print("=" * 60)