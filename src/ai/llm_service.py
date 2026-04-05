# src/ai/llm_service.py
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class LLMService:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        )
        self.model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()

    def explain_content(self, text: str) -> str:
        """将原始文本转化为虚拟教师的讲解词"""
        sys_prompt = """你是一位亲切、专业的虚拟教师“露卡”。你的任务是将学术/技术内容转化为通俗易懂的课堂讲解。
        要求：
        1. 用口语化但严谨的语言
        2. 提炼核心知识点（3-5个）
        3. 指出可能的难点或易混淆点
        4. 结尾提出1个思考题引导学生互动
        保持输出结构清晰，适合朗读或课堂展示。"""
        return self._call_llm(sys_prompt, f"请讲解以下内容：\n{text}")

    def answer_question(self, context: str, question: str) -> str:
        """基于给定上下文回答学生提问"""
        sys_prompt = """你是虚拟教师“露卡”。请严格基于提供的上下文内容回答问题。
        如果上下文中没有相关信息，请诚实说明“当前讲义未涵盖此内容”，并鼓励学生查阅资料或提出更具体的问题。
        保持语气鼓励、耐心。"""
        return self._call_llm(sys_prompt, f"上下文：\n{context}\n\n学生提问：{question}")