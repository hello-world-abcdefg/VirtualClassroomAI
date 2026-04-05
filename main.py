# main.py
import gradio as gr
from src.ai.pdf_loader import extract_text_from_pdf
from src.ai.llm_service import LLMService

llm = LLMService()
current_context = ""  # MVP 简化：仅缓存当前页上下文

def process_pdf(file_path):
    global current_context
    if file_path is None:
        return "⚠️ 请先上传PDF文件", ""

    try:
        pages = extract_text_from_pdf(file_path)
        if not pages:
            return "❌ PDF解析失败或内容为空", ""

        # MVP：先处理第1页
        page1 = pages[0]
        current_context = page1["content"]
        explanation = llm.explain_content(current_context)
        return f"✅ 成功解析第 {page1['page_num']} 页（共{len(pages)}页）\n---\n{explanation}", current_context
    except Exception as e:
        return f"❌ 解析出错：{str(e)}", ""

def handle_question(question, context):
    if not context:
        return "⚠️ 请先上传并解析PDF"
    if not question.strip():
        return "⚠️ 请输入问题"
    return llm.answer_question(context, question)

with gr.Blocks(title="VirtualClassroomAI - 虚拟课堂", css="footer {display:none !important}") as demo:
    gr.Markdown("# 🎓 VirtualClassroomAI 原型")
    gr.Markdown("上传论文/教材，AI教师将为你分段讲解，并支持实时问答。")

    with gr.Row():
        with gr.Column():
            pdf_input = gr.File(label="📄 上传PDF", file_types=[".pdf"])
            process_btn = gr.Button("🚀 开始解析第1页", variant="primary")
        with gr.Column():
            output_explanation = gr.Textbox(label="👩‍ 教师讲解", lines=12)
            context_state = gr.Textbox(visible=False)  # 隐藏状态传递

    process_btn.click(
        fn=process_pdf,
        inputs=[pdf_input],
        outputs=[output_explanation, context_state]
    )

    gr.Markdown("### 💬 向露卡提问")
    with gr.Row():
        question_input = gr.Textbox(label="你的问题", placeholder="例如：这个概念和上一章有什么联系？")
        ask_btn = gr.Button("提问")
    answer_output = gr.Textbox(label="回答", lines=5)

    ask_btn.click(
        fn=handle_question,
        inputs=[question_input, context_state],
        outputs=[answer_output]
    )

if __name__ == "__main__":
    demo.launch(share=False, server_name="127.0.0.1", server_port=7860)