# main.py
import gradio as gr
from src.ai.pdf_loader import extract_text_from_pdf
from src.ai.llm_service import LLMService
from src.core.memory import ConversationMemory

llm = LLMService()
memory = ConversationMemory(max_turns=6)

# --- 核心逻辑函数 ---
def load_pdf(file_path, state_pages, state_idx, state_chat):
    if file_path is None:
        return [], 0, [], "⚠️ 请先上传PDF"
    try:
        pages = extract_text_from_pdf(file_path, max_chars=6000)
        memory.clear()
        return pages, 0, [], f"✅ 成功加载 {len(pages)} 页。点击「讲解当前页」开始。"
    except Exception as e:
        return [], 0, [], f"❌ 解析失败：{str(e)}"

def explain_page(state_pages, state_idx, state_chat):
    if not state_pages or state_idx >= len(state_pages):
        return state_chat, "⚠️ 无内容可讲解"
    
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
        return new_chat, status
    except Exception as e:
        return state_chat, f"❌ AI调用失败：{str(e)}"

def navigate(state_pages, state_idx, delta):
    if not state_pages:
        return 0, "📖 请先加载PDF"
    
    new_idx = max(0, min(len(state_pages) - 1, state_idx + delta))
    page = state_pages[new_idx]
    status = f"📖 当前：第 {page['page_num']}/{len(state_pages)} 页"
    return new_idx, status

def ask_question(question, state_pages, state_idx, state_chat):
    if not question.strip():
        return state_chat, ""
    if not state_pages or state_idx >= len(state_pages):
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

# --- Gradio 界面搭建 ---
with gr.Blocks(title="VirtualClassroomAI - 虚拟课堂") as demo:
    gr.Markdown("# 🎓 VirtualClassroomAI Phase 2")
    gr.Markdown("支持多页导航 + 对话记忆，打造连贯的AI课堂体验")

    pdf_pages = gr.State([])
    current_idx = gr.State(0)
    chat_hist = gr.State([])

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
            chatbot = gr.Chatbot(label="👩‍ 课堂对话", height=500)
            with gr.Row():
                question_input = gr.Textbox(label="💬 向露卡提问", placeholder="例如：这个公式和上一页有什么联系？", scale=4)
                ask_btn = gr.Button("提问", scale=1)

    # 事件绑定
    load_btn.click(load_pdf, inputs=[pdf_input, pdf_pages, current_idx, chat_hist], 
                   outputs=[pdf_pages, current_idx, chat_hist, status_msg])
    explain_btn.click(explain_page, inputs=[pdf_pages, current_idx, chat_hist], 
                      outputs=[chatbot, page_status])
    prev_btn.click(lambda pages, idx: navigate(pages, idx, -1), inputs=[pdf_pages, current_idx], 
                   outputs=[current_idx, page_status])
    next_btn.click(lambda pages, idx: navigate(pages, idx, 1), inputs=[pdf_pages, current_idx], 
                   outputs=[current_idx, page_status])
    ask_btn.click(ask_question, inputs=[question_input, pdf_pages, current_idx, chat_hist], 
                  outputs=[chatbot, question_input])

if __name__ == "__main__":
    demo.launch(share=False, server_name="127.0.0.1", server_port=7860, 
                css="footer {display:none !important}")