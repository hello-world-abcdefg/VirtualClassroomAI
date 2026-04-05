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
        self.temperature = 0.3

    def _call(self, messages: list) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=1024
        )
        return response.choices[0].message.content.strip()

    def explain_page(self, text: str, history: list = None) -> str:
        """讲解当前页内容（携带历史对话）"""
        sys_prompt = """你是虚拟教师“露卡”。请将学术内容转化为通俗易懂的课堂讲解。
        要求：提炼3-5个核心知识点，指出易混淆点，结尾提1个思考题。保持口语化但严谨。"""
        
        messages = [{"role": "system", "content": sys_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": f"请讲解以下新内容：\n{text}"})
        return self._call(messages)

    def answer_question(self, context: str, question: str, history: list = None) -> str:
        """基于上下文+历史对话回答问题"""
        sys_prompt = """你是虚拟教师“露卡”。请严格基于提供的上下文和之前的课堂对话回答问题。
        如果上下文中没有相关信息，请诚实说明“当前讲义未涵盖此内容”，并鼓励学生查阅资料。保持语气鼓励、耐心。"""
        
        messages = [{"role": "system", "content": sys_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": f"📖 当前页上下文：\n{context}\n\n💬 学生提问：{question}"})
        return self._call(messages)