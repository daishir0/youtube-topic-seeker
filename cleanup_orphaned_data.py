#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フェーズ3ベクターストアの孤立データクリーンアップスクリプト

メタデータが見つからない動画データをベクターストアから削除し、
データ整合性を確保します。
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Set, Tuple
import sys

# プロジェクトのsrcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import Config
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
import httpx

class VectorStoreCleanup:
    """ベクターストアのクリーンアップを実行するクラス"""
    
    def __init__(self):
        """初期化"""
        self.config = Config()
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # OpenAI Embeddings設定
        http_client = None
        proxy_settings = self.config.get_proxy_settings()
        if proxy_settings:
            proxy_url = self.config.get_proxy_url()
            http_client = httpx.Client(proxy=proxy_url)
        
        self.embeddings = OpenAIEmbeddings(
            model=self.config.rag.embedding_model,
            openai_api_key=self.config.openai.api_key,
            http_client=http_client
        )
        
        self.vectorstore_dir = Path('data/vectorstore')
        self.phase1_dir = Path('data/1-plain')
        
    def setup_logging(self):
        """ログ設定"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def identify_orphaned_data(self) -> Tuple[Set[str], Set[str], Set[str]]:
        """孤立データを特定する"""
        self.logger.info("孤立データの特定を開始...")
        
        # ベクターストアから処理済み動画IDを取得
        build_info_file = self.vectorstore_dir / "build_info.json"
        if not build_info_file.exists():
            self.logger.error("build_info.jsonが見つかりません")
            return set(), set(), set()
        
        with open(build_info_file, 'r') as f:
            build_info = json.load(f)
        
        vectorstore_video_ids = set(build_info.get('processed_video_ids', []))
        self.logger.info(f"ベクターストア内の動画数: {len(vectorstore_video_ids)}")
        
        # フェーズ1に存在する動画IDを収集
        phase1_video_ids = set()
        cutoff_date = datetime.now() - timedelta(days=365)
        
        for metadata_file in self.phase1_dir.rglob('*/metadata.json'):
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                video_id = metadata.get('id')
                upload_date_str = metadata.get('upload_date', '')
                
                if video_id and upload_date_str:
                    # 1年以内のデータのみを対象
                    upload_date = datetime.strptime(upload_date_str, '%Y%m%d')
                    if upload_date >= cutoff_date:
                        phase1_video_ids.add(video_id)
                        
            except Exception as e:
                self.logger.warning(f"メタデータ読み込みエラー {metadata_file}: {e}")
                continue
        
        self.logger.info(f"フェーズ1の有効動画数（1年以内）: {len(phase1_video_ids)}")
        
        # 孤立データ特定
        orphaned_video_ids = vectorstore_video_ids - phase1_video_ids
        valid_video_ids = vectorstore_video_ids & phase1_video_ids
        
        self.logger.info(f"孤立データ: {len(orphaned_video_ids)}本")
        self.logger.info(f"有効データ: {len(valid_video_ids)}本")
        
        return orphaned_video_ids, valid_video_ids, vectorstore_video_ids
    
    def remove_orphaned_data_from_vectorstore(self, orphaned_video_ids: Set[str]) -> bool:
        """ベクターストアから孤立データを削除"""
        if not orphaned_video_ids:
            self.logger.info("削除対象の孤立データはありません")
            return True
        
        self.logger.info(f"ベクターストアから{len(orphaned_video_ids)}本の孤立データを削除開始...")
        
        try:
            # Chromaベクターストアをロード
            vectorstore = Chroma(
                persist_directory=str(self.vectorstore_dir),
                embedding_function=self.embeddings
            )
            
            # 削除対象のドキュメントIDを特定
            # ChromaではメタデータのVideo_idでフィルタリング
            deleted_count = 0
            batch_size = 50  # バッチサイズを小さくして安全に処理
            
            orphaned_list = list(orphaned_video_ids)
            for i in range(0, len(orphaned_list), batch_size):
                batch_ids = orphaned_list[i:i + batch_size]
                
                try:
                    # 該当する動画IDのドキュメントを検索
                    for video_id in batch_ids:
                        # メタデータで検索してドキュメントIDを取得
                        results = vectorstore.get(
                            where={"video_id": video_id}
                        )
                        
                        if results and results['ids']:
                            # ドキュメントを削除
                            vectorstore.delete(ids=results['ids'])
                            deleted_count += len(results['ids'])
                            self.logger.debug(f"削除完了: {video_id} ({len(results['ids'])}ドキュメント)")
                
                except Exception as e:
                    self.logger.error(f"バッチ削除エラー {batch_ids}: {e}")
                    continue
            
            self.logger.info(f"ベクターストアから{deleted_count}ドキュメントを削除完了")
            return True
            
        except Exception as e:
            self.logger.error(f"ベクターストア削除エラー: {e}")
            return False
    
    def update_build_info(self, valid_video_ids: Set[str]) -> bool:
        """build_info.jsonを更新"""
        self.logger.info("build_info.jsonを更新中...")
        
        try:
            build_info_file = self.vectorstore_dir / "build_info.json"
            
            with open(build_info_file, 'r') as f:
                build_info = json.load(f)
            
            # 有効な動画IDのみに更新
            build_info['processed_video_ids'] = list(valid_video_ids)
            build_info['total_videos'] = len(valid_video_ids)
            build_info['cleaned_at'] = datetime.now().isoformat()
            build_info['cleanup_removed_count'] = len(build_info.get('processed_video_ids', [])) - len(valid_video_ids)
            
            # バックアップ作成
            backup_file = build_info_file.with_suffix('.json.backup')
            with open(backup_file, 'w') as f:
                json.dump(json.load(open(build_info_file)), f, indent=2, ensure_ascii=False)
            
            # 更新版を保存
            with open(build_info_file, 'w') as f:
                json.dump(build_info, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"build_info.json更新完了（バックアップ: {backup_file}）")
            return True
            
        except Exception as e:
            self.logger.error(f"build_info.json更新エラー: {e}")
            return False
    
    def verify_data_consistency(self, valid_video_ids: Set[str]) -> bool:
        """データ整合性の最終確認"""
        self.logger.info("データ整合性を確認中...")
        
        try:
            # ベクターストアから動画IDを再取得
            vectorstore = Chroma(
                persist_directory=str(self.vectorstore_dir),
                embedding_function=self.embeddings
            )
            
            # 全ドキュメント取得
            all_docs = vectorstore.get()
            vectorstore_video_ids = set()
            
            for metadata in all_docs.get('metadatas', []):
                if metadata and 'video_id' in metadata:
                    vectorstore_video_ids.add(metadata['video_id'])
            
            # 整合性チェック
            missing_in_vectorstore = valid_video_ids - vectorstore_video_ids
            extra_in_vectorstore = vectorstore_video_ids - valid_video_ids
            
            self.logger.info(f"最終確認結果:")
            self.logger.info(f"  - 有効動画ID数: {len(valid_video_ids)}")
            self.logger.info(f"  - ベクターストア動画ID数: {len(vectorstore_video_ids)}")
            self.logger.info(f"  - 不足データ: {len(missing_in_vectorstore)}")
            self.logger.info(f"  - 余剰データ: {len(extra_in_vectorstore)}")
            
            if missing_in_vectorstore:
                self.logger.warning(f"ベクターストアに不足: {list(missing_in_vectorstore)[:5]}...")
            
            if extra_in_vectorstore:
                self.logger.warning(f"ベクターストアに余剰: {list(extra_in_vectorstore)[:5]}...")
            
            return len(extra_in_vectorstore) == 0
            
        except Exception as e:
            self.logger.error(f"整合性確認エラー: {e}")
            return False
    
    def run_cleanup(self) -> bool:
        """クリーンアップ処理を実行"""
        self.logger.info("=== ベクターストアクリーンアップ開始 ===")
        
        try:
            # 1. 孤立データ特定
            orphaned_ids, valid_ids, original_ids = self.identify_orphaned_data()
            
            if not orphaned_ids:
                self.logger.info("孤立データが見つかりませんでした。クリーンアップ不要です。")
                return True
            
            # 確認プロンプト
            print(f"\n🔍 クリーンアップ対象:")
            print(f"  📊 現在のベクターストア動画数: {len(original_ids)}")
            print(f"  🟢 有効動画数: {len(valid_ids)}")
            print(f"  🔴 削除対象（孤立データ）: {len(orphaned_ids)}")
            print(f"\n⚠️  {len(orphaned_ids)}本の孤立データを削除します。")
            
            # 自動実行のため確認をスキップ
            print("✅ 自動実行モード: クリーンアップを開始します...")
            confirm = 'y'
            
            # 2. ベクターストアから削除
            if not self.remove_orphaned_data_from_vectorstore(orphaned_ids):
                return False
            
            # 3. build_info.json更新
            if not self.update_build_info(valid_ids):
                return False
            
            # 4. 整合性確認
            if not self.verify_data_consistency(valid_ids):
                self.logger.warning("整合性確認で問題が検出されました")
                return False
            
            self.logger.info("=== クリーンアップ完了 ===")
            print(f"\n✅ クリーンアップが正常に完了しました！")
            print(f"📊 最終結果: {len(valid_ids)}本の動画データが保持されています")
            
            return True
            
        except Exception as e:
            self.logger.error(f"クリーンアップ処理エラー: {e}")
            return False

def main():
    """メイン処理"""
    cleanup = VectorStoreCleanup()
    success = cleanup.run_cleanup()
    
    if not success:
        print("❌ クリーンアップが失敗しました。ログを確認してください。")
        sys.exit(1)
    
    print("🎉 すべての処理が正常に完了しました！")

if __name__ == "__main__":
    main()