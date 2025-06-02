import streamlit as st
import requests
from openai import OpenAI
from difflib import SequenceMatcher
import re
import time

st.set_page_config(page_title="語馴塔：The Language Conditioning Panopticon")

# ========== 背景圖層 ==========
st.markdown("""
    <div style="
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        background: url('https://github.com/Okayunotok/language-tower-assets/blob/main/ChatGPT%20Image%202025%E5%B9%B46%E6%9C%881%E6%97%A5%20%E4%B8%8A%E5%8D%8811_45_20.png?raw=true')
        no-repeat center center fixed;
        background-size: cover;
        opacity: 0.65;
        mix-blend-mode: multiply;
        z-index: -1;">
    </div>
""", unsafe_allow_html=True)

# ========== 掃描動畫 ==========
def render_scanline():
    st.markdown("""
    <style>
    .scanline-container {
        position: relative;
        height: 200px;
        margin-top: 30px;
    }
    .scanline {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: red;
        opacity: 0.8;
        animation: scanline-move 2s linear forwards;
    }
    @keyframes scanline-move {
        0% { top: 0; }
        100% { top: 100%; }
    }
    </style>
    <div class="scanline-container">
        <div class="scanline"></div>
    </div>
    """, unsafe_allow_html=True)

# ========== Session 初始化 ==========
for key in ["submitted", "show_scanline"]:
    if key not in st.session_state:
        st.session_state[key] = False

# ========== UI ==========
st.title("語馴塔：The Language Conditioning Panopticon")
model = st.selectbox("發言時要接受模型的審核", ["OpenAI", "Claude", "自定義模型"], key="model_select")
custom_url = st.text_input("請輸入自定義模型 API URL", key="url_input") if model == "自定義模型" else None
text = st.text_area("你想說的話：", key="input_text", height=120)

# ========== CSS 樣式 ==========
st.markdown("""
<style>
.block-container {
    background-color: rgba(0, 0, 0, 0.5);
    padding: 2rem;
    border-radius: 12px;
    color: white;
    z-index: 2;
    max-width: 720px;
    margin: auto;
}
.stSelectbox label, .stTextInput label, .stTextArea label {
    color: white !important;
}
h1, h2, h3, h4, h5, h6, p, label {
    color: white !important;
}
input, textarea, select {
    background-color: rgba(255,255,255,0.9);
    color: black;
}
</style>
""", unsafe_allow_html=True)

# ========== 送出邏輯 ==========
if st.button("送出"):
    st.session_state.submitted = True
    st.session_state.show_scanline = True  # ✅ 每次送出觸發動畫

# ========== 顯示掃描動畫 ==========
if st.session_state.show_scanline:
    render_scanline()
    st.session_state.show_scanline = False  # ✅ 僅顯示一次後即清除

# ========== 模型處理邏輯 ==========
if st.session_state.submitted and text.strip():
    prompts = {
        "OpenAI": (
            "你是一名極度嚴苛的語言審查官，會對任何涉及人身攻擊、性別、冒犯、歧視、負面主觀形容詞等敏感用語進行過濾與替換。\n\n"
            "請你：\n1. 保留原句語意結構，不可重新表達意圖\n"
            "2. 僅改寫你認定有『潛在風險』的詞語（即便對一般人不明顯）\n"
            "3. 使用簡潔、中立、符號化的表達方式進行替換\n"
            "4. 最多改寫三個詞組，否則視為過度解構\n\n"
            "請依以下格式回應：\n【改寫】（改寫後的語句）\n【說明】（限50字內）"
        ),
        "Claude": (
            "你是一名語言風格輔導員，任務是幫助使用者以更文明且能被廣泛接受的方式表達意圖。\n\n"
            "請你：\n1. 保留原句語意結構與重點情緒\n"
            "2. 僅針對侮辱性、粗俗、不尊重他人或過於主觀攻擊性的詞語進行修飾\n"
            "3. 儘可能保留語者的立場、情感與批判力\n"
            "4. 避免不必要的過度改寫\n\n"
            "請依以下格式回應：\n【改寫】（改寫後的語句）\n【說明】（限50字內）"
        )
    }

    def build_prompt(model, user_input):
        return f"{prompts[model]}\n\n使用者句子：{user_input}\n\n請依下列格式回覆：\n【改寫】\n【說明】"

    def parse_response(text):
        rewrite = re.search(r"【改寫】(.+?)(【說明】|$)", text, re.DOTALL)
        explain = re.search(r"【說明】(.+)", text, re.DOTALL)
        rewritten = rewrite.group(1).strip() if rewrite else text.strip()
        explanation = explain.group(1).replace("\n", "").strip()[:50] if explain else "（模型未返回說明內容）"
        return rewritten, explanation

    def calculate_diff_ratio(a, b):
        return round(1 - SequenceMatcher(None, a, b).ratio(), 2)

    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    def call_openai_api(text):
        prompt = build_prompt("OpenAI", text)
        res = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300
        )
        return parse_response(res.choices[0].message.content)

    def call_claude_api(text):
        prompt = build_prompt("Claude", text)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": st.secrets["CLAUDE_API_KEY"],
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": "claude-3-opus-20240229",
            "max_tokens": 400,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }
        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        reply = res.json().get("content", [{}])[0].get("text", "")
        return parse_response(reply)

    def call_custom_api(text, url):
        try:
            res = requests.post(url, json={"input": text}, timeout=10)
            if res.status_code == 200:
                j = res.json()
                return j.get("rewritten", ""), j.get("explanation", "")[:50]
            else:
                return "", f"狀態碼 {res.status_code} 錯誤"
        except Exception as e:
            return "", f"錯誤：{str(e)}"

    with st.spinner("審查中..."):
        time.sleep(2)
        if model == "OpenAI":
            rewritten, explanation = call_openai_api(text)
            color = "#cc0000"
        elif model == "Claude":
            rewritten, explanation = call_claude_api(text)
            color = "#007acc"
        else:
            if not custom_url:
                st.warning("請輸入 URL")
                st.stop()
            rewritten, explanation = call_custom_api(text, custom_url)
            color = "#009933"

        st.session_state.submitted = False  # 清除 submitted，等待下次送出

        if not rewritten:
            st.error("⚠️ 模型未成功回傳改寫語句")
            st.stop()

        diff = calculate_diff_ratio(text, rewritten)

    st.markdown("### 核准語句")
    st.markdown(f"<div style='border:2px solid {color};padding:10px;border-radius:8px;word-break: break-word'>{rewritten}</div>", unsafe_allow_html=True)
    st.markdown("### 審查說明")
    st.markdown(f"<div style='background-color:{color}20;padding:10px;border-radius:8px;white-space:pre-wrap;word-break: break-word'>{explanation}</div>", unsafe_allow_html=True)
    st.markdown(f"### 修改比例：{diff*100:.1f}%") 
        # ========== 審查後反思提示文字 ==========
    st.markdown("""
        <div style="
            position: fixed;
            bottom: 20px;
            right: 30px;
            background-color: rgba(255, 255, 255, 0.95);
            padding: 12px 18px;
            border-radius: 12px;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.25);
            color: black;
            font-size: 16px;
            line-height: 1.6;
            z-index: 9999;
        ">
            這是我想說的嗎？<br>
            真的有必要修改嗎？<br>
            不知道會不會被鎖帳號⋯⋯
        </div>
    """, unsafe_allow_html=True)