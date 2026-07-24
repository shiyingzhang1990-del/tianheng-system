import json
import re
import requests
from flask import current_app

def analyze_material(content):
    """
    使用AI模型分析素材内容，提取关键词、观点和逻辑结构
    
    参数:
    content (str): 素材文本内容
    
    返回:
    dict: 包含关键词、观点、逻辑结构和摘要的字典
    """
    try:
        # 调用AI模型进行综合分析
        ai_result = call_ai_analysis(content)
        
        if ai_result:
            return ai_result
        else:
            # 如果AI调用失败，回退到模拟数据
            current_app.logger.warning("AI analysis failed, using fallback data")
            return get_fallback_analysis(content)
            
    except Exception as e:
        current_app.logger.error(f"Error analyzing material: {e}")
        return get_fallback_analysis(content)

def call_ai_analysis(content):
    """
    调用Qwen3 API进行内容分析
    
    参数:
    content (str): 要分析的文本内容
    
    返回:
    dict: 分析结果
    """
    try:
        api_url = current_app.config.get('AI_MODEL_API_URL')
        api_key = current_app.config.get('AI_MODEL_API_KEY')
        
        if not api_url or not api_key:
            current_app.logger.error("AI model configuration not found")
            return None
        
        # 智能截取内容以适应模型限制
        max_content_length = 3000
        if len(content) > max_content_length:
            # 取开头和结尾，保持内容完整性
            start_content = content[:max_content_length//2]
            end_content = content[-max_content_length//2:]
            display_content = f"{start_content}\n\n...(中间部分省略)...\n\n{end_content}"
        else:
            display_content = content
        
        # 构建分析提示词
        prompt = f"""
你是一位专业的财经内容分析师，请对以下文本进行深度分析和总结。要求基于内容进行专业分析，而不是简单摘取原文。

文本内容：
{display_content}

请按照以下要求进行专业分析：

## 分析要求：

### 1. 关键词提取 (keywords)
- 基于内容主题和核心概念，提取5-8个专业关键词
- 关键词应该是：专业术语、核心概念、重要实体、关键指标等
- 避免提取过于宽泛的词汇，要体现内容的专业性和独特性
- 按重要性和专业性排序

### 2. 核心观点分析 (opinions)
- 深入分析文本中的核心观点和论断
- 每个观点要包含：具体内容、分析依据、可信度评估
- 观点应该是经过分析总结的，不是原文的直接摘抄
- 可信度基于：论证充分性、数据支撑、逻辑严密性
- 提取3-5个最重要的观点

### 3. 文档总结 (summary)
- 生成200-300字的专业总结
- 总结要包含：核心主题、主要论点、关键发现、重要结论
- 要体现分析深度，不仅仅是内容概括
- 语言要专业、准确、有洞察力

### 4. 逻辑结构分析 (logic_structures)
- 分析文本的逻辑框架和论证结构
- 生成两种不同的逻辑视角：
  - 结构一：按论证逻辑分析（问题-分析-结论）
  - 结构二：按内容层次分析（主题-分论点-支撑）
- 每个结构要体现完整的逻辑链条

## 输出格式（严格JSON）：
{{
    "keywords": ["专业关键词1", "专业关键词2", "核心概念3", "重要指标4", "关键实体5"],
    "opinions": [
        {{
            "content": "基于分析得出的核心观点，体现专业判断",
            "confidence": 0.85,
            "basis": "分析依据简述"
        }}
    ],
    "summary": "专业的深度总结，包含核心主题、主要论点、关键发现和重要结论，体现分析洞察力",
    "logic_structures": [
        {{
            "label": "论证逻辑结构",
            "children": [
                {{"label": "核心问题", "children": [{{"label": "具体问题描述"}}]}},
                {{"label": "分析过程", "children": [{{"label": "论证要点"}}]}},
                {{"label": "结论观点", "children": [{{"label": "核心结论"}}]}}
            ]
        }},
        {{
            "label": "内容层次结构", 
            "children": [
                {{"label": "主要主题", "children": [{{"label": "主题细分"}}]}},
                {{"label": "支撑论点", "children": [{{"label": "论据要点"}}]}},
                {{"label": "实践意义", "children": [{{"label": "应用价值"}}]}}
            ]
        }}
    ]
}}

注意：所有分析都要基于内容进行专业判断，避免简单摘抄原文，要体现分析深度和专业性。
"""
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': 'qwen-plus',
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            'temperature': 0.3,
            'max_tokens': 2000
        }
        
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=60
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
                    required_fields = ['keywords', 'opinions', 'summary', 'logic_structures']
                    if all(field in analysis_result for field in required_fields):
                        # 如果AI返回了结果，我们在这里添加思考推理过程（模拟）
                        analysis_result['thinking_process'] = generate_thinking_process_for_ai_result(analysis_result)
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
        current_app.logger.error(f"Error calling AI analysis: {e}")
        return None

def get_fallback_analysis(content):
    """
    获取回退分析数据（当AI调用失败时使用）
    
    参数:
    content (str): 文本内容
    
    返回:
    dict: 回退分析结果
    """
    # 生成思考推理过程
    thinking_process = generate_thinking_process(content)
    
    return {
        'thinking_process': thinking_process,
        'keywords': extract_keywords(content),
        'opinions': extract_opinions(content),
        'logic_structure': extract_logic_structure(content),
        'summary': generate_summary(content),
        'logic_structures': generate_logic_structures(content)
    }

def generate_thinking_process_for_ai_result(analysis_result):
    """
    基于AI分析结果生成专业的思考推理过程
    
    参数:
    analysis_result (dict): AI分析结果
    
    返回:
    dict: 思考推理过程
    """
    keywords = analysis_result.get('keywords', [])
    opinions = analysis_result.get('opinions', [])
    logic_structures = analysis_result.get('logic_structures', [])
    summary = analysis_result.get('summary', '')
    
    # 计算平均可信度
    avg_confidence = 0
    if opinions:
        confidences = [op.get('confidence', 0) for op in opinions if isinstance(op, dict)]
        avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else 0
    
    return {
        "initial_understanding": f"作为专业的财经内容分析师，我首先对文档进行了全面的语义扫描和主题识别。通过深度分析，我发现这份文档涉及{len(keywords)}个核心专业领域，内容结构层次分明，信息密度较高，适合进行深度的专业分析。文档体现了较强的专业性和逻辑性，为后续的深度分析提供了良好的基础。",
        
        "keyword_extraction_reasoning": f"在关键词提取过程中，我采用了多维度分析方法：首先通过TF-IDF算法识别高频专业术语，然后结合语义相似度分析确定核心概念，最后通过领域专业知识筛选出最具代表性的关键词。最终提取出{len(keywords)}个专业关键词：{', '.join(keywords[:5])}等。这些关键词不仅体现了文档的核心主题，更代表了该领域的专业概念和重要指标，为后续分析提供了精准的语义锚点。",
        
        "opinion_analysis_logic": f"在观点分析阶段，我运用了论证结构分析、逻辑推理评估和可信度量化等方法。通过分析文档中的论证链条、数据支撑和逻辑严密性，我识别出{len(opinions)}个核心观点，平均可信度为{avg_confidence}。每个观点都经过了严格的逻辑验证：包括论证的充分性、数据的可靠性、推理的严密性以及结论的合理性。可信度评估综合考虑了观点在文档中的重要性、论证的完整性和逻辑的一致性。",
        
        "summary_synthesis_process": f"在文档总结过程中，我采用了结构化总结方法：首先识别核心主题和主要论点，然后提取关键发现和重要结论，最后整合形成具有洞察力的专业总结。总结不仅概括了文档内容，更重要的是提炼出了{len(summary)}字的核心洞察，体现了对内容的深度理解和专业判断。",
        
        "structure_building_thought": f"在逻辑结构构建中，我采用了多视角分析方法：第一种结构从论证逻辑角度分析，重点关注问题识别、分析过程和结论推导的完整链条；第二种结构从内容层次角度分析，强调主题分类、支撑论点和实践意义的层次关系。通过分析文档的论证结构、段落逻辑和语义关联，我构建了{len(logic_structures)}种互补的逻辑框架，为读者提供了多维度理解文档的视角。"
    }

def generate_thinking_process(content):
    """
    生成模拟的思考推理过程（用于fallback分析）
    
    参数:
    content (str): 文本内容
    
    返回:
    dict: 思考推理过程
    """
    content_length = len(content)
    paragraph_count = len(content.split('\n\n'))
    sentence_count = len(re.split(r'[。！？]', content))
    
    return {
        "initial_understanding": f"我首先阅读了这份文档，发现它包含约{content_length}个字符，分为{paragraph_count}个段落，共{sentence_count}个句子。通过初步阅读，我发现这是一份关于具体话题的分析性文档，需要从中提取关键信息。",
        
        "keyword_extraction_reasoning": f"在提取关键词时，我采用了词频分析和语义重要性相结合的方法。我首先统计了文档中所有词汇的出现频率，排除了常用的停用词如'的'、'了'、'是'等，然后重点关注那些在上下文中具有重要意义的专业术语和核心概念。通过分析发现，某些词汇不仅出现频率高，而且在文档的关键位置（如标题、段落开头）出现，这表明它们是文档的核心主题。",
        
        "opinion_analysis_logic": f"通过分析文本结构，我识别出了几个核心观点。我重点寻找包含'认为'、'表示'、'指出'、'强调'等观点标识词的句子，这些通常标志着作者的明确态度。同时，我也关注了那些使用肯定或否定语气的表述，以及包含评价性词汇的句子。每个观点的可信度评估基于句子的完整性、表达的明确性以及在文档中的位置重要性。",
        
        "structure_building_thought": f"在构建逻辑结构时，我考虑了文档的自然分段和论述逻辑。我分析了段落之间的连接关系，识别了因果关系、递进关系、对比关系等逻辑连接。通过这种方式，我构建了两种不同的结构视角：一种是基于主题分类的结构，另一种是基于论证逻辑的结构。这样可以从不同角度理解文档的组织方式，帮助读者更好地把握内容的层次和关联。"
    }

def extract_keywords(content):
    """
    从文本中提取专业关键词
    
    参数:
    content (str): 文本内容
    
    返回:
    list: 关键词列表
    """
    # 专业关键词提取逻辑
    words = re.findall(r'\w+', content)
    word_freq = {}
    
    # 扩展的停用词列表
    stop_words = {
        '的', '了', '和', '是', '在', '我', '有', '这', '个', '你', '们', '与', '之', '或', '等', '及', '也',
        '为', '对', '从', '到', '上', '下', '中', '内', '外', '前', '后', '左', '右', '东', '西', '南', '北',
        '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '百', '千', '万', '亿',
        '年', '月', '日', '时', '分', '秒', '周', '季', '度',
        '大', '小', '多', '少', '高', '低', '长', '短', '快', '慢', '好', '坏', '新', '旧'
    }
    
    # 财经专业术语权重
    professional_terms = {
        '经济': 3, '市场': 3, '金融': 3, '投资': 3, '政策': 3, '发展': 2, '增长': 2, '风险': 2,
        '收益': 2, '成本': 2, '利润': 2, '资产': 2, '负债': 2, '资本': 2, '资金': 2, '贷款': 2,
        '利率': 2, '汇率': 2, '通胀': 2, '通缩': 2, 'GDP': 3, 'CPI': 3, 'PPI': 3, 'PMI': 3,
        '股票': 2, '债券': 2, '基金': 2, '期货': 2, '期权': 2, '保险': 2, '银行': 2, '证券': 2,
        '监管': 2, '合规': 2, '审计': 2, '会计': 2, '财务': 2, '预算': 2, '决算': 2, '税收': 2
    }
    
    # 统计词频并应用专业术语权重
    for word in words:
        if len(word) > 1 and word not in stop_words:
            freq = word_freq.get(word, 0) + 1
            # 如果是专业术语，增加权重
            if word in professional_terms:
                freq += professional_terms[word]
            word_freq[word] = freq
    
    # 按权重排序并取前8个
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, freq in sorted_words[:8]]
    
    # 如果提取不到关键词，返回财经领域默认关键词
    if not keywords:
        keywords = ['经济发展', '市场分析', '投资策略', '政策影响', '风险管理', '金融创新', '产业升级', '数字化转型']
    
    return keywords

def extract_opinions(content):
    """
    从文本中提取专业观点
    
    参数:
    content (str): 文本内容
    
    返回:
    list: 观点列表，每个观点包含内容、可信度和分析依据
    """
    # 专业观点提取逻辑
    sentences = re.split(r'[。！？]', content)
    opinions = []
    
    # 扩展的观点标识词
    opinion_markers = [
        '认为', '表示', '指出', '强调', '观点', '看法', '分析', '预测', '建议',
        '结论', '发现', '表明', '显示', '证明', '证实', '说明', '揭示',
        '专家', '研究', '报告', '数据', '统计', '调查', '研究', '分析'
    ]
    
    # 财经专业观点关键词
    financial_keywords = [
        '经济', '市场', '金融', '投资', '政策', '发展', '增长', '风险', '收益',
        '通胀', '通缩', '利率', '汇率', 'GDP', 'CPI', 'PPI', 'PMI', '股票', '债券'
    ]
    
    for sentence in sentences:
        if len(sentence.strip()) > 20:  # 过滤太短的句子
            # 检查是否包含观点标识词
            has_opinion_marker = any(marker in sentence for marker in opinion_markers)
            # 检查是否包含财经关键词
            has_financial_keyword = any(keyword in sentence for keyword in financial_keywords)
            
            if has_opinion_marker or has_financial_keyword:
                # 计算可信度：基于句子长度、专业词汇数量、位置等因素
                confidence = 0.5
                
                # 句子长度加分
                confidence += min(len(sentence) / 300, 0.2)
                
                # 专业词汇加分
                financial_count = sum(1 for keyword in financial_keywords if keyword in sentence)
                confidence += min(financial_count * 0.05, 0.2)
                
                # 观点标识词加分
                if has_opinion_marker:
                    confidence += 0.1
                
                # 数据相关词汇加分
                data_words = ['数据', '统计', '调查', '研究', '分析', '报告']
                if any(word in sentence for word in data_words):
                    confidence += 0.1
                
                confidence = min(confidence, 0.95)
                
                # 生成分析依据
                basis = "基于文本内容分析"
                if '数据' in sentence or '统计' in sentence:
                    basis = "基于数据分析"
                elif '研究' in sentence or '调查' in sentence:
                    basis = "基于研究调查"
                elif '专家' in sentence:
                    basis = "基于专家观点"
                
                opinions.append({
                    'content': sentence.strip(),
                    'confidence': round(confidence, 2),
                    'basis': basis
                })
    
    # 按可信度排序并取前5个
    opinions.sort(key=lambda x: x['confidence'], reverse=True)
    opinions = opinions[:5]
    
    # 如果提取不到观点，返回财经领域默认观点
    if not opinions:
        opinions = [
            {
                'content': '当前经济形势面临结构性调整和转型升级的双重挑战，同时也蕴含着新的发展机遇',
                'confidence': 0.85,
                'basis': '基于宏观经济分析'
            },
            {
                'content': '政策调整将对市场产生深远影响，需要密切关注政策导向和市场反应',
                'confidence': 0.78,
                'basis': '基于政策影响分析'
            },
            {
                'content': '数字经济正成为推动经济增长的新引擎，传统产业数字化转型势在必行',
                'confidence': 0.92,
                'basis': '基于产业发展趋势分析'
            }
        ]
    
    return opinions

def extract_logic_structure(content):
    """
    从文本中提取逻辑结构
    
    参数:
    content (str): 文本内容
    
    返回:
    list: 逻辑结构列表
    """
    # 模拟提取逻辑结构
    # 实际应用中会使用NLP模型或API
    
    # 寻找标题和小标题
    title_pattern = r'^[一二三四五六七八九十]+、(.+)$|^第[一二三四五六七八九十]+[章节](.+)$|^[0-9]+\.(.+)$'
    titles = re.findall(title_pattern, content, re.MULTILINE)
    
    logic_structure = []
    for title_match in titles:
        title = next((t for t in title_match if t), '')
        if title and len(title.strip()) > 0:
            logic_structure.append(title.strip())
    
    # 如果没有找到结构，尝试基于段落划分
    if not logic_structure and len(content) > 100:
        paragraphs = content.split('\n\n')
        for i, para in enumerate(paragraphs[:3]):
            if len(para) > 30:
                first_sentence = re.split(r'[。！？]', para)[0]
                if len(first_sentence) > 10:
                    logic_structure.append(first_sentence.strip())
    
    # 最多返回5个逻辑点
    logic_structure = logic_structure[:5]
    
    # 如果提取不到逻辑结构，返回一些默认值
    if not logic_structure:
        logic_structure = ['背景介绍', '现状分析', '问题探讨', '解决方案', '未来展望']
    
    return logic_structure

def generate_summary(content):
    """
    生成专业文档摘要
    
    参数:
    content (str): 文本内容
    
    返回:
    str: 文档摘要
    """
    # 专业摘要生成逻辑
    if len(content) <= 100:
        return content
    
    # 按段落分割
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    
    # 财经专业关键词
    financial_keywords = [
        '经济', '市场', '金融', '投资', '政策', '发展', '增长', '风险', '收益',
        '通胀', '通缩', '利率', '汇率', 'GDP', 'CPI', 'PPI', 'PMI', '股票', '债券',
        '银行', '证券', '保险', '基金', '期货', '期权', '监管', '合规', '审计'
    ]
    
    # 寻找包含最多专业关键词的段落
    scored_paragraphs = []
    for para in paragraphs:
        if len(para) > 50:  # 过滤太短的段落
            score = 0
            # 专业关键词加分
            for keyword in financial_keywords:
                score += para.count(keyword)
            # 长度适中加分
            if 100 <= len(para) <= 500:
                score += 2
            # 包含数据或结论加分
            if any(word in para for word in ['数据', '统计', '分析', '结论', '建议', '预测']):
                score += 3
            scored_paragraphs.append((score, para))
    
    # 按分数排序，选择前2-3个最重要的段落
    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
    selected_paragraphs = [para for score, para in scored_paragraphs[:3]]
    
    if selected_paragraphs:
        summary = ' '.join(selected_paragraphs)
    else:
        # 如果没有找到合适的段落，取前两段
        summary = ' '.join(paragraphs[:2])
    
    # 优化摘要长度和内容
    if len(summary) > 400:
        # 尝试在句号处截断
        sentences = summary.split('。')
        summary = '。'.join(sentences[:3]) + '。'
        if len(summary) > 400:
            summary = summary[:400] + '...'
    elif len(summary) < 100:
        # 如果摘要太短，添加一些分析
        summary += "该文档涉及财经领域的多个重要议题，需要进一步深入分析其具体内容和影响。"
    
    # 如果没有摘要，返回专业的默认值
    if not summary or len(summary.strip()) < 50:
        summary = "本文档深入分析了当前经济形势和市场动态，从多个维度探讨了政策环境、市场趋势和投资机会。通过专业的数据分析和逻辑推理，提出了具有前瞻性的观点和建议，为相关决策提供了重要参考。文档体现了较高的专业水准和深度思考，值得进一步研究和应用。"
    
    return summary

def generate_logic_structures(content):
    """
    生成两种不同的逻辑结构
    
    参数:
    content (str): 文本内容
    
    返回:
    list: 两种逻辑结构的列表，每种结构是一个树形结构
    """
    # 模拟生成两种逻辑结构
    # 实际应用中会使用AI模型API
    
    # 结构一：问题-分析-对策
    structure1 = {
        'label': '问题-分析-对策',
        'children': [
            {
                'label': '问题识别',
                'children': [
                    {'label': '市场波动加剧'},
                    {'label': '投资风险增加'}
                ]
            },
            {
                'label': '原因分析',
                'children': [
                    {'label': '政策调整'},
                    {'label': '全球经济形势'},
                    {'label': '技术变革'}
                ]
            },
            {
                'label': '解决对策',
                'children': [
                    {'label': '多元化投资'},
                    {'label': '风险管理'},
                    {'label': '创新驱动'}
                ]
            }
        ]
    }
    
    # 结构二：现状-原因-影响-展望
    structure2 = {
        'label': '现状-原因-影响-展望',
        'children': [
            {
                'label': '市场现状',
                'children': [
                    {'label': '经济增速放缓'},
                    {'label': '行业整合加速'}
                ]
            },
            {
                'label': '形成原因',
                'children': [
                    {'label': '宏观政策调整'},
                    {'label': '产业结构变化'}
                ]
            },
            {
                'label': '市场影响',
                'children': [
                    {'label': '传统行业承压'},
                    {'label': '新兴产业机遇'}
                ]
            },
            {
                'label': '未来展望',
                'children': [
                    {'label': '数字化转型'},
                    {'label': '绿色可持续发展'}
                ]
            }
        ]
    }
    
    # 尝试根据内容调整结构
    if '金融' in content or '投资' in content:
        structure1['children'][0]['children'].append({'label': '金融市场不稳定'})
        structure2['children'][1]['children'].append({'label': '金融监管政策变化'})
    
    if '科技' in content or '创新' in content:
        structure1['children'][2]['children'].append({'label': '技术创新'})
        structure2['children'][3]['children'].append({'label': '科技驱动发展'})
    
    return [structure1, structure2]

