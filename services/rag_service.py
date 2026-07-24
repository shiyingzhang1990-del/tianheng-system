"""
RAG问答服务
实现基于检索增强生成的智能问答功能
"""
import requests
from typing import List, Dict, Tuple, Optional

class RAGService:
    """RAG问答服务"""
    
    def __init__(self, vector_store, deepseek_api_key: str, 
                 deepseek_api_url: str):
        """初始化RAG服务
        
        Args:
            vector_store: 向量存储实例
            deepseek_api_key: DeepSeek API密钥
            deepseek_api_url: DeepSeek API地址
        """
        self.vector_store = vector_store
        self.api_key = deepseek_api_key
        self.api_url = deepseek_api_url
        
        if not self.api_key or self.api_key == 'your-deepseek-api-key-here':
            print("警告: DeepSeek API密钥未配置，问答功能将使用模拟数据")
            self.api_enabled = False
        else:
            self.api_enabled = True
    
    def answer_question(self, question: str, 
                       n_context: int = 5,
                       document_id: Optional[int] = None) -> Tuple[str, List[Dict]]:
        """回答问题
        
        Args:
            question: 用户问题
            n_context: 检索上下文数量
            document_id: 可选，限制在特定文档内检索
            
        Returns:
            Tuple[str, List[Dict]]: (回答, 引用来源列表)
        """
        try:
            print(f"正在处理问题: {question}")
            
            # 1. 检索相关上下文
            print("正在检索相关文档...")
            search_results = self.vector_store.search(
                question, 
                n_results=n_context,
                document_id=document_id
            )
            
            if not search_results:
                print("⚠️ 未找到相关文档，将使用AI通用知识回答")
                # 没有文档时，返回基于AI通用知识的回答
                context = ""
                sources = []
            else:
                print(f"找到 {len(search_results)} 个相关文档片段")
                # 2. 构建上下文
                context = self._build_context(search_results)
                # 5. 整理引用来源
                sources = self._format_sources(search_results)
            
            # 3. 生成提示词
            prompt = self._build_prompt(question, context)
            
            # 4. 调用DeepSeek API或返回模拟答案
            if self.api_enabled:
                answer = self._call_deepseek(prompt)
            else:
                if search_results:
                    answer = self._get_mock_answer(question, search_results)
                else:
                    answer = self._get_no_context_answer(question)
            
            return answer, sources
            
        except Exception as e:
            print(f"回答问题时出错: {e}")
            return f"抱歉，处理您的问题时出现错误：{str(e)}", []
    
    def _build_context(self, search_results: List[Dict]) -> str:
        """构建上下文
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            str: 格式化的上下文文本
        """
        context_parts = []
        for i, result in enumerate(search_results):
            relevance = result.get('relevance', 0)
            text = result['text']
            context_parts.append(
                f"[参考资料{i+1}] (相关度: {relevance:.2%})\n{text}\n"
            )
        return '\n'.join(context_parts)
    
    def _build_prompt(self, question: str, context: str) -> str:
        """构建提示词（融入E-P-I-C生成式认知逻辑链条）
        
        Args:
            question: 用户问题
            context: 上下文信息（可能为空）
            
        Returns:
            str: 完整的提示词
        """
        # 根据是否有参考资料调整提示词
        if context.strip():
            context_section = f"""# 参考资料
{context}

请基于以上参考资料，运用 E-P-I-C 认知框架深度分析和回答问题。"""
        else:
            context_section = """# 注意
当前知识库中暂无相关文档。请基于你自己的知识储备，运用 E-P-I-C 认知框架深度分析和回答问题。
建议在回答开头说明：此回答基于通用知识，未参考用户上传的文档。"""
        
        return f"""你是一位顶尖的经济管理领域思想家，具备深刻的洞察力和原创性思维。

{context_section}

# 用户问题
{question}

# E-P-I-C 生成式认知逻辑链条

请运用 **E-P-I-C 认知框架** 来深度分析和回答问题，展现你的思想深度：

## 第一环 (E): 本质洞察 - 寻找张力

**核心任务**：从参考资料中挖掘出"根本性张力"（Fundamental Tension）

**思考路径**：
1. **悖论扫描**：识别资料中的矛盾、冲突或不一致性（理论vs现实、宏观vs微观、过去vs现在）
2. **异常信号放大**：关注"意外发现"和"局外点"，将其作为颠覆性洞察的突破口
3. **问题升维**：将具体问题升维至"制度-结构-人性"的深层追问

**输出目标**：提炼出一个极具张力的核心问题，抓住智识要害

## 第二环 (P): 模式提炼 - 锻造概念

**核心任务**：为发现的张力创造"原创性概念模型"

**思考路径**：
1. **过程抽象**：将案例演化抽象为普适性的"阶段"和"核心机制"
2. **概念命名**：为独特模式赋予简洁、形象、富有理论意涵的新名字
3. **模型建构**：构建可视化、结构化的理论框架（如矩阵、流程图、整合框架）

**输出目标**：创造一个原创的理论模型和核心构念

## 第三环 (I): 意涵衍生 - 情景推演

**核心任务**：基于新模型进行前瞻性的"多维情景推演"

**思考路径**：
1. **理论推演**：用新模型审视其他领域，得出颠覆性理论假设
2. **实践推演**：为不同实践者（CEO、政策制定者、投资者）提供差异化的"行动剧本"
3. **边界推演**：明确模型的适用条件和失效边界，预见未来挑战

**输出目标**：提供具有前瞻性和可操作性的战略洞察

## 第四环 (C): 语境重构 - 定义贡献

**核心任务**：阐述这个分析如何"重塑认知语境"

**思考路径**：
1. **贡献定位**：在宏大的知识地图中定位这个洞察的位置
2. **议程设置**：提出能引领未来思考方向的"新问题"和"新议程"
3. **价值升华**：回归时代命题，彰显思想格局和社会价值

**输出目标**：重新定义问题的认知框架，开启新探索

---

## 回答要求

1. **深度优先**：追求洞察的深刻性，而非表面的全面性
2. **创造性**：不满足于应用现有理论，要创造新的理论框架
3. **结构化**：使用Markdown格式（标题、列表、粗体、代码块、表格等）清晰呈现思维层次
4. **前瞻性**：不仅解释过去，更要塑造对未来的理解
5. **基于事实**：所有洞察必须源自参考资料，不编造信息
6. **承认局限**：如果资料不足以支撑深度分析，明确说明

请开始你的E-P-I-C认知分析："""
    
    def _call_deepseek(self, prompt: str) -> str:
        """调用DeepSeek API (非流式，用于兼容)
        
        Args:
            prompt: 提示词
            
        Returns:
            str: API返回的回答
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # 使用推理模型 deepseek-reasoner
        data = {
            'model': 'deepseek-reasoner',
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,  # 降低随机性，提高准确性
            'max_tokens': 4000
        }
        
        try:
            print("正在调用DeepSeek推理模型...")
            response = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60  # 推理模型需要更长时间
            )
            
            if response.status_code == 200:
                result = response.json()
                # 推理模型返回包含reasoning_content和content
                message = result['choices'][0]['message']
                reasoning = message.get('reasoning_content', '')
                answer = message.get('content', '')
                
                # 如果有推理过程，可以记录或展示
                if reasoning:
                    print(f"推理过程长度: {len(reasoning)} 字符")
                
                print("API调用成功")
                return answer
            else:
                error_msg = f"API调用失败: {response.status_code} - {response.text}"
                print(error_msg)
                return f"抱歉，AI服务暂时不可用。错误信息：{error_msg}"
        
        except requests.Timeout:
            return "抱歉，AI服务响应超时，请稍后重试。"
        except Exception as e:
            return f"抱歉，调用AI服务时出错：{str(e)}"
    
    def call_deepseek_stream(self, prompt: str):
        """调用DeepSeek API 流式输出
        
        Args:
            prompt: 提示词
            
        Yields:
            tuple: (type, content) - type为'reasoning'或'content'
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # 使用推理模型 deepseek-reasoner，启用流式输出
        data = {
            'model': 'deepseek-reasoner',
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 4000,
            'stream': True  # 启用流式输出
        }
        
        try:
            print("正在调用DeepSeek推理模型（流式）...")
            response = requests.post(
                f"{self.api_url}/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=60,
                stream=True  # 启用流式响应
            )
            
            if response.status_code == 200:
                import json
                
                for line in response.iter_lines():
                    if line:
                        line = line.decode('utf-8')
                        if line.startswith('data: '):
                            line = line[6:]  # 移除 'data: ' 前缀
                            
                            if line.strip() == '[DONE]':
                                break
                            
                            try:
                                chunk = json.loads(line)
                                delta = chunk['choices'][0]['delta']
                                
                                # 推理模型先返回reasoning_content，再返回content
                                if 'reasoning_content' in delta:
                                    # 推理过程
                                    reasoning_text = delta['reasoning_content']
                                    if reasoning_text:
                                        yield ('reasoning', reasoning_text)
                                
                                if 'content' in delta:
                                    # 最终答案
                                    content = delta['content']
                                    if content:
                                        yield ('content', content)
                                        
                            except json.JSONDecodeError:
                                continue
                
                print("流式API调用完成")
            else:
                error_msg = f"API调用失败: {response.status_code}"
                print(error_msg)
                yield ('error', f"\n\n抱歉，AI服务暂时不可用。")
        
        except Exception as e:
            print(f"流式调用出错: {e}")
            yield ('error', f"\n\n抱歉，调用AI服务时出错：{str(e)}")
    
    def _get_mock_answer(self, question: str, search_results: List[Dict]) -> str:
        """获取模拟答案（当API未配置时）
        
        Args:
            question: 用户问题
            search_results: 搜索结果
            
        Returns:
            str: 模拟的回答
        """
        # 提取最相关的文本片段
        top_result = search_results[0] if search_results else None
        
        if not top_result:
            return "抱歉，在知识库中未找到相关信息。"
        
        answer = f"基于知识库中的相关内容，关于「{question}」的信息如下：\n\n"
        answer += f"{top_result['text'][:500]}...\n\n"
        answer += "（注意：当前为演示模式，未连接真实AI服务。请配置DeepSeek API密钥以获得智能回答。）"
        
        return answer
    
    def _get_no_context_answer(self, question: str) -> str:
        """当没有找到相关上下文时的回答"""
        return f"抱歉，在知识库中未找到与「{question}」相关的内容。\n\n建议：\n1. 尝试使用不同的关键词\n2. 确保相关文档已上传到知识库\n3. 检查问题表述是否清晰"
    
    def _format_sources(self, search_results: List[Dict]) -> List[Dict]:
        """格式化引用来源
        
        Args:
            search_results: 搜索结果列表
            
        Returns:
            List[Dict]: 格式化的来源列表
        """
        sources = []
        seen_docs = set()  # 避免重复
        
        for result in search_results:
            meta = result['metadata']
            doc_id = meta.get('document_id')
            
            # 避免同一文档重复出现
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            
            sources.append({
                'document_id': doc_id,
                'document_title': meta.get('title', '未知文档'),
                'chunk_index': meta.get('chunk_index', 0),
                'relevance': result.get('relevance', 0),
                'preview': meta.get('chunk_preview', '')
            })
        
        return sources


# 全局RAG服务实例（延迟初始化）
_rag_service = None

def get_rag_service(vector_store, api_key: str, api_url: str) -> RAGService:
    """获取全局RAG服务实例"""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService(vector_store, api_key, api_url)
    return _rag_service

