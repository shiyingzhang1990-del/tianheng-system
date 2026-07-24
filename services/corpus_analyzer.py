import json
import re
import requests
from collections import Counter
from flask import current_app

def analyze_corpus(content):
    """
    分析语料库内容，提取写作风格特征（集成AI分析）
    
    参数:
    content (str): 语料库文本内容
    
    返回:
    dict: 包含词频统计、写作风格特征、语调分析和AI深度分析的字典
    """
    try:
        # 传统分析方法
        word_frequency = analyze_word_frequency(content)
        style_features = analyze_style_features(content)
        tone_analysis = analyze_tone(content)
        
        # AI深度分析
        ai_analysis = call_ai_corpus_analysis(content)
        
        # 合并分析结果
        result = {
            'word_frequency': word_frequency,
            'style_features': style_features,
            'tone_analysis': tone_analysis
        }
        
        # 如果AI分析成功，添加AI分析结果并使用优化的词频统计
        if ai_analysis:
            # 使用AI优化的词频统计替换传统统计
            if 'enhanced_word_frequency' in ai_analysis:
                result['word_frequency'] = ai_analysis['enhanced_word_frequency']
                current_app.logger.info("Using AI-enhanced word frequency analysis")
            
            # 添加其他AI分析结果
            for key, value in ai_analysis.items():
                if key != 'enhanced_word_frequency':
                    result[key] = value
            
            current_app.logger.info("AI corpus analysis completed successfully")
        else:
            current_app.logger.warning("AI corpus analysis failed, using traditional analysis only")
        
        return result
        
    except Exception as e:
        current_app.logger.error(f"Error analyzing corpus: {e}")
        return {
            'word_frequency': [],
            'style_features': [],
            'tone_analysis': {'professional': 0, 'neutral': 0, 'casual': 0}
        }

def analyze_word_frequency(content):
    """
    分析文本中的词频
    
    参数:
    content (str): 文本内容
    
    返回:
    list: 词频统计列表，每项包含词和出现次数
    """
    # 分词并统计频率
    words = re.findall(r'\w+', content.lower())
    word_freq = Counter()
    
    # 停用词列表
    stop_words = {'的', '了', '和', '是', '在', '我', '有', '这', '个', '你', '们', '与', '之', '或', '等', '及', '也'}
    
    for word in words:
        if len(word) > 1 and word not in stop_words:
            word_freq[word] += 1
    
    # 取频率最高的20个词
    most_common = word_freq.most_common(20)
    
    return [{'word': word, 'count': count} for word, count in most_common]

def analyze_style_features(content):
    """
    分析文本的写作风格特征
    
    参数:
    content (str): 文本内容
    
    返回:
    list: 写作风格特征列表，每项包含特征名称和值
    """
    features = []
    
    # 分割句子和段落
    sentences = re.split(r'[。！？]', content)
    sentences = [s for s in sentences if len(s.strip()) > 0]
    
    paragraphs = content.split('\n\n')
    paragraphs = [p for p in paragraphs if len(p.strip()) > 0]
    
    # 计算句子平均长度
    if sentences:
        avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
        features.append({
            'name': '句子平均长度',
            'value': f'{avg_sentence_length:.1f}个字'
        })
    
    # 计算段落平均句子数
    if paragraphs and sentences:
        sentences_per_paragraph = len(sentences) / len(paragraphs)
        features.append({
            'name': '段落平均长度',
            'value': f'{sentences_per_paragraph:.1f}句'
        })
    
    # 计算形容词使用频率
    adjectives = ['大', '小', '好', '坏', '高', '低', '新', '旧', '快', '慢', '重要', '关键', '显著', '明显']
    adj_count = sum(content.count(adj) for adj in adjectives)
    if len(content) > 0:
        adj_ratio = adj_count / len(content) * 100
        features.append({
            'name': '形容词使用频率',
            'value': f'{adj_ratio:.1f}%'
        })
    
    # 计算专业术语占比
    professional_terms = ['经济', '金融', '市场', '政策', '增长', '发展', '投资', '风险', '监管', '改革']
    term_count = sum(content.count(term) for term in professional_terms)
    if len(content) > 0:
        term_ratio = term_count / len(content) * 100
        features.append({
            'name': '专业术语占比',
            'value': f'{term_ratio:.1f}%'
        })
    
    return features

def analyze_tone(content):
    """
    分析文本的语调
    
    参数:
    content (str): 文本内容
    
    返回:
    dict: 语调分析结果，包含专业性、中立性和随意性的百分比
    """
    # 专业性指标词
    professional_indicators = [
        '研究表明', '数据显示', '分析认为', '专家指出', '根据统计', 
        '理论', '模型', '体系', '机制', '战略', '规划', '政策',
        '因此', '然而', '此外', '综上所述', '总结'
    ]
    
    # 随意性指标词
    casual_indicators = [
        '我觉得', '我认为', '其实', '真的', '挺', '蛮', '很', '非常',
        '哈', '嗯', '呢', '吧', '啊', '哦', '嘿', '嘻'
    ]
    
    # 计算各类指标出现次数
    professional_count = sum(content.count(ind) for ind in professional_indicators)
    casual_count = sum(content.count(ind) for ind in casual_indicators)
    total_count = professional_count + casual_count
    
    # 如果没有足够的指标词，设置默认值
    if total_count < 10:
        return {
            'professional': 60,
            'neutral': 30,
            'casual': 10
        }
    
    # 计算各类型占比
    professional_ratio = min(professional_count / total_count * 100, 100)
    casual_ratio = min(casual_count / total_count * 100, 100)
    neutral_ratio = max(100 - professional_ratio - casual_ratio, 0)
    
    return {
        'professional': round(professional_ratio),
        'neutral': round(neutral_ratio),
        'casual': round(casual_ratio)
    }

def call_ai_corpus_analysis(content):
    """
    调用AI模型进行语料库深度分析
    
    参数:
    content (str): 语料库文本内容
    
    返回:
    dict: AI分析结果
    """
    try:
        api_url = current_app.config.get('AI_MODEL_API_URL')
        api_key = current_app.config.get('AI_MODEL_API_KEY')
        
        if not api_url or not api_key:
            current_app.logger.error("AI model configuration not found")
            return None
        
        # 智能截取内容以适应模型限制
        max_content_length = 4000
        if len(content) > max_content_length:
            # 取开头和结尾，保持内容完整性
            start_content = content[:max_content_length//2]
            end_content = content[-max_content_length//2:]
            display_content = start_content + "\n\n[内容截取...]\n\n" + end_content
        else:
            display_content = content
        
        # 构建语料分析提示词
        prompt = f"""
你是一位专业的语料库分析师，请对以下语料库内容进行深度分析。要求基于内容进行专业分析，提供写作风格、主题特征和语言特点的深度洞察。

语料库内容：
{display_content}

请按照以下要求进行专业分析：

## 分析要求：

### 1. 主题分析 (theme_analysis)
- 识别语料库的主要主题和子主题
- 分析内容的专业领域和知识范围
- 评估主题的一致性和深度
- 提供主题分布和重点领域分析

### 2. 写作风格深度分析 (writing_style)
- 分析语言风格特征（正式/非正式、学术/通俗等）
- 评估句式结构和表达习惯
- 分析修辞手法和表达技巧
- 识别独特的写作特色和风格倾向

### 3. 语言质量评估 (language_quality)
- 评估语言的准确性、流畅性和专业性
- 分析词汇使用的丰富度和准确性
- 评估语法和表达的规范性
- 提供语言改进建议

### 4. 内容结构分析 (content_structure)
- 分析内容的组织结构和逻辑层次
- 评估段落安排和内容衔接
- 分析论证方式和论述逻辑
- 识别内容的结构特点

### 5. 专业程度评估 (professional_level)
- 评估内容的专业深度和学术水平
- 分析专业术语使用的准确性和丰富度
- 评估内容的权威性和可信度
- 提供专业水平提升建议

### 6. 词频统计优化 (word_frequency_enhancement)
- 基于AI分析结果，优化词频统计的准确性
- 识别真正重要的专业词汇和核心概念
- 过滤掉无意义的停用词和常见词汇
- 提取具有分析价值的术语和关键词

## 输出格式（严格JSON）：
{{
    "theme_analysis": {{
        "main_themes": ["主题1", "主题2", "主题3"],
        "professional_domain": "专业领域描述",
        "theme_consistency": 0.85,
        "depth_analysis": "深度分析描述"
    }},
    "writing_style": {{
        "style_type": "风格类型描述",
        "language_level": "语言水平评估",
        "expression_characteristics": ["特征1", "特征2", "特征3"],
        "unique_features": "独特特征描述"
    }},
    "language_quality": {{
        "accuracy_score": 0.9,
        "fluency_score": 0.85,
        "professional_score": 0.88,
        "improvement_suggestions": ["建议1", "建议2", "建议3"]
    }},
    "content_structure": {{
        "organization_score": 0.87,
        "logic_clarity": 0.82,
        "coherence_level": 0.85,
        "structure_analysis": "结构分析描述"
    }},
    "professional_level": {{
        "expertise_score": 0.83,
        "terminology_usage": 0.89,
        "authority_level": 0.86,
        "enhancement_recommendations": ["建议1", "建议2", "建议3"]
    }},
    "enhanced_word_frequency": [
        {{"word": "专业术语1", "count": 15, "importance": "high", "category": "核心概念"}},
        {{"word": "专业术语2", "count": 12, "importance": "medium", "category": "关键指标"}},
        {{"word": "专业术语3", "count": 8, "importance": "high", "category": "重要实体"}}
    ]
}}

注意：所有分析都要基于内容进行专业判断，提供具体的评估分数和改进建议。
"""
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'qwen-plus',
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'temperature': 0.7,
            'max_tokens': 2000
        }
        
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=1200  # 20分钟 = 1200秒
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_content = result['choices'][0]['message']['content']
            
            # 尝试解析AI返回的JSON
            try:
                # 提取JSON部分
                json_start = ai_content.find('{')
                json_end = ai_content.rfind('}') + 1
                if json_start != -1 and json_end > json_start:
                    json_str = ai_content[json_start:json_end]
                    analysis_result = json.loads(json_str)
                    
                    # 验证必要字段
                    required_fields = ['theme_analysis', 'writing_style', 'language_quality', 'content_structure', 'professional_level', 'enhanced_word_frequency']
                    if all(field in analysis_result for field in required_fields):
                        return analysis_result
                    else:
                        current_app.logger.warning("AI response missing required fields")
                        return None
                else:
                    current_app.logger.warning("No valid JSON found in AI response")
                    return None
                    
            except json.JSONDecodeError as e:
                current_app.logger.error(f"Failed to parse AI response as JSON: {e}")
                return None
        else:
            current_app.logger.error(f"AI API request failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Error calling AI corpus analysis: {e}")
        return None
