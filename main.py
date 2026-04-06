# main.py - Phase 3 最终修复版（带颜色切换 + CSS 修复）
import gradio as gr
from src.ai.pdf_loader import extract_text_from_pdf
from src.ai.llm_service import LLMService
from src.core.memory import ConversationMemory

llm = LLMService()
memory = ConversationMemory(max_turns=6)

def load_pdf(file_path, state_pages, state_idx, state_chat):
    if file_path is None:
        return [], 0, [], "⚠️ 请先上传PDF", ""
    try:
        pages = extract_text_from_pdf(file_path, max_chars=6000)
        memory.clear()
        return pages, 0, [], f"✅ 成功加载 {len(pages)} 页。点击「讲解当前页」开始。", ""
    except Exception as e:
        return [], 0, [], f"❌ 解析失败：{str(e)}", ""

def explain_page(state_pages, state_idx, state_chat):
    if not state_pages or len(state_pages) == 0:
        return state_chat, "⚠️ 请先加载PDF", "", ""
    
    if state_idx < 0 or state_idx >= len(state_pages):
        return state_chat, f"⚠️ 无效页码：{state_idx}", "", ""
    
    page = state_pages[state_idx]
    
    try:
        explanation = llm.explain_page(page["content"], memory.get())
        memory.add("user", f"[系统] 进入第 {page['page_num']} 页")
        memory.add("assistant", explanation)
        
        new_chat = state_chat + [{
            "role": "assistant", 
            "content": f"👩‍ **第 {page['page_num']} 页讲解**\n{explanation}"
        }]
        status = f"📖 当前：第 {page['page_num']}/{len(state_pages)} 页"
        
        # 提取关键点用于黑板（前3-4个段落）
        paragraphs = [p.strip() for p in explanation.split('\n\n') if p.strip()]
        board_content = "\n\n".join([f"{i+1}. {p}" for i, p in enumerate(paragraphs[:4])])
        
        return new_chat, status, explanation, board_content
    except Exception as e:
        return state_chat, f"❌ AI调用失败：{str(e)}", "", ""

def navigate(state_pages, state_idx, delta):
    if not state_pages or len(state_pages) == 0:
        return 0, "📖 请先加载PDF"
    delta = delta if delta is not None else 0
    new_idx = max(0, min(len(state_pages) - 1, state_idx + delta))
    page = state_pages[new_idx]
    return new_idx, f"📖 当前：第 {page['page_num']}/{len(state_pages)} 页"

def ask_question(question, state_pages, state_idx, state_chat):
    if not question.strip():
        return state_chat, ""
    if not state_pages or len(state_pages) == 0 or state_idx >= len(state_pages):
        return state_chat, "⚠️ 请先加载并讲解PDF"
    try:
        memory.add("user", question)
        answer = llm.answer_question(state_pages[state_idx]["content"], question, memory.get())
        memory.add("assistant", answer)
        new_chat = state_chat + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]
        return new_chat, ""
    except Exception as e:
        return state_chat, f"❌ 回答失败：{str(e)}"

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
    current_idx = color_list.index(current_color)
    next_color = color_list[(current_idx + 1) % len(color_list)]
    next_hex, next_name = colors[next_color]
    return next_color, next_name

def update_blackboard_html(content, color):
    """根据颜色更新黑板 HTML"""
    color_map = {
        "white": "#ffffff",
        "yellow": "#ffeb3b",
        "green": "#4caf50",
        "blue": "#2196f3",
        "red": "#ff5722",
    }
    text_color = color_map.get(color, "#ffffff")
    
    display_content = content if content else "<span style='color: rgba(255,255,255,0.5); font-style: italic;'>✨ 等待内容...</span>"
    
    return f"""
    <div style="
        width: 100%; min-height: 350px; 
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); 
        border-radius: 12px; padding: 30px;
        font-family: 'Comic Sans MS', 'Chalkboard', cursive, sans-serif;
        box-shadow: inset 0 0 50px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.3);
        border: 8px solid #5c3a21;
    ">
        <div style="
            text-align: center; 
            color: rgba(255,255,255,0.7); 
            font-size: 14px; 
            margin-bottom: 25px;
            font-weight: bold;
        ">
            📝 虚拟黑板 - 板书内容
        </div>
        <div style="
            white-space: pre-wrap;
            line-height: 1.8;
            font-size: 17px;
            padding: 15px;
            background: rgba(0,0,0,0.15);
            border-radius: 8px;
            min-height: 250px;
            color: {text_color};
            transition: color 0.3s ease;
        ">
{display_content}
        </div>
        <div style="
            position: absolute;
            bottom: 15px;
            right: 20px;
            font-size: 12px;
            color: rgba(255,255,255,0.5);
        ">
            VirtualClassroomAI
        </div>
    </div>
    """

# Gradio 界面 - 移除 css 参数
with gr.Blocks(title="VirtualClassroomAI - 虚拟课堂") as demo:
    gr.Markdown("# 🎓 VirtualClassroomAI Phase 3")
    gr.Markdown("支持多页导航 + 对话记忆 + **黑板板书动画**")

    pdf_pages = gr.State([])
    current_idx = gr.State(0)
    chat_hist = gr.State([])
    chalk_color_state = gr.State("white")  # 粉笔颜色状态

    with gr.Row():
        with gr.Column(scale=1):
            pdf_input = gr.File(label="📄 上传PDF", file_types=[".pdf"])
            load_btn = gr.Button("📥 加载文档", variant="primary")
            
            with gr.Row():
                prev_btn = gr.Button("⬅️ 上一页")
                next_btn = gr.Button("➡️ 下一页")
            explain_btn = gr.Button("🎙️ 讲解当前页", variant="primary")
            
            page_status = gr.Textbox(label="📊 页面状态", interactive=False)
            status_msg = gr.Textbox(label="💡 提示", interactive=False)

        with gr.Column(scale=2):
            chatbot = gr.Chatbot(label="👩‍ 课堂对话", height=380)
            with gr.Row():
                question_input = gr.Textbox(label="💬 向露卡提问", placeholder="例如：这个公式和上一页有什么联系？", scale=4)
                ask_btn = gr.Button("提问", scale=1)

    # 黑板面板 + 颜色控制
    gr.Markdown("### 🖍️ 虚拟黑板")
    
    with gr.Row():
        color_btn = gr.Button("🎨 切换粉笔颜色", variant="secondary")
    color_display = gr.Textbox(label="当前颜色", value="⚪ 白色", interactive=False)
    
    blackboard_html = gr.HTML(
        value="""<div style="width: 100%; min-height: 350px; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); border-radius: 12px; padding: 30px; font-family: 'Comic Sans MS', 'Chalkboard', cursive, sans-serif; box-shadow: inset 0 0 50px rgba(0,0,0,0.5); border: 8px solid #5c3a21;"><div style="text-align: center; color: rgba(255,255,255,0.7); font-size: 14px; margin-bottom: 25px; font-weight: bold;">📝 虚拟黑板 - 板书内容</div><div id='chalk-content' style="white-space: pre-wrap; line-height: 1.8; font-size: 17px; padding: 15px; background: rgba(0,0,0,0.15); border-radius: 8px; min-height: 250px; color: #ffffff;"><span style="color: rgba(255,255,255,0.5); font-style: italic;">等待讲解内容...</span></div></div>"""
    )
    
    board_textbox = gr.Textbox(visible=False, label="黑板内容")

    # 事件绑定
    load_btn.click(
        load_pdf, 
        inputs=[pdf_input, pdf_pages, current_idx, chat_hist], 
        outputs=[pdf_pages, current_idx, chat_hist, status_msg, board_textbox]
    )
    
    explain_btn.click(
        explain_page, 
        inputs=[pdf_pages, current_idx, chat_hist], 
        outputs=[chatbot, page_status, gr.Textbox(visible=False), board_textbox]
    ).then(
        update_blackboard_html,
        inputs=[board_textbox, chalk_color_state],
        outputs=[blackboard_html]
    )
    
    # 颜色切换按钮
    color_btn.click(
        change_chalk_color,
        inputs=[chalk_color_state],
        outputs=[chalk_color_state, color_display]
    ).then(
        update_blackboard_html,
        inputs=[board_textbox, chalk_color_state],
        outputs=[blackboard_html]
    )
    
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
    
    ask_btn.click(
        ask_question, 
        inputs=[question_input, pdf_pages, current_idx, chat_hist], 
        outputs=[chatbot, question_input]
    )

if __name__ == "__main__":
    # ✅ CSS 参数已移至 launch() 方法
    demo.launch(
        share=False, 
        server_name="127.0.0.1", 
        server_port=7860,
        css="footer {display:none !important}"
    )