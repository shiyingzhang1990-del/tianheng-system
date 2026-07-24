"""
向量存储服务 - 基于ChromaDB实现
用于文档向量化存储和检索
"""
import os
from typing import List, Dict, Optional

CHROMADB_AVAILABLE = None
SENTENCE_TRANSFORMERS_AVAILABLE = None


def _ensure_chromadb():
    global CHROMADB_AVAILABLE
    if CHROMADB_AVAILABLE is None:
        try:
            global chromadb, Settings
            import chromadb
            from chromadb.config import Settings
            CHROMADB_AVAILABLE = True
        except ImportError:
            CHROMADB_AVAILABLE = False
            print("警告: ChromaDB未安装，向量检索功能将不可用")
    return CHROMADB_AVAILABLE


def _ensure_sentence_transformers():
    global SENTENCE_TRANSFORMERS_AVAILABLE
    if SENTENCE_TRANSFORMERS_AVAILABLE is None:
        try:
            global SentenceTransformer
            from sentence_transformers import SentenceTransformer
            SENTENCE_TRANSFORMERS_AVAILABLE = True
        except ImportError:
            SENTENCE_TRANSFORMERS_AVAILABLE = False
            print("警告: sentence-transformers未安装，文档向量化功能将不可用")
    return SENTENCE_TRANSFORMERS_AVAILABLE


class VectorStore:
    """向量存储服务"""
    
    def __init__(self, persist_directory: str = "./vector_db"):
        """初始化向量存储
        
        Args:
            persist_directory: 向量数据库持久化目录
        """
        if not _ensure_chromadb():
            raise ImportError("请先安装chromadb: pip install chromadb")

        if not _ensure_sentence_transformers():
            raise ImportError("请先安装sentence-transformers: pip install sentence-transformers")
        
        # 创建持久化目录
        os.makedirs(persist_directory, exist_ok=True)
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # 初始化嵌入模型（多语言支持）
        print("正在加载嵌入模型...")
        
        # 优先从本地加载模型
        local_model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'models', 
            'embedding'
        )
        
        if os.path.exists(local_model_path) and os.path.isdir(local_model_path):
            print(f"从本地加载模型: {local_model_path}")
            self.model = SentenceTransformer(local_model_path)
        else:
            print("从缓存加载模型...")
            import time
            start = time.time()
            self.model = SentenceTransformer(
                'paraphrase-multilingual-MiniLM-L12-v2',
                local_files_only=True
            )
            elapsed = time.time() - start
            print(f"模型加载完成（用时{elapsed:.1f}秒）")
        
        # 获取或创建集合
        try:
            self.collection = self.client.get_collection(name="documents")
            print(f"已加载现有集合，包含 {self.collection.count()} 个文档")
        except:
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"description": "经商知识库文档向量"}
            )
            print("已创建新的向量集合")
    
    def add_document(self, document_id: int, chunks: List[str], 
                    metadata: Optional[Dict] = None) -> bool:
        """添加文档到向量数据库
        
        Args:
            document_id: 文档ID
            chunks: 文档分块列表
            metadata: 文档元数据（标题、作者等）
            
        Returns:
            bool: 是否成功
        """
        try:
            if not chunks:
                print(f"警告: 文档 {document_id} 没有有效的文本块")
                return False
            
            # 生成嵌入向量
            print(f"正在为文档 {document_id} 生成向量...")
            embeddings = self.model.encode(chunks, show_progress_bar=False).tolist()
            
            # 生成唯一ID
            ids = [f"doc_{document_id}_chunk_{i}" for i in range(len(chunks))]
            
            # 准备元数据
            metadatas = []
            for i, chunk in enumerate(chunks):
                meta = {
                    'document_id': str(document_id),
                    'chunk_index': i,
                    'chunk_preview': chunk[:100] + '...' if len(chunk) > 100 else chunk
                }
                if metadata:
                    meta.update(metadata)
                metadatas.append(meta)
            
            # 添加到集合
            self.collection.add(
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
            
            print(f"文档 {document_id} 已添加到向量数据库（{len(chunks)} 个文本块）")
            return True
            
        except Exception as e:
            print(f"添加文档到向量数据库时出错: {e}")
            return False
    
    def search(self, query: str, n_results: int = 5, 
               document_id: Optional[int] = None) -> List[Dict]:
        """搜索相关文档
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            document_id: 可选，限制在特定文档内搜索
            
        Returns:
            List[Dict]: 搜索结果列表
        """
        try:
            # 查询向量化
            query_embedding = self.model.encode([query], show_progress_bar=False).tolist()
            
            # 构建查询条件
            where = None
            if document_id is not None:
                where = {"document_id": str(document_id)}
            
            # 执行搜索
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                where=where
            )
            
            # 格式化结果
            formatted_results = []
            if results['ids'] and len(results['ids'][0]) > 0:
                for i in range(len(results['ids'][0])):
                    formatted_results.append({
                        'id': results['ids'][0][i],
                        'text': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'distance': results['distances'][0][i] if 'distances' in results else None,
                        'relevance': 1 - results['distances'][0][i] if 'distances' in results else 1.0
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"向量搜索时出错: {e}")
            return []
    
    def delete_document(self, document_id: int) -> bool:
        """删除文档向量
        
        Args:
            document_id: 文档ID
            
        Returns:
            bool: 是否成功
        """
        try:
            # 查找该文档的所有chunk
            results = self.collection.get(
                where={"document_id": str(document_id)}
            )
            
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                print(f"已删除文档 {document_id} 的向量数据（{len(results['ids'])} 个文本块）")
                return True
            else:
                print(f"未找到文档 {document_id} 的向量数据")
                return False
                
        except Exception as e:
            print(f"删除文档向量时出错: {e}")
            return False
    
    def get_collection_info(self) -> Dict:
        """获取集合信息"""
        try:
            count = self.collection.count()
            return {
                'total_chunks': count,
                'collection_name': self.collection.name
            }
        except Exception as e:
            print(f"获取集合信息时出错: {e}")
            return {'total_chunks': 0, 'collection_name': 'documents'}


# 全局向量存储实例（延迟初始化）
_vector_store = None

def get_vector_store(persist_directory: str = "./vector_db") -> VectorStore:
    """获取全局向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore(persist_directory)
    return _vector_store

