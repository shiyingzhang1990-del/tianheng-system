import json
import re
import requests
from flask import current_app

def generate_article_stream(keywords, opinions, logic_structure, selected_logic=None, style_preference='balanced', word_count=1000, custom_style=None, use_corpus=False, custom_instructions=None, logic_structures=None):
    """
    流式生成文章
    
    参数:
    同generate_article函数
    
    返回:
    generator: 生成器，每次yield一个内容块
    """
    try:
        # 调用AI模型流式生成文章
        ai_result = call_ai_generate_article_stream(
            keywords, opinions, logic_structure, selected_logic, 
            style_preference, word_count, custom_style, 
            use_corpus, custom_instructions, logic_structures
        )
        
        if ai_result:
            for chunk in ai_result:
                yield chunk
        else:
            # 如果AI调用失败，回退到模拟流式数据
            current_app.logger.warning("AI stream generation failed, using fallback")
            for chunk in get_fallback_article_stream(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures):
                yield chunk
            
    except Exception as e:
        current_app.logger.error(f"Error in stream article generation: {e}")
        yield "文章生成失败，请稍后重试。"

def generate_article(keywords, opinions, logic_structure, selected_logic=None, style_preference='balanced', word_count=1000, custom_style=None, use_corpus=False, custom_instructions=None, logic_structures=None):
    """
    使用AI模型生成文章
    
    参数:
    keywords (list): 关键词列表
    opinions (list): 观点列表
    logic_structure (list): 逻辑结构列表
    selected_logic (list): 用户选择的逻辑结构，默认为None表示使用所有逻辑结构
    style_preference (str): 写作风格偏好，可选值：'professional', 'balanced', 'vivid', 'custom'
    word_count (int): 目标字数
    custom_style (str): 自定义写作风格描述
    use_corpus (bool): 是否使用个人语料库
    custom_instructions (str): 自定义生成指令
    logic_structures (list): 两种逻辑结构的树形数据
    
    返回:
    str: 生成的文章内容
    """
    try:
        # 调用AI模型生成文章
        ai_result = call_ai_generate_article(
            keywords, opinions, logic_structure, selected_logic, 
            style_preference, word_count, custom_style, 
            use_corpus, custom_instructions, logic_structures
        )
        
        if ai_result:
            return ai_result
        else:
            # 如果AI调用失败，回退到模拟数据
            current_app.logger.warning("AI article generation failed, using fallback data")
            return get_fallback_article(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures)
            
    except Exception as e:
        current_app.logger.error(f"Error generating article: {e}")
        return get_fallback_article(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures)

def get_tone_by_style(style_preference, custom_style=None):
    """
    根据风格偏好获取写作语调参数
    
    参数:
    style_preference (str): 写作风格偏好
    custom_style (str): 自定义风格描述
    
    返回:
    dict: 语调参数
    """
    if style_preference == 'professional':
        return {
            'formal': True,
            'use_technical_terms': True,
            'sentence_length': 'long',
            'use_metaphors': False
        }
    elif style_preference == 'vivid':
        return {
            'formal': False,
            'use_technical_terms': False,
            'sentence_length': 'varied',
            'use_metaphors': True
        }
    elif style_preference == 'custom' and custom_style:
        # 解析自定义风格
        is_formal = '专业' in custom_style or '正式' in custom_style
        use_tech = '术语' in custom_style or '专业' in custom_style
        is_metaphor = '比喻' in custom_style or '生动' in custom_style
        
        if '简短' in custom_style:
            sentence_length = 'short'
        elif '冗长' in custom_style or '详细' in custom_style:
            sentence_length = 'long'
        else:
            sentence_length = 'medium'
            
        return {
            'formal': is_formal,
            'use_technical_terms': use_tech,
            'sentence_length': sentence_length,
            'use_metaphors': is_metaphor
        }
    else:  # balanced
        return {
            'formal': True,
            'use_technical_terms': True,
            'sentence_length': 'medium',
            'use_metaphors': True
        }

def generate_title(keywords, main_topic):
    """生成文章标题"""
    # 模拟标题生成
    if main_topic:
        return f"{main_topic}：基于{keywords[0]}和{keywords[1]}的分析"
    else:
        return f"{keywords[0]}与{keywords[1]}：当前形势与未来展望"

def generate_introduction(keywords, opinions, tone):
    """生成文章引言"""
    # 模拟引言生成
    intro = f"## 引言\n\n"
    intro += f"近年来，{keywords[0]}和{keywords[1]}的发展引起了广泛关注。"
    
    if opinions and len(opinions) > 0:
        intro += f"正如专家所指出的，\"{opinions[0]['content']}\"。"
    
    intro += f"本文将从多个角度分析{keywords[0]}的现状，探讨其与{keywords[2] if len(keywords) > 2 else keywords[1]}的关系，并对未来发展趋势进行展望。"
    
    return intro

def generate_section(section_title, keywords, opinions, tone):
    """生成文章章节"""
    # 模拟章节生成
    section = f"## {section_title}\n\n"
    
    # 添加1-2个段落
    paragraph1 = f"在{section_title}方面，{keywords[0]}表现出显著的特点。"
    
    # 根据是否使用专业术语调整内容
    if tone['use_technical_terms']:
        paragraph1 += f"从技术层面分析，{keywords[1]}与{keywords[2] if len(keywords) > 2 else keywords[0]}之间存在紧密的关联，这种关联主要体现在三个方面：资源配置、结构优化和效率提升。"
    else:
        paragraph1 += f"{keywords[1]}和{keywords[2] if len(keywords) > 2 else keywords[0]}相互影响，共同推动了整体发展。"
    
    # 添加观点引用
    relevant_opinions = [op for op in opinions if any(kw in op['content'] for kw in keywords[:3])]
    if relevant_opinions:
        op = relevant_opinions[0]
        paragraph1 += f"有研究表明，\"{op['content']}\"，这一观点得到了{int(op['confidence']*100)}%的数据支持。"
    
    # 第二段
    paragraph2 = f"从另一个角度看，{keywords[3] if len(keywords) > 3 else keywords[1]}也是影响{section_title}的重要因素。"
    
    # 根据句子长度偏好调整
    if tone['sentence_length'] == 'long':
        paragraph2 += f"综合考虑各种因素，包括政策环境、市场需求、技术创新以及国际形势等，我们可以预见{keywords[0]}在未来将呈现出更加多元化和复杂化的发展态势，这也对相关领域的研究和实践提出了更高的要求。"
    elif tone['sentence_length'] == 'short':
        paragraph2 += f"政策支持很关键。市场需求在变化。技术创新不断涌现。这些都影响着{keywords[0]}的发展。"
    else:
        paragraph2 += f"政策环境、市场需求和技术创新共同影响着{keywords[0]}的发展。未来，我们需要更加关注这些因素的变化，以把握发展机遇。"
    
    section += paragraph1 + "\n\n" + paragraph2
    
    return section

def generate_conclusion(keywords, opinions, tone):
    """生成文章结论"""
    # 模拟结论生成
    conclusion = f"## 结论与展望\n\n"
    
    conclusion += f"综上所述，{keywords[0]}的发展呈现出新的特点和趋势。"
    
    # 添加观点总结
    if opinions and len(opinions) > 1:
        conclusion += f"正如前文所述，\"{opinions[-1]['content']}\"，这一点值得我们深入思考。"
    
    # 根据是否使用比喻调整内容
    if tone['use_metaphors']:
        conclusion += f"未来，{keywords[0]}的发展道路犹如一条蜿蜒的河流，虽有曲折但终将汇入时代发展的大海。"
    else:
        conclusion += f"未来，{keywords[0]}的发展将面临机遇与挑战并存的局面，需要我们持续关注和研究。"
    
    conclusion += f"我们期待在{keywords[1]}和{keywords[2] if len(keywords) > 2 else keywords[0]}的共同作用下，相关领域能够取得更加丰硕的成果。"
    
    return conclusion

def expand_article(article, target_length):
    """扩展文章内容以达到目标字数"""
    current_length = len(article)
    
    if current_length >= target_length:
        return article
    
    # 找出所有章节
    sections = re.findall(r'## (.+)\n\n', article)
    
    # 如果字数差距较大，添加新章节
    if target_length - current_length > 500 and len(sections) < 5:
        new_section = """## 相关政策与影响分析

近年来，一系列相关政策的出台对行业发展产生了深远影响。政策导向明确，支持力度加大，为行业提供了良好的发展环境。从具体措施来看，包括资金支持、人才引进、技术创新等多个方面，形成了全方位的支持体系。

与此同时，政策实施过程中也面临一些挑战。如何平衡发展与规范之间的关系，如何确保政策的精准落地，都是需要进一步思考的问题。未来政策走向将更加注重质量和效益，推动行业高质量发展。"""
        
        # 在结论前插入新章节
        conclusion_pos = article.find("## 结论与展望")
        if conclusion_pos > 0:
            article = article[:conclusion_pos] + new_section + "\n\n" + article[conclusion_pos:]
        else:
            article += "\n\n" + new_section
    
    # 如果仍然不够长，扩展现有段落
    current_length = len(article)
    if current_length < target_length:
        expansion_text = """此外，从国际比较视角来看，我国在该领域的发展与国际先进水平相比仍有一定差距，主要体现在原始创新能力、高端人才储备以及产业链协同效应等方面。未来需要进一步加强国际合作，借鉴国外先进经验，同时发挥自身优势，走出一条具有中国特色的发展道路。

值得注意的是，随着数字化转型的深入推进，新技术、新模式、新业态不断涌现，为传统领域带来了革命性变化。人工智能、大数据、云计算等新一代信息技术的应用，极大地提升了效率和创新能力，也带来了新的发展机遇和挑战。"""
        
        # 在结论前插入扩展文本
        conclusion_pos = article.find("## 结论与展望")
        if conclusion_pos > 0:
            article = article[:conclusion_pos] + expansion_text + "\n\n" + article[conclusion_pos:]
        else:
            article += "\n\n" + expansion_text
    
    return article

def trim_article(article, target_length):
    """缩减文章内容以接近目标字数"""
    if len(article) <= target_length:
        return article
    
    # 按段落分割文章
    paragraphs = article.split("\n\n")
    
    # 保留标题、引言和结论
    essential_paragraphs = [p for p in paragraphs if p.startswith("# ") or p.startswith("## 引言") or p.startswith("## 结论")]
    other_paragraphs = [p for p in paragraphs if not (p.startswith("# ") or p.startswith("## 引言") or p.startswith("## 结论"))]
    
    # 计算需要保留的段落数
    current_essential_length = sum(len(p) for p in essential_paragraphs)
    remaining_length = target_length - current_essential_length
    
    # 从其他段落中选择最重要的部分
    selected_paragraphs = []
    current_length = 0
    
    for p in other_paragraphs:
        if current_length + len(p) <= remaining_length:
            selected_paragraphs.append(p)
            current_length += len(p)
    
    # 重新组合文章
    all_paragraphs = []
    title = next((p for p in paragraphs if p.startswith("# ")), "")
    if title:
        all_paragraphs.append(title)
    
    intro = next((p for p in paragraphs if p.startswith("## 引言")), "")
    if intro:
        all_paragraphs.append(intro)
    
    all_paragraphs.extend(selected_paragraphs)
    
    conclusion = next((p for p in paragraphs if p.startswith("## 结论")), "")
    if conclusion:
        all_paragraphs.append(conclusion)
    
    return "\n\n".join(all_paragraphs)

def generate_qa_response(article_content, question, history_messages=None):
    """
    基于文章内容和历史对话生成问答回复
    
    参数:
    article_content (str): 文章内容，如果为空字符串则表示是首页新建会话
    question (str): 用户提问
    history_messages (list): 历史对话消息列表，包含ChatMessage对象
    
    返回:
    str: 生成的回答
    """
    try:
        # 判断是否是首页新建会话（没有文章内容）
        is_homepage_chat = not article_content or article_content.strip() == ''
        
        # 首先尝试调用AI API
        ai_answer = call_ai_qa_response(article_content, question, is_homepage_chat, history_messages)
        
        if ai_answer:
            return ai_answer
        else:
            # 如果AI调用失败，回退到模拟数据
            current_app.logger.warning("AI QA failed, using fallback logic")
            return get_fallback_qa_response(article_content, question, is_homepage_chat)
    
    except Exception as e:
        current_app.logger.error(f"Error generating QA response: {e}")
        return get_fallback_qa_response(article_content, question, is_homepage_chat)

def call_ai_qa_response(article_content, question, is_homepage_chat=False, history_messages=None):
    """
    调用Qwen3 API生成问答回复
    
    参数:
    article_content (str): 文章内容，如果为空则表示是首页新建会话
    question (str): 用户问题
    is_homepage_chat (bool): 是否是首页新建会话，默认为False
    history_messages (list): 历史对话消息列表，包含ChatMessage对象
    
    返回:
    str: AI生成的回答
    """
    try:
        api_url = current_app.config.get('AI_MODEL_API_URL')
        api_key = current_app.config.get('AI_MODEL_API_KEY')
        
        if not api_url or not api_key:
            current_app.logger.error("AI model configuration not found")
            return None
        
        # 根据是否是首页新建会话构建不同的提示词
        if is_homepage_chat or not article_content or article_content.strip() == '':
            # 首页新建会话，直接回答用户问题，不依赖文章内容
            prompt = f"""
请回答用户的问题：

用户问题：{question}

回答要求：
1. 简洁明了，重点突出
2. 内容准确，逻辑清晰
3. 保持客观和专业的语调
4. 如果问题涉及不确定信息，请说明
"""
        else:
            # 基于文章内容回答问题
            prompt = f"""
基于以下文章内容，回答用户的问题：

文章内容：
{article_content[:3000]}...

用户问题：{question}

请根据文章内容准确回答问题。如果文章中没有相关信息，请明确说明。回答要：
1. 准确且基于文章内容
2. 简洁明了，重点突出
3. 如果需要引用文章内容，请适当标注
4. 保持客观和专业的语调
"""
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        # 构建消息列表，包含历史对话上下文
        messages = []
        
        # 添加系统提示（如果有文章内容）
        if not is_homepage_chat and article_content and article_content.strip():
            messages.append({
                'role': 'system',
                'content': f"你是一个AI助手，基于以下文章内容回答用户问题：\n\n{article_content[:2000]}..."
            })
        
        # 添加历史对话上下文
        if history_messages:
            for msg in history_messages[-5:]:  # 只取最近5轮对话
                messages.append({
                    'role': 'user',
                    'content': msg.question
                })
                messages.append({
                    'role': 'assistant', 
                    'content': msg.answer
                })
        
        # 添加当前问题
        messages.append({
            'role': 'user',
            'content': prompt if is_homepage_chat or not article_content else question
        })

        data = {
            'model': 'qwen-plus',
            'messages': messages,
            'temperature': 0.3,
            'max_tokens': 1000
        }
        
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_content = result['choices'][0]['message']['content']
            return ai_content
        else:
            current_app.logger.error(f"AI QA API request failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Error calling AI QA: {e}")
        return None

def get_fallback_qa_response(article_content, question, is_homepage_chat=False):
    """
    回退的问答回复生成（当AI调用失败时使用）
    
    参数:
    article_content (str): 文章内容
    question (str): 用户问题
    is_homepage_chat (bool): 是否是首页新建会话，默认为False
    
    返回:
    str: 回退生成的回答
    """
    try:
        # 如果是首页新建会话，不依赖文章内容直接回答
        if is_homepage_chat or not article_content or article_content.strip() == '':
            # 提取问题中的关键词
            keywords = re.findall(r'\w{2,}', question)
            
            # 根据问题类型生成不同的回答
            if any(kw in question.lower() for kw in ['你好', '您好', 'hello', 'hi']):
                return "您好！我是AI助手，很高兴为您服务。请问有什么我可以帮助您的吗？"
            elif any(kw in question.lower() for kw in ['介绍', '是什么', '功能', '能做什么']):
                return "我是一个AI助手，可以回答您的问题、提供信息和帮助您完成各种任务。您可以向我咨询各种话题，我会尽力提供准确和有用的回答。"
            elif any(kw in question.lower() for kw in ['天气', '气温', '下雨']):
                return "很抱歉，我无法获取实时天气信息。您可以通过天气应用或网站查询最新的天气预报。"
            elif any(kw in question.lower() for kw in ['时间', '几点', '日期', '今天']):
                return "很抱歉，我无法获取当前的时间和日期信息。您可以查看您的设备上显示的时间。"
            else:
                # 通用回答
                return f"关于\"{question}\"，这是一个很好的问题。作为AI助手，我会尽力提供相关信息。请问您想了解这个问题的哪些具体方面呢？"
        else:
            # 基于文章内容回答问题
            # 简单的关键词匹配
            keywords = re.findall(r'\w{2,}', question)
            relevant_paragraphs = []
            
            # 按段落分割文章
            paragraphs = article_content.split('\n\n')
            
            # 查找相关段落
            for paragraph in paragraphs:
                if any(keyword in paragraph for keyword in keywords if len(keyword) > 1):
                    relevant_paragraphs.append(paragraph)
            
            if relevant_paragraphs:
                # 基于相关段落生成回答
                answer = f"根据文章内容，"
                
                # 提取相关段落中的关键句子
                sentences = []
                for paragraph in relevant_paragraphs:
                    paragraph_sentences = re.split(r'[。！？]', paragraph)
                    for sentence in paragraph_sentences:
                        if any(keyword in sentence for keyword in keywords if len(keyword) > 1) and len(sentence) > 10:
                            sentences.append(sentence)
                
                if sentences:
                    answer += "我找到了以下相关信息：\n\n"
                    for i, sentence in enumerate(sentences[:3]):
                        answer += f"{i+1}. {sentence.strip()}。\n"
                    
                    answer += f"\n基于以上信息，{question}的答案是：{sentences[0].strip()}等相关内容提供了线索。"
                else:
                    answer += f"文章中没有直接提到关于{question}的具体信息，但根据上下文可以推断，这可能与文章讨论的主题有间接关联。"
            else:
                answer = f"文章中没有直接涉及到{question}的内容。您可能需要参考其他资料或重新调整问题。"
            
            return answer
    
    except Exception as e:
        current_app.logger.error(f"Error in fallback QA response: {e}")
        if is_homepage_chat:
            return "抱歉，我暂时无法回答这个问题。请尝试提问其他问题。"
        else:
            return "抱歉，我无法回答这个问题。请尝试提问与文章内容更相关的问题。"

def call_ai_generate_article(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures):
    """
    调用Qwen3 API生成文章
    
    参数:
    keywords (list): 关键词列表
    opinions (list): 观点列表
    logic_structure (list): 逻辑结构列表
    selected_logic (list): 用户选择的逻辑结构
    style_preference (str): 写作风格偏好
    word_count (int): 目标字数
    custom_style (str): 自定义写作风格描述
    use_corpus (bool): 是否使用个人语料库
    custom_instructions (str): 自定义生成指令
    logic_structures (list): 两种逻辑结构的树形数据
    
    返回:
    str: 生成的文章内容
    """
    try:
        api_url = current_app.config.get('AI_MODEL_API_URL')
        api_key = current_app.config.get('AI_MODEL_API_KEY')
        
        if not api_url or not api_key:
            current_app.logger.error("AI model configuration not found")
            return None
        
        # 构建生成提示词
        prompt = f"""
请根据以下信息生成一篇高质量的文章：

关键词：{', '.join(keywords) if keywords else '无'}

核心观点：
{chr(10).join([f"- {op.get('content', '')} (可信度: {op.get('confidence', 0)})" for op in opinions]) if opinions else '无'}

逻辑结构：{', '.join(selected_logic) if selected_logic else ', '.join(logic_structure) if logic_structure else '无'}

写作风格：{style_preference}
{f"自定义风格：{custom_style}" if custom_style else ""}

目标字数：{word_count}字
{f"使用个人语料库：是" if use_corpus else ""}
{f"自定义指令：{custom_instructions}" if custom_instructions else ""}

请生成一篇结构清晰、内容丰富的文章，包含：
1. 吸引人的标题
2. 引言部分
3. 主体内容（按照逻辑结构展开）
4. 结论部分

文章要求：
- 语言流畅，逻辑清晰
- 适当使用关键词
- 体现核心观点
- 符合指定的写作风格
- 字数控制在目标范围内
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
            'temperature': 0.7,
            'max_tokens': 3000
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
            return ai_content
        else:
            current_app.logger.error(f"AI API request failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Error calling AI article generation: {e}")
        return None

def get_fallback_article(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures):
    """
    获取回退文章生成（当AI调用失败时使用）
    
    参数:
    同generate_article函数
    
    返回:
    str: 回退生成的文章内容
    """
    try:
        # 如果没有指定逻辑结构，使用所有的逻辑结构
        if not selected_logic or len(selected_logic) == 0:
            selected_logic = logic_structure
        
        # 根据风格调整写作参数
        tone = get_tone_by_style(style_preference, custom_style)
        
        # 生成文章标题
        title = generate_title(keywords, selected_logic[0] if selected_logic else "")
        
        # 生成文章内容
        content = []
        
        # 添加引言
        introduction = generate_introduction(keywords, opinions, tone)
        content.append(introduction)
        
        # 根据选定的逻辑结构生成主体内容
        for logic in selected_logic:
            section = generate_section(logic, keywords, opinions, tone)
            content.append(section)
        
        # 添加结论
        conclusion = generate_conclusion(keywords, opinions, tone)
        content.append(conclusion)
        
        # 如果有自定义指令，添加到文章生成中
        if custom_instructions:
            custom_section = f"## 补充观点\n\n根据您的要求，{custom_instructions}。这一点值得我们特别关注，因为它直接关系到{keywords[0] if keywords else '相关领域'}的未来发展方向。"
            content.append(custom_section)
        
        # 如果使用语料库，添加语料库相关内容
        if use_corpus:
            corpus_section = f"## 相关语料分析\n\n根据个人语料库中的相关资料，{keywords[0] if keywords else '相关领域'}领域有以下几个值得注意的趋势：\n\n1. 近期研究表明，{keywords[1] if len(keywords) > 1 else keywords[0] if keywords else '相关因素'}与{keywords[2] if len(keywords) > 2 else keywords[0] if keywords else '相关因素'}的关联度不断提高\n2. 行业专家普遍认为，未来五年内{keywords[0] if keywords else '相关领域'}将迎来重大变革\n3. 从历史数据来看，{keywords[0] if keywords else '相关领域'}的发展呈现出明显的周期性特征"
            content.append(corpus_section)
        
        # 组合成完整文章
        full_article = f"# {title}\n\n" + "\n\n".join(content)
        
        # 根据用户指定的字数调整文章长度
        if word_count and word_count > 0:
            current_length = len(full_article)
            if current_length < word_count * 0.8:  # 如果文章长度少于目标的80%，进行扩展
                full_article = expand_article(full_article, word_count)
            # 不再强制截断，让AI自由发挥
        
        return full_article
        
    except Exception as e:
        current_app.logger.error(f"Error in fallback article generation: {e}")
        return "文章生成失败，请稍后重试。"

def call_ai_generate_article_stream(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures):
    """
    调用Qwen3 API流式生成文章
    
    参数:
    同generate_article函数
    
    返回:
    generator: 生成器，每次yield一个内容块
    """
    try:
        api_url = current_app.config.get('AI_MODEL_API_URL')
        api_key = current_app.config.get('AI_MODEL_API_KEY')
        
        if not api_url or not api_key:
            current_app.logger.error("AI model configuration not found")
            return None
        
        # 构建生成提示词
        prompt = f"""
请根据以下信息生成一篇高质量的文章：

关键词：{', '.join(keywords) if keywords else '无'}

核心观点：
{chr(10).join([f"- {op.get('content', '')} (可信度: {op.get('confidence', 0)})" for op in opinions]) if opinions else '无'}

逻辑结构：{', '.join(selected_logic) if selected_logic else ', '.join(logic_structure) if logic_structure else '无'}

写作风格：{style_preference}
{f"自定义风格：{custom_style}" if custom_style else ""}

目标字数：{word_count}字
{f"使用个人语料库：是" if use_corpus else ""}
{f"自定义指令：{custom_instructions}" if custom_instructions else ""}

请生成一篇结构清晰、内容丰富的文章，包含：
1. 吸引人的标题
2. 引言部分
3. 主体内容（按照逻辑结构展开）
4. 结论部分

文章要求：
- 语言流畅，逻辑清晰
- 适当使用关键词
- 体现核心观点
- 符合指定的写作风格
- 字数控制在目标范围内
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
            'temperature': 0.7,
            'max_tokens': 3000,
            'stream': True  # 启用流式输出
        }
        
        response = requests.post(
            f"{api_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=60,
            stream=True
        )
        
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str.strip() == '[DONE]':
                            break
                        try:
                            data_obj = json.loads(data_str)
                            if 'choices' in data_obj and len(data_obj['choices']) > 0:
                                delta = data_obj['choices'][0].get('delta', {})
                                content = delta.get('content', '')
                                if content:
                                    yield content
                        except json.JSONDecodeError:
                            continue
        else:
            current_app.logger.error(f"AI API request failed: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        current_app.logger.error(f"Error calling AI stream generation: {e}")
        return None

def get_fallback_article_stream(keywords, opinions, logic_structure, selected_logic, style_preference, word_count, custom_style, use_corpus, custom_instructions, logic_structures):
    """
    回退的流式文章生成（当AI调用失败时使用）
    
    参数:
    同generate_article函数
    
    返回:
    generator: 生成器，每次yield一个内容块
    """
    try:
        # 生成文章标题
        title = generate_title(keywords, selected_logic[0] if selected_logic else "")
        yield f"# {title}\n\n"
        
        # 生成引言
        tone = get_tone_by_style(style_preference, custom_style)
        introduction = generate_introduction(keywords, opinions, tone)
        yield introduction + "\n\n"
        
        # 根据选定的逻辑结构生成主体内容
        for logic in (selected_logic or logic_structure or []):
            section = generate_section(logic, keywords, opinions, tone)
            yield section + "\n\n"
        
        # 添加结论
        conclusion = generate_conclusion(keywords, opinions, tone)
        yield conclusion
        
    except Exception as e:
        current_app.logger.error(f"Error in fallback stream generation: {e}")
        yield "文章生成失败，请稍后重试。"





