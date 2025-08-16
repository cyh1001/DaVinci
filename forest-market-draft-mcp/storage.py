"""
草稿存储管理器
"""

import json
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

try:
    from .models import ProductDraft
except ImportError:
    from models import ProductDraft


class DraftStorage:
    """草稿存储管理器"""
    def __init__(self, file_path: Path = Path("drafts.json")):
        self.file_path = file_path
        self._drafts: Dict[str, ProductDraft] = {}
        self.load_drafts()
    
    def load_drafts(self):
        """从文件加载草稿"""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._drafts = {
                        draft_id: ProductDraft.from_dict(draft_data)
                        for draft_id, draft_data in data.items()
                    }
            except Exception as e:
                print("加载草稿失败: 文件格式错误或损坏")
                self._drafts = {}
        else:
            # 文件不存在，创建空的草稿文件
            self._drafts = {}
            self.save_drafts()
    
    def save_drafts(self):
        """保存草稿到文件"""
        try:
            data = {
                draft_id: draft.to_dict()
                for draft_id, draft in self._drafts.items()
            }
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("保存草稿失败: 磁盘空间不足或权限不够")
    
    def create_draft(self, draft: ProductDraft) -> str:
        """创建新草稿"""
        self._drafts[draft.draft_id] = draft
        self.save_drafts()
        return draft.draft_id
    
    def get_draft(self, draft_id: str) -> Optional[ProductDraft]:
        """获取草稿"""
        return self._drafts.get(draft_id)
    
    def update_draft(self, draft_id: str, **updates) -> bool:
        """更新草稿"""
        if draft_id not in self._drafts:
            return False
        
        draft = self._drafts[draft_id]
        for key, value in updates.items():
            if hasattr(draft, key):
                setattr(draft, key, value)
        
        draft.updated_at = datetime.now().isoformat()
        draft.version += 1
        self.save_drafts()
        return True
    
    def delete_draft(self, draft_id: str) -> bool:
        """删除草稿"""
        if draft_id in self._drafts:
            del self._drafts[draft_id]
            self.save_drafts()
            return True
        return False
    
    def list_drafts(self) -> List[ProductDraft]:
        """列出所有草稿"""
        return list(self._drafts.values())