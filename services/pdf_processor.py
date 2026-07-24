"""
PDF处理服务
负责PDF文件的解析、文本提取和分块处理
"""
import hashlib
import re
from typing import Dict, List, Tuple
from pathlib import Path

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


class PDFProcessor:
    """PDF文件处理器"""

    def __init__(self):
        if not PYPDF2_AVAILABLE:
            raise ImportError("请先安装PyPDF2: pip install PyPDF2")
    
    def calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值（用于重复检测）
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: MD5哈希值
        """
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    
    def extract_metadata(self, file_path: str) -> Dict:
        """提取PDF元数据
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            Dict: 包含标题、作者、页数等信息
        """
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                metadata = reader.metadata if reader.metadata else {}
                
                # 提取元数据
                title = metadata.get('/Title', '') if hasattr(metadata, 'get') else ''
                author = metadata.get('/Author', '') if hasattr(metadata, 'get') else ''
                
                # 如果标题为空，尝试从文件名提取
                if not title:
                    title = Path(file_path).stem
                
                return {
                    'title': self._clean_text(title),
                    'author': self._clean_text(author),
                    'page_count': len(reader.pages),
                    'file_hash': self.calculate_file_hash(file_path)
                }
        except Exception as e:
            print(f"提取PDF元数据时出错: {e}")
            return {
                'title': Path(file_path).stem,
                'author': '',
                'page_count': 0,
                'file_hash': self.calculate_file_hash(file_path)
            }
    
    def extract_text(self, file_path: str) -> Tuple[str, int]:
        global PDFPLUMBER_AVAILABLE
        try:
            text_parts = []

            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page_num, page in enumerate(reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text_parts.append(f"\n\n[第{page_num + 1}页]\n{page_text}")
                    except Exception as e:
                        print(f"提取第 {page_num + 1} 页时出错: {e}")

            full_text = ''.join(text_parts)
            word_count = len(full_text.replace(' ', '').replace('\n', ''))

            if word_count < 100 and PDFPLUMBER_AVAILABLE:
                try:
                    import pdfplumber
                    text_parts = []
                    with pdfplumber.open(file_path) as pdf:
                        for page_num, page in enumerate(pdf.pages):
                            page_text = page.extract_text()
                            if page_text:
                                text_parts.append(f"\n\n[第{page_num + 1}页]\n{page_text}")
                    full_text = ''.join(text_parts)
                    word_count = len(full_text.replace(' ', '').replace('\n', ''))
                    print(f"pdfplumber补充提取完成，共 {word_count} 字")
                except Exception as e:
                    print(f"pdfplumber提取失败: {e}")

            return self._clean_text(full_text), word_count
        except Exception as e:
            print(f"提取PDF文本时出错: {e}")
            return "", 0
    
    def chunk_text(self, text: str, chunk_size: int = 500, 
                   overlap: int = 50) -> List[str]:
        """文本分块（用于向量化）
        
        Args:
            text: 原始文本
            chunk_size: 每块字符数
            overlap: 重叠字符数
            
        Returns:
            List[str]: 文本块列表
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = start + chunk_size
            
            # 尝试在句子边界处分块
            chunk = text[start:end]
            
            # 如果不是最后一块，尝试找到句号、问号等标点符号
            if end < text_length:
                # 查找最后一个句子结束符
                last_period = max(
                    chunk.rfind('。'),
                    chunk.rfind('！'),
                    chunk.rfind('？'),
                    chunk.rfind('.'),
                    chunk.rfind('!'),
                    chunk.rfind('?')
                )
                
                if last_period > chunk_size * 0.3:  # 至少包含30%的内容
                    chunk = chunk[:last_period + 1]
                    end = start + len(chunk)
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        # 过滤掉过短的块
        chunks = [c for c in chunks if len(c) > 50]
        
        return chunks
    
    def _clean_text(self, text: str) -> str:
        """清理文本
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        # 移除特殊控制字符
        text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', text)
        
        return text.strip()
    
    def process_pdf(self, file_path: str) -> Dict:
        """处理PDF文件（提取元数据、文本、分块）
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            Dict: 包含所有处理结果
        """
        try:
            print(f"正在处理PDF文件: {file_path}")
            
            # 1. 提取元数据
            metadata = self.extract_metadata(file_path)
            print(f"元数据提取完成: {metadata['title']}")
            
            # 2. 提取文本
            text, word_count = self.extract_text(file_path)
            print(f"文本提取完成，共 {word_count} 字")
            
            # 3. 文本分块
            chunks = self.chunk_text(text)
            print(f"文本分块完成，共 {len(chunks)} 个块")
            
            return {
                'success': True,
                'metadata': metadata,
                'text': text,
                'word_count': word_count,
                'chunks': chunks
            }
            
        except Exception as e:
            print(f"处理PDF文件时出错: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# 全局PDF处理器实例
_pdf_processor = None

def get_pdf_processor() -> PDFProcessor:
    """获取全局PDF处理器实例"""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()
    return _pdf_processor

