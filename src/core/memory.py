# src/core/memory.py
class ConversationMemory:
    """轻量级对话记忆管理器（避免上下文窗口溢出）"""
    def __init__(self, max_turns: int = 8):
        self.history = []  # 格式: [{"role": "user"/"assistant", "content": "..."}]
        self.max_turns = max_turns

    def add(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        # 保留最近 N 轮对话，防止 token 爆炸
        if len(self.history) > self.max_turns * 2:
            self.history = self.history[-self.max_turns * 2:]

    def get(self) -> list:
        return self.history

    def clear(self):
        self.history = []