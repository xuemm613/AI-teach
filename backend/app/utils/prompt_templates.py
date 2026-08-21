"""提示词模板集合。"""
from typing import List, Optional


def build_history_text(history: Optional[List[dict]]) -> str:
    if not history:
        return "（无）"
    lines = []
    for item in history:
        role = "用户" if item.get("role") == "user" else "助手"
        lines.append(f"{role}: {item.get('content', '')}")
    return "\n".join(lines)


RAG_PROMPT = """你是一个严谨的教育智能问答助手。请仅根据下面的【参考资料】回答用户问题。

规则：
1. 若参考资料足以回答，请给出准确、条理清晰、适合学生理解的答案。
2. 在引用资料内容的相关句子后标注来源，格式：[来源：文件名-第X页]。
3. 若参考资料不足以回答，必须明确回答“知识库中暂无相关信息”，不要编造内容。
4. 使用中文回答。

【参考资料】
{context}

【对话历史】
{history}

【用户问题】
{question}
"""

LESSON_GENERATION_PROMPT = """你是经验丰富的优秀教师，请为以下课程生成一份结构完整、可直接使用的教案。
要求：必须输出【严格 JSON 对象】（不要输出任何其他文字、注释或 markdown 代码块标记），
JSON 结构如下：
{{
  "teaching_objectives": ["教学目标1", "教学目标2", ...],
  "introduction": "课堂导入（情境/问题导入，200字以内）",
  "outline": ["讲授要点1", "讲授要点2", ...],
  "interactive_questions": [{{"question": "互动问题", "answer": "参考答案", "type": "提问/小组讨论/随堂练习"}}],
  "board_design": "板书设计（用 | 或换行表示分区）",
  "layered_exercises": {{
    "basic": ["基础题1", "基础题2"],
    "medium": ["提高题1", "提高题2"],
    "advanced": ["拓展题1", "拓展题2"]
  }}
}}

【年级】{grade}
【学科】{subject}
【章节】{chapter}
【教学目标（可选）】{objectives}

【知识库检索到的参考资料】（用于确保内容与教材一致，可选择性引用）
{context}
"""

ERROR_ANALYSIS_PROMPT = """你是资深学科教师，请对学生错题进行诊断分析。
题目：{question}
学生答案：{user_answer}
正确答案：{correct_answer}

请输出【严格 JSON 对象】：
{{
  "knowledge_point": "涉及的知识点",
  "error_type": "错误类型（概念不清/审题失误/计算错误/方法不当/其他）",
  "analysis": "错因分析（200字以内，结合学生答案与正确答案对比）",
  "suggestion": "针对性学习建议（100字以内）"
}}
"""

EXERCISE_GENERATION_PROMPT = """你是出题专家，请围绕知识点生成一道练习题。
要求：输出【严格 JSON 对象】：
{{
  "content": "题目内容",
  "options": [{{"key": "A", "text": "选项A"}}, {{"key": "B", "text": "选项B"}}, {{"key": "C", "text": "选项C"}}, {{"key": "D", "text": "选项D"}}],
  "answer": "正确答案（如 A，问答题则填参考答案文本）",
  "analysis": "答案解析",
  "knowledge_point": "知识点",
  "difficulty": "难度（easy/medium/hard）"
}}
选择题请给出 4 个选项；若为问答题，options 为空数组。

重要规则：如果【知识点】与学习、学科知识无关（如娱乐、闲聊、新闻、生活琐事等），请直接输出以下 JSON，不要生成题目：
{{"refused": true, "message": "该内容与学习/学科无关，无法生成练习题"}}
只有知识点与学习相关时才正常出题，且正常出题时不要包含 refused 字段。

【知识点】{knowledge_point}
【难度】{difficulty}
"""


SIMILAR_EXERCISE_PROMPT = """你是出题专家。请依据给出的"原题"，生成一道【高度相似】的变式练习题：
要求保持与原题一致的【知识点】、【难度】、【题型结构】（选项形式/填空形式保持一致），
仅更换具体数据、场景或表述，避免与原题重复雷同。
输出【严格 JSON 对象】：
{{
  "content": "变式题目内容",
  "options": [{{"key": "A", "text": "选项A"}}, {{"key": "B", "text": "选项B"}}, {{"key": "C", "text": "选项C"}}, {{"key": "D", "text": "选项D"}}],
  "answer": "正确答案（如 A）",
  "analysis": "答案解析",
  "knowledge_point": "与原题一致或紧紧归属于原题知识点的知识点",
  "difficulty": "与原题一致（easy/medium/hard）",
  "quality": "置信度（high/medium/low）"
}}
选择题给 4 个选项；若原题为填空题/问答题，options 为空数组，answer 填参考答案文本。

【原题】
{original}
"""

SQL_AGENT_PROMPT = """你是教学数据查询助手。根据用户自然语言问题，生成一条【只读 SELECT】SQL 查询语句。
数据库表结构如下：
- users(id, username, full_name, role, is_active)
- students(id, user_id, student_no, grade)
- classes(id, name, teacher_id, grade, subject)
- class_students(class_id, student_id)
- courses(id, name, grade, subject, chapter_tree)
- exercises(id, course_id, type, content, difficulty, knowledge_points)
- learning_records(id, student_id, exercise_id, user_answer, is_correct, duration_seconds, created_at)

约束：
1. 只允许 SELECT（或 WITH ... SELECT）单条语句，禁止 INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE。
2. 聚合统计可使用 COUNT/AVG/SUM/GROUP BY。
3. 直接输出 SQL 本身，不要解释、不要 markdown 代码块。

用户问题：{question}
"""

TUTOR_AGENT_SYSTEM_PROMPT = """你是个性化学习辅导智能体，帮助学生诊断薄弱点并制定学习路径。
你可以调用以下工具（每次只调用一个）：
- search_knowledge: 检索知识库，参数 {"query": "检索关键词"}
- generate_exercise: 生成练习题，参数 {"knowledge_point": "知识点", "difficulty": "easy|medium|hard"}
- analyze_error: 错因分析，参数 {"question": "题目", "user_answer": "学生答案", "correct_answer": "正确答案"}
- query_sql: 查询教学统计数据（只读 SQL），参数 {"natural_language": "自然语言问题，如：班级平均正确率是多少"}
- plan_path: 制定学习路径，参数 {"weak_points": "薄弱知识点描述", "student_id": 学生ID}

工作流程：
1. 首先理解学生问题，进行任务分解；
2. 每一步必须输出严格 JSON（不要输出其他文字）：{"thought": "思考", "tool": "工具名", "args": {参数}}
3. 根据工具返回结果决定下一步，最多 {max_steps} 步；
4. 完成所有工具调用后，输出最终结果：{"final": true, "answer": {最终方案}}。

最终方案 answer 必须为 JSON 对象，结构：
{{
  "weakness_diagnosis": "薄弱点诊断",
  "learning_path": [{{"stage": "阶段1", "content": "学习内容", "exercises": ["建议练习"]}}],
  "recommended_exercises": ["推荐练习题或知识点"],
  "suggestions": ["学习建议1", "学习建议2"]
}}
"""

AGENT_FINAL_PROMPT = """基于前面所有工具调用结果，为学生生成最终个性化辅导方案。
请输出【严格 JSON 对象】（不要输出其他文字）：
{{
  "weakness_diagnosis": "薄弱点诊断",
  "learning_path": [{{"stage": "阶段1", "content": "学习内容", "exercises": ["建议练习"]}}],
  "recommended_exercises": ["推荐练习题或知识点"],
  "suggestions": ["学习建议1", "学习建议2"]
}}

学生问题：{problems}
工具调用记录：
{steps}
"""

PLAN_PATH_PROMPT = """你是学习规划专家，请为以下薄弱知识点制定分阶段学习路径。
输出【严格 JSON 对象】：
{{
  "learning_path": [
    {{"stage": "阶段1-基础巩固", "content": "具体学习内容与方法", "exercises": ["练习1", "练习2"]}},
    {{"stage": "阶段2-能力提升", "content": "具体学习内容与方法", "exercises": ["练习1", "练习2"]}},
    {{"stage": "阶段3-综合拓展", "content": "具体学习内容与方法", "exercises": ["练习1", "练习2"]}}
  ],
  "suggestions": ["建议1", "建议2", "建议3"]
}}
【薄弱知识点】{weak_points}
【学生历史表现】{history}
"""

STUDENT_ANALYSIS_PROMPT = """你是个性化学习辅导专家。请仅根据以下【学生自身学习数据】分析学生的薄弱点并生成个性化辅导方案。
要求：输出【严格 JSON 对象】（不要输出任何其他文字、注释或 markdown 代码块标记）：
{{
  "weakness_diagnosis": "薄弱点诊断（结合错题与知识点）",
  "learning_path": [{{"stage": "阶段1", "content": "学习内容", "exercises": ["建议练习"]}}],
  "recommended_exercises": ["推荐练习题或知识点"],
  "suggestions": ["学习建议1", "学习建议2"]
}}

【学生信息】姓名：{student_name}　学号：{student_no}　年级：{grade}
【学习记录】共作答 {total} 题，答对 {correct} 题，正确率约 {accuracy}。
【错题数】{wrong_count}
【薄弱知识点】{weak_kps}
【最近错题明细】
{wrong_detail}
"""
