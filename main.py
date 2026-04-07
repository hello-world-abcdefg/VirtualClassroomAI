# main.py - VirtualClassroomAI Phase 4
# 沉浸式虚拟课堂｜多页导航 + 对话记忆 + 黑板板书 + 奖励系统 + 虚拟教室
# 兼容 Gradio 6.0+

import gradio as gr
from src.ai.pdf_loader import extract_text_from_pdf
from src.ai.llm_service import LLMService
from src.core.memory import ConversationMemory

# 初始化全局服务
llm = LLMService()
memory = ConversationMemory(max_turns=6)


# ============================================================================
# 🏆 奖励系统（纯字典操作，兼容 Gradio 状态管理）
# ============================================================================
def init_reward():
    """初始化奖励状态"""
    return {"flowers": 0, "points": 0, "achievements": []}


def add_flower(state, reason=""):
    """添加小红花"""
    state = state.copy()  # 避免原地修改
    state["flowers"] += 1
    state["points"] += 10
    return state, f"🌸 +1 小红花！({reason})"


def check_achievement(state, action: str):
    """检查并解锁成就"""
    state = state.copy()
    new_achs = []
    achs = state.get("achievements", [])
    
    if action == "first_question" and "首次提问" not in achs:
        achs = achs + ["首次提问"]
        new_achs.append("🎯 勇敢提问者")
    if state.get("flowers", 0) >= 5 and "收集达人" not in achs:
        achs = achs + ["收集达人"]
        new_achs.append("🌟 收集达人（5 朵小红花）")
    if state.get("points", 0) >= 50 and "学习之星" not in achs:
        achs = achs + ["学习之星"]
        new_achs.append("⭐ 学习之星（50 积分）")
    
    state["achievements"] = achs
    return state, new_achs


def format_rewards(state):
    """格式化奖励显示为 HTML"""
    # 安全处理：支持字典或对象
    if hasattr(state, '__dict__'):
        d = state.__dict__
    else:
        d = state or {}
    
    flowers = d.get("flowers", 0)
    points = d.get("points", 0)
    achs_list = d.get("achievements", [])
    achs = " • ".join(achs_list) if achs_list else "🌱 继续努力~"
    
    return f"""
    <div style="background: linear-gradient(135deg, #fff9e6 0%, #ffecb3 100%); 
                border-radius: 10px; padding: 15px; border: 2px solid #ffd54f;">
        <div style="font-weight: bold; color: #e65100; margin-bottom: 8px;">🏆 学习成就</div>
        <div style="font-size: 14px; color: #5d4037;">
            🌸 小红花: <b>{flowers}</b> | ⭐ 积分: <b>{points}</b>
        </div>
        <div style="margin-top: 8px; font-size: 13px;">🎖️ {achs}</div>
    </div>
    """


# ============================================================================
# 📚 核心逻辑函数
# ============================================================================
def load_pdf(file_path, state_pages, state_idx, state_chat, state_rewards):
    """加载并解析 PDF"""
    if file_path is None:
        return [], 0, [], "⚠️ 请先上传PDF", state_rewards, ""
    
    try:
        # 解析 PDF（注意：确认 pdf_loader.py 支持 max_chars 参数）
        pages = extract_text_from_pdf(file_path, max_chars=6000)
        
        if not pages:
            return [], 0, [], "⚠️ PDF 内容为空或无法解析", state_rewards, ""
        
        # 重置状态
        memory.clear()
        
        return (
            pages,                          # → pdf_pages
            0,                              # → current_idx
            [],                             # → chat_hist
            f"✅ 成功加载 {len(pages)} 页",  # → page_status
            init_reward(),                  # → reward_state
            ""                              # → notification_area (字符串！)
        )
        
    except FileNotFoundError:
        return [], 0, [], "❌ 文件不存在", state_rewards, ""
    except Exception as e:
        return [], 0, [], f"❌ 解析失败：{type(e).__name__}", state_rewards, ""


def explain_page(state_pages, state_idx, state_chat, state_rewards):
    """讲解当前页内容"""
    if not state_pages or len(state_pages) == 0:
        return state_chat, "⚠️ 请先加载PDF", "", state_rewards, "", ""
    
    if state_idx < 0 or state_idx >= len(state_pages):
        return state_chat, f"⚠️ 无效页码：{state_idx}", "", state_rewards, "", ""
    
    page = state_pages[state_idx]
    
    try:
        # 调用 AI 生成讲解
        explanation = llm.explain_page(page["content"], memory.get())
        memory.add("user", f"[系统] 进入第 {page['page_num']} 页")
        memory.add("assistant", explanation)
        
        # 更新对话历史
        new_chat = state_chat + [{
            "role": "assistant", 
            "content": f"👩‍🏫 **第 {page['page_num']} 页讲解**\n{explanation}"
        }]
        
        status = f"📖 当前：第 {page['page_num']}/{len(state_pages)} 页"
        
        # 提取关键点用于黑板（前 3-4 个段落）
        paragraphs = [p.strip() for p in explanation.split('\n\n') if p.strip()]
        board_content = "\n\n".join([f"{i+1}. {p}" for i, p in enumerate(paragraphs[:4])])
        
        # 奖励系统更新
        state_rewards, flower_msg = add_flower(state_rewards, f"完成第{page['page_num']}页学习")
        state_rewards, new_achs = check_achievement(state_rewards, "page_completed")
        
        # ✅ 关键修复：通知必须是字符串，不是列表
        notifications = "<br>".join([flower_msg] + new_achs) if new_achs else flower_msg
        
        return new_chat, status, explanation, state_rewards, board_content, notifications
        
    except Exception as e:
        return state_chat, f"❌ AI调用失败：{str(e)}", "", state_rewards, "", f"❌ {str(e)}"


def navigate(state_pages, state_idx, delta):
    """翻页导航"""
    if not state_pages or len(state_pages) == 0:
        return 0, "📖 请先加载PDF"
    
    # 安全处理 delta
    delta = delta if delta is not None else 0
    new_idx = max(0, min(len(state_pages) - 1, state_idx + delta))
    
    if state_pages and new_idx < len(state_pages):
        page = state_pages[new_idx]
        status = f"📖 当前：第 {page['page_num']}/{len(state_pages)} 页"
    else:
        status = "📖 请选择页面"
    
    return new_idx, status


def ask_question(question, state_pages, state_idx, state_chat, state_rewards):
    """回答学生提问"""
    if not question.strip():
        return state_chat, "", state_rewards, ""
    
    if not state_pages or len(state_pages) == 0 or state_idx >= len(state_pages):
        return state_chat, "⚠️ 请先加载并讲解PDF", state_rewards, ""
    
    try:
        memory.add("user", question)
        answer = llm.answer_question(state_pages[state_idx]["content"], question, memory.get())
        memory.add("assistant", answer)
        
        new_chat = state_chat + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]
        
        # 奖励：提问
        state_rewards, flower_msg = add_flower(state_rewards, "积极提问")
        state_rewards, new_achs = check_achievement(state_rewards, "first_question")
        
        # ✅ 关键修复：通知必须是字符串
        notifications = "<br>".join([flower_msg] + new_achs) if new_achs else flower_msg
        
        return new_chat, "", state_rewards, notifications
        
    except Exception as e:
        return state_chat, f"❌ 回答失败：{str(e)}", state_rewards, f"❌ {str(e)}"


def change_chalk_color(current_color):
    """切换粉笔颜色"""
    colors = {
        "white": ("#ffffff", "⚪ 白色"),
        "yellow": ("#ffeb3b", "🟡 黄色"),
        "green": ("#4caf50", "🟢 绿色"),
        "blue": ("#2196f3", "🔵 蓝色"),
        "red": ("#ff5722", "🔴 红色"),
    }
    color_list = list(colors.keys())
    current_idx = color_list.index(current_color) if current_color in color_list else 0
    next_color = color_list[(current_idx + 1) % len(color_list)]
    return next_color, colors[next_color][1]


def update_blackboard_html(content, color):
    """根据内容+颜色生成黑板 HTML"""
    color_map = {
        "white": "#ffffff", "yellow": "#ffeb3b", "green": "#4caf50",
        "blue": "#2196f3", "red": "#ff5722",
    }
    text_color = color_map.get(color, "#ffffff")
    
    display_content = content if content else "<span style='color: rgba(255,255,255,0.5); font-style: italic;'>✨ 等待内容...</span>"
    
    return f"""
    <div style="
        width: 100%; min-height: 320px; 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        border-radius: 12px; padding: 25px;
        font-family: 'Comic Sans MS', 'Chalkboard', cursive, sans-serif;
        box-shadow: inset 0 0 50px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.3);
        border: 8px solid #5c3a21; position: relative;
    ">
        <div style="
            text-align: center; color: rgba(255,255,255,0.7); 
            font-size: 13px; margin-bottom: 20px; font-weight: bold;
        ">📝 虚拟黑板</div>
        <div style="
            white-space: pre-wrap; line-height: 1.7; font-size: 16px;
            padding: 12px; background: rgba(0,0,0,0.15); border-radius: 6px;
            min-height: 220px; color: {text_color};
        ">{display_content}</div>
    </div>
    """


# ============================================================================
# 🏫 沉浸式课堂组件（虚拟教师 + 同学 + 视角切换）
# ============================================================================
CLASSROOM_HTML = """
<style>
.classroom-container {
    display: flex; gap: 20px; padding: 15px; 
    background: linear-gradient(to bottom, #e3f2fd, #bbdefb);
    border-radius: 16px; border: 3px solid #90caf9;
}
.teacher-area {
    flex: 1; display: flex; flex-direction: column; align-items: center;
}
.teacher-avatar {
    width: 100px; height: 140px; 
    background: linear-gradient(135deg, #ffecb3, #ffe082);
    border-radius: 50% 50% 45% 45%; border: 4px solid #ffa000;
    display: flex; align-items: center; justify-content: center;
    font-size: 50px; margin-bottom: 8px;
    animation: breathe 3s ease-in-out infinite;
}
@keyframes breathe {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}
.classmates-area {
    flex: 1; display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px;
}
.classmate {
    width: 50px; height: 70px; 
    background: linear-gradient(135deg, #c8e6c9, #a5d6a7);
    border-radius: 40%; border: 3px solid #66bb6a;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; cursor: pointer; transition: 0.2s;
}
.classmate:hover { transform: scale(1.15); }
.view-toggle {
    text-align: center; margin: 15px 0;
}
.view-btn {
    padding: 8px 20px; border: none; border-radius: 20px;
    background: #1976d2; color: white; cursor: pointer;
    font-weight: bold; margin: 0 5px; transition: 0.2s;
}
.view-btn.active { background: #0d47a1; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
.desk-view {
    background: linear-gradient(to bottom, #fff9c4, #ffecb3);
    border-radius: 12px; padding: 20px; border: 3px dashed #ffb74d;
    font-style: italic; color: #5d4037; text-align: center; display: none;
}
</style>

<div class="classroom-container">
    <div class="teacher-area">
        <div class="teacher-avatar">👩‍🏫</div>
        <div style="font-weight: bold; color: #5d4037;">露卡老师</div>
    </div>
    <div class="classmates-area">
        <div class="classmate" onclick="alert('小明：这个知识点我懂了！')">👦</div>
        <div class="classmate" onclick="alert('小红：老师能再讲一遍吗？')">👧</div>
        <div class="classmate" onclick="alert('小刚：记笔记中✍️')">👦</div>
        <div class="classmate" onclick="alert('小美：举手🙋')">👧</div>
    </div>
</div>

<div class="view-toggle">
    <button class="view-btn active" onclick="switchView('front')">🎥 教室视角</button>
    <button class="view-btn" onclick="switchView('desk')">🪑 课桌视角</button>
</div>

<div id="deskViewPanel" class="desk-view">
    🪑 你坐在课桌前，黑板在正前方，露卡老师站在黑板旁讲解。<br>
    <span style="font-size: 12px;">（第一人称视角模拟 - 后续 Unity 版将实现真实 3D 视角）</span>
</div>

<script>
function switchView(view) {
    const buttons = document.querySelectorAll('.view-btn');
    const deskPanel = document.getElementById('deskViewPanel');
    
    buttons.forEach(btn => btn.classList.remove('active'));
    
    if (view === 'desk') {
        buttons[1].classList.add('active');
        deskPanel.style.display = 'block';
    } else {
        buttons[0].classList.add('active');
        deskPanel.style.display = 'none';
    }
}
console.log('[Classroom] UI loaded');
</script>
"""


# ============================================================================
# 🎨 Gradio 界面搭建
# ============================================================================
with gr.Blocks(title="VirtualClassroomAI - 虚拟课堂") as demo:
    gr.Markdown("# 🎓 VirtualClassroomAI Phase 4")
    gr.Markdown("沉浸式虚拟课堂｜多页导航 + 对话记忆 + 黑板板书 + **奖励系统**")

    # 状态管理
    pdf_pages = gr.State([])
    current_idx = gr.State(0)
    chat_hist = gr.State([])
    reward_state = gr.State(init_reward())
    chalk_color_state = gr.State("white")

    # 沉浸式课堂组件
    gr.HTML(CLASSROOM_HTML)
    
    with gr.Row():
        with gr.Column(scale=1):
            pdf_input = gr.File(label="📄 上传PDF", file_types=[".pdf"])
            load_btn = gr.Button("📥 加载文档", variant="primary")
            
            with gr.Row():
                prev_btn = gr.Button("⬅️ 上一页")
                next_btn = gr.Button("➡️ 下一页")
            explain_btn = gr.Button("🎙️ 讲解当前页", variant="primary")
            
            page_status = gr.Textbox(label="📊 页面状态", interactive=False)
            
            # 奖励面板
            gr.Markdown("### 🏆 学习成就")
            reward_display = gr.HTML(value=format_rewards(init_reward()))
            notification_area = gr.Markdown(value="")

        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="👩‍🏫 课堂对话", height=350)
            with gr.Row():
                question_input = gr.Textbox(
                    label="💬 向露卡提问", 
                    placeholder="例如：这个公式和上一页有什么联系？", 
                    scale=4
                )
                ask_btn = gr.Button("提问", scale=1)

    # 黑板 + 颜色控制
    gr.Markdown("### 🖍️ 虚拟黑板")
    with gr.Row():
        color_btn = gr.Button("🎨 切换粉笔色", variant="secondary")
    color_display = gr.Textbox(label="当前颜色", value="⚪ 白色", interactive=False)
    blackboard_html = gr.HTML(value=update_blackboard_html("", "white"))
    board_textbox = gr.Textbox(visible=False)

    # ========================================================================
    # 🔗 事件绑定（关键：确保输入输出数量/顺序完全匹配）
    # ========================================================================
    
    # 加载 PDF
    load_btn.click(
        load_pdf, 
        inputs=[pdf_input, pdf_pages, current_idx, chat_hist, reward_state], 
        outputs=[pdf_pages, current_idx, chat_hist, page_status, reward_state, notification_area]
    ).then(
        lambda r: format_rewards(r), 
        inputs=[reward_state], 
        outputs=[reward_display]
    )
    
    # 讲解当前页
    explain_btn.click(
        explain_page, 
        inputs=[pdf_pages, current_idx, chat_hist, reward_state], 
        outputs=[chatbot, page_status, gr.Textbox(visible=False), reward_state, board_textbox, notification_area]
    ).then(
        lambda r: format_rewards(r), 
        inputs=[reward_state], 
        outputs=[reward_display]
    ).then(
        update_blackboard_html,
        inputs=[board_textbox, chalk_color_state],
        outputs=[blackboard_html]
    )
    
    # 切换粉笔颜色
    color_btn.click(
        change_chalk_color,
        inputs=[chalk_color_state],
        outputs=[chalk_color_state, color_display]
    ).then(
        update_blackboard_html,
        inputs=[board_textbox, chalk_color_state],
        outputs=[blackboard_html]
    )
    
    # 翻页导航（使用 lambda 确保参数正确传递）
    prev_btn.click(
        lambda pages, idx: navigate(pages, idx, -1),
        inputs=[pdf_pages, current_idx], 
        outputs=[current_idx, page_status]
    )
    
    next_btn.click(
        lambda pages, idx: navigate(pages, idx, 1),
        inputs=[pdf_pages, current_idx], 
        outputs=[current_idx, page_status]
    )
    
    # 提问
    ask_btn.click(
        ask_question, 
        inputs=[question_input, pdf_pages, current_idx, chat_hist, reward_state], 
        outputs=[chatbot, question_input, reward_state, notification_area]
    ).then(
        lambda r: format_rewards(r), 
        inputs=[reward_state], 
        outputs=[reward_display]
    )

# ============================================================================
# 🚀 启动应用
# ============================================================================
if __name__ == "__main__":
    # ✅ Gradio 6.0: css 参数必须放在 launch() 中，而非 Blocks()
    demo.launch(
        share=False, 
        server_name="127.0.0.1", 
        server_port=7860,
        css="footer {display:none !important}"
    )