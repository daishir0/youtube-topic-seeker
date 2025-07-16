#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
既存のレガシー構造の強化ファイルを新しいマルチチャンネル構造に移行
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Optional

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import Config

def find_video_channel_from_phase1(video_id: str, config: Config) -> Optional[str]:
    """Phase1データからビデオIDに対応するチャンネルIDを検索"""
    phase1_dir = config.get_phase1_path()
    
    # 各チャンネルディレクトリを検索
    for channel_dir in phase1_dir.iterdir():
        if not channel_dir.is_dir():
            continue
            
        # このチャンネル内でビデオIDを含むディレクトリを検索
        for video_dir in channel_dir.iterdir():
            if not video_dir.is_dir():
                continue
            
            # ディレクトリ名がビデオIDで始まるかチェック
            if video_dir.name.startswith(video_id):
                return channel_dir.name
    
    return None

def migrate_legacy_enhanced_files():
    """レガシー構造の強化ファイルを新構造に移行"""
    print("🔄 レガシー強化ファイルのマルチチャンネル構造への移行開始")
    
    config = Config()
    phase2_dir = config.get_phase2_path()
    
    # レガシーファイル（ルートディレクトリ直下の強化ファイル）を検索
    legacy_files = list(phase2_dir.glob("*_enhanced.json"))
    
    print(f"📁 検出されたレガシーファイル: {len(legacy_files)}")
    
    moved_count = 0
    error_count = 0
    no_channel_count = 0
    
    for enhanced_file in legacy_files:
        try:
            # 強化ファイルからビデオ情報を読み取り
            with open(enhanced_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            video_id = data.get('video_id')
            channel_id = data.get('channel_id')
            
            # チャンネルIDがない場合、Phase1データから推定
            if not channel_id and video_id:
                print(f"🔍 Phase1データからチャンネルIDを検索中: {video_id}")
                channel_id = find_video_channel_from_phase1(video_id, config)
                
                # ファイルにチャンネルIDを追加して更新
                if channel_id:
                    data['channel_id'] = channel_id
                    with open(enhanced_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    print(f"✅ チャンネルID補完: {video_id} → {channel_id}")
            
            if not channel_id:
                print(f"⚠️ チャンネルIDが見つかりません: {enhanced_file.name}")
                no_channel_count += 1
                continue
            
            # チャンネル別ディレクトリを作成
            channel_dir = phase2_dir / channel_id
            channel_dir.mkdir(exist_ok=True)
            
            # ファイルを移動
            destination = channel_dir / enhanced_file.name
            
            if destination.exists():
                print(f"⚠️ ファイルが既に存在します: {destination}")
                continue
            
            shutil.move(str(enhanced_file), str(destination))
            print(f"✅ 移動完了: {enhanced_file.name} → {channel_id}/")
            moved_count += 1
            
        except Exception as e:
            print(f"❌ エラー: {enhanced_file.name} - {e}")
            error_count += 1
    
    print(f"\n📊 移行結果:")
    print(f"  ✅ 移動成功: {moved_count}")
    print(f"  ❌ エラー: {error_count}")
    print(f"  ⚠️ チャンネル不明: {no_channel_count}")
    print(f"  📄 残り: {len(list(phase2_dir.glob('*_enhanced.json')))}")
    
    # 移行後の構造確認
    print(f"\n📁 移行後のディレクトリ構造:")
    for item in phase2_dir.iterdir():
        if item.is_dir():
            file_count = len(list(item.glob("*_enhanced.json")))
            print(f"  📺 {item.name}: {file_count} 強化ファイル")

if __name__ == "__main__":
    migrate_legacy_enhanced_files()