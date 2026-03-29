"""
frontend.py - Streamlit 前端介面（白色簡約風格 + 專業版面）

功能: 提供使用者介面，讓使用者輸入 Google Drive 連結並分析影片
執行: streamlit run frontend.py
"""

import streamlit as st
import requests
import json
import re
import time
import html as html_lib

# ========== 設定 ==========
MODAL_WEBHOOK_URL = "https://samchang176--video-analyzer-analyze-video-webhook.modal.run"
MODAL_STATUS_URL = "https://samchang176--video-analyzer-check-status.modal.run"

# ========== 工具函數 ==========
def extract_file_id(url: str) -> str:
    """從 Google Drive URL 提取檔案 ID"""
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None

def is_valid_gdrive_url(url: str) -> tuple[bool, str]:
    """驗證是否為有效的 Google Drive 影片連結"""
    if not url or not url.strip():
        return False, "請輸入 Google Drive 連結"
    url = url.strip()
    if "docs.google.com/document" in url:
        return False, "這是 Google 文件連結，請上傳影片檔案到雲端硬碟後再分享"
    if "docs.google.com/spreadsheets" in url:
        return False, "這是 Google 試算表連結，請上傳影片檔案到雲端硬碟後再分享"
    if "docs.google.com/presentation" in url:
        return False, "這是 Google 簡報連結，請上傳影片檔案到雲端硬碟後再分享"
    if "docs.google.com/forms" in url:
        return False, "這是 Google 表單連結，請上傳影片檔案到雲端硬碟後再分享"
    if "drive.google.com" not in url:
        return False, "這不是 Google Drive 連結，請貼上 drive.google.com 的影片分享連結"
    if "/folders/" in url:
        return False, "這是資料夾連結，請分享單一影片檔案的連結"
    file_id = extract_file_id(url)
    if not file_id:
        return False, "無法從連結中提取檔案 ID，請確認是影片檔案的分享連結"
    if len(file_id) < 10:
        return False, "連結格式可能不正確，請重新複製分享連結"
    return True, file_id

# ========== 頁面設定 ==========
st.set_page_config(
    page_title="NN雲端影片重點生成器",
    page_icon="🎬",
    layout="wide"
)

# ========== CSS 樣式 ==========
st.markdown("""
<style>
    /* 隱藏 Streamlit 預設元素 */
    #MainMenu, footer, header {visibility: hidden;}

    /* 整體背景 */
    .stApp {
        background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    }

    /* ========== 文字基礎 ========== */
    h1, h2, h3, h4, h5, h6, p, span, div, label {
        color: #1e293b !important;
    }
    .stMarkdown h5 {
        color: #1e293b !important;
        font-weight: 600 !important;
    }
    .stMarkdown p {
        color: #475569 !important;
    }

    /* ========== 主標題 ========== */
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.3rem;
        animation: fadeInDown 0.6s ease-out;
        letter-spacing: -0.5px;
    }
    .subtitle {
        color: #64748b !important;
        text-align: center;
        font-size: 1.05rem;
        margin-bottom: 2rem;
        animation: fadeInUp 0.6s ease-out 0.2s both;
        letter-spacing: 0.3px;
    }

    /* ========== 動畫 ========== */
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes slideInLeft {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* ========== 按鈕 ========== */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%) !important;
        color: white !important;
        border: none !important;
        padding: 16px 32px !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        border-radius: 12px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 25px rgba(37, 99, 235, 0.5) !important;
        background: linear-gradient(135deg, #1d4ed8 0%, #6d28d9 100%) !important;
    }
    .stButton > button:active {
        transform: translateY(1px) scale(0.98) !important;
        box-shadow: 0 2px 10px rgba(37, 99, 235, 0.4) !important;
        transition: all 0.1s ease !important;
    }
    .stButton > button[kind="secondary"] {
        background: #ffffff !important;
        color: #1e40af !important;
        border: 2px solid #3b82f6 !important;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #eff6ff !important;
        border-color: #2563eb !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25) !important;
    }

    /* ========== 輸入框 ========== */
    .stTextInput > div > div > input {
        background: #ffffff !important;
        border: 2px solid #e2e8f0 !important;
        border-radius: 12px !important;
        color: #1e293b !important;
        padding: 16px !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    .stTextInput > div > div > input::placeholder {
        color: #94a3b8 !important;
    }

    /* ========== 說明區塊 ========== */
    .info-box {
        background: linear-gradient(135deg, #f0f9ff 0%, #f5f3ff 100%);
        border-radius: 16px;
        padding: 24px;
        margin-top: 24px;
        border: 1px solid #e0e7ff;
        animation: fadeInUp 0.6s ease-out 0.3s both;
    }
    .info-box h4 { color: #3b82f6 !important; margin-bottom: 16px; font-size: 1.1rem; }
    .info-box p { color: #475569 !important; margin: 8px 0; font-size: 0.95rem; }

    /* ========== 影片播放器（置頂固定） ========== */
    .video-sticky {
        position: sticky;
        top: 0;
        z-index: 100;
        padding-bottom: 16px;
    }
    .video-wrapper {
        background: #ffffff;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
        animation: fadeIn 0.6s ease-out;
    }
    .video-header {
        background: #f8fafc;
        padding: 10px 16px;
        display: flex;
        align-items: center;
        border-bottom: 1px solid #e2e8f0;
    }
    .dot { width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; }
    .dot-r { background: #ef4444; }
    .dot-y { background: #f59e0b; }
    .dot-g { background: #22c55e; }

    /* ========== 成功橫幅 ========== */
    .success-banner {
        background: linear-gradient(135deg, #dcfce7 0%, #d1fae5 100%);
        border: 1px solid #86efac;
        border-radius: 12px;
        padding: 16px 24px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: fadeInDown 0.5s ease-out;
    }
    .success-banner .icon { font-size: 1.5rem; }
    .success-banner .text { color: #166534 !important; font-weight: 600; }

    /* ========== 摘要區段標題 ========== */
    .section-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 32px 0 20px;
        animation: fadeIn 0.5s ease-out;
    }
    .section-header-icon {
        width: 40px;
        height: 40px;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
    }
    .section-header-text {
        font-size: 1.4rem;
        font-weight: 700;
        color: #1e293b !important;
    }
    .section-header-count {
        background: #f1f5f9;
        color: #64748b !important;
        font-size: 0.85rem;
        font-weight: 600;
        padding: 4px 12px;
        border-radius: 20px;
    }

    /* ========== 時間軸容器 ========== */
    .timeline-container {
        position: relative;
        padding-left: 48px;
    }
    .timeline-container::before {
        content: '';
        position: absolute;
        left: 19px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: linear-gradient(180deg, #3b82f6 0%, #8b5cf6 50%, #e2e8f0 100%);
        border-radius: 2px;
    }

    /* ========== 時間軸節點 ========== */
    .timeline-item {
        position: relative;
        margin-bottom: 16px;
        animation: slideInLeft 0.4s ease-out both;
    }
    .timeline-dot {
        position: absolute;
        left: -37px;
        top: 18px;
        width: 14px;
        height: 14px;
        background: #ffffff;
        border: 3px solid #3b82f6;
        border-radius: 50%;
        z-index: 2;
        transition: all 0.3s ease;
    }
    .timeline-item:hover .timeline-dot {
        background: #3b82f6;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.2);
    }
    .timeline-number {
        position: absolute;
        left: -48px;
        top: 42px;
        font-size: 0.7rem;
        color: #94a3b8 !important;
        font-weight: 600;
        width: 24px;
        text-align: center;
    }

    /* ========== 時間軸卡片 ========== */
    .timeline-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        border: 1px solid #f1f5f9;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .timeline-card:hover {
        transform: translateX(6px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.1);
        border-color: #e0e7ff;
    }
    .time-tag {
        display: inline-block;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        color: white !important;
        padding: 3px 10px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 700;
        font-family: 'SF Mono', 'Menlo', monospace;
        letter-spacing: 0.5px;
        margin-bottom: 10px;
    }
    .point-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #1e293b !important;
        margin-bottom: 8px;
        line-height: 1.4;
    }
    .point-desc {
        color: #64748b !important;
        font-size: 0.92rem;
        line-height: 1.7;
    }

    /* ========== 分析中卡片 ========== */
    .analyzing-card {
        background: #ffffff;
        border-radius: 20px;
        padding: 48px 32px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08);
        border: 1px solid #e2e8f0;
        text-align: center;
        animation: fadeIn 0.5s ease-out;
    }
    .analyzing-spinner {
        width: 64px;
        height: 64px;
        border: 4px solid #e2e8f0;
        border-top: 4px solid #3b82f6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 24px;
    }
    .analyzing-title { font-size: 1.5rem; font-weight: 700; color: #1e293b !important; margin-bottom: 8px; }
    .analyzing-subtitle { color: #64748b !important; font-size: 1rem; }
    .progress-steps {
        background: #f8fafc;
        border-radius: 12px;
        padding: 20px 24px;
        margin-top: 24px;
        text-align: left;
    }
    .progress-step {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 8px 0;
        color: #64748b !important;
        font-size: 0.95rem;
    }
    .progress-step.active { color: #3b82f6 !important; font-weight: 600; }

    /* ========== 展開區塊 ========== */
    .streamlit-expanderHeader,
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details > summary {
        background: #f8fafc !important;
        border-radius: 12px !important;
        color: #1e293b !important;
    }
    /* 展開後 header 保持淺色（不變黑） */
    [data-testid="stExpander"] details[open] > summary,
    [data-testid="stExpander"] summary:hover,
    [data-testid="stExpander"] summary:focus,
    [data-testid="stExpander"] summary:active,
    .streamlit-expanderHeader:hover,
    .streamlit-expanderHeader:focus,
    .streamlit-expanderHeader[aria-expanded="true"] {
        background: #eef2f7 !important;
        color: #1e293b !important;
    }
    .streamlit-expanderHeader p,
    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span {
        color: #1e293b !important;
        font-weight: 600 !important;
        -webkit-text-fill-color: #1e293b !important;
    }
    .streamlit-expanderContent {
        background: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 0 0 12px 12px !important;
    }

    /* ========== 程式碼/文字區塊 - 深色文字 ========== */
    .stTextArea textarea,
    [data-testid="stExpander"] .stTextArea textarea,
    .streamlit-expanderContent .stTextArea textarea {
        color: #1e293b !important;
        background: #f8fafc !important;
        -webkit-text-fill-color: #1e293b !important;
    }
    .stCodeBlock,
    [data-testid="stExpander"] .stCodeBlock,
    .streamlit-expanderContent .stCodeBlock { background: #f8fafc !important; }
    .stCodeBlock code,
    [data-testid="stExpander"] .stCodeBlock code { color: #334155 !important; -webkit-text-fill-color: #334155 !important; }
    pre { color: #334155 !important; background: #f8fafc !important; }
    code { color: #334155 !important; }

    /* ========== 分隔線 ========== */
    hr {
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
        margin: 24px 0;
    }

    /* ========== Footer ========== */
    .app-footer {
        text-align: center;
        padding: 32px 0 16px;
        color: #94a3b8 !important;
        font-size: 0.85rem;
        animation: fadeIn 0.5s ease-out;
    }
    .app-footer a { color: #3b82f6 !important; text-decoration: none; }
    .footer-divider {
        width: 60px;
        height: 2px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        margin: 0 auto 16px;
        border-radius: 2px;
    }

    /* ========== 回到頂部 ========== */
    .back-to-top {
        position: fixed;
        bottom: 32px;
        right: 32px;
        width: 44px;
        height: 44px;
        background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
        color: white !important;
        border: none;
        border-radius: 50%;
        font-size: 1.2rem;
        cursor: pointer;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
        z-index: 999;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.3s ease;
        text-decoration: none;
    }
    .back-to-top:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(59, 130, 246, 0.5);
    }

    /* ========== 動畫延遲 ========== */
    .timeline-item:nth-child(1) { animation-delay: 0.05s; }
    .timeline-item:nth-child(2) { animation-delay: 0.1s; }
    .timeline-item:nth-child(3) { animation-delay: 0.15s; }
    .timeline-item:nth-child(4) { animation-delay: 0.2s; }
    .timeline-item:nth-child(5) { animation-delay: 0.25s; }
    .timeline-item:nth-child(6) { animation-delay: 0.3s; }
    .timeline-item:nth-child(7) { animation-delay: 0.35s; }
    .timeline-item:nth-child(8) { animation-delay: 0.4s; }
    .timeline-item:nth-child(9) { animation-delay: 0.45s; }
    .timeline-item:nth-child(10) { animation-delay: 0.5s; }
    .timeline-item:nth-child(11) { animation-delay: 0.55s; }
    .timeline-item:nth-child(12) { animation-delay: 0.6s; }
    .timeline-item:nth-child(13) { animation-delay: 0.65s; }
    .timeline-item:nth-child(14) { animation-delay: 0.7s; }
    .timeline-item:nth-child(15) { animation-delay: 0.75s; }
</style>
""", unsafe_allow_html=True)

# ========== 主標題 ==========
st.markdown('<div id="top"></div>', unsafe_allow_html=True)
st.markdown('<h1 class="main-title">🎬 NN雲端影片重點生成器</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">AI 智慧分析影片內容，一鍵生成時間軸重點摘要</p>', unsafe_allow_html=True)

# ========== 主要邏輯 ==========

if "analyzing" in st.session_state and st.session_state["analyzing"]:
    # === 分析中頁面（輪詢架構） ===

    # 記錄開始時間
    if "start_time" not in st.session_state:
        st.session_state["start_time"] = time.time()
    elapsed = int(time.time() - st.session_state["start_time"])
    elapsed_min = elapsed // 60
    elapsed_sec = elapsed % 60

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div class="analyzing-card">
            <div class="analyzing-spinner"></div>
            <div class="analyzing-title">🎬 AI 正在分析影片</div>
            <div class="analyzing-subtitle">已經過 {elapsed_min:02d}:{elapsed_sec:02d}，預估需要 2-15 分鐘</div>
            <div class="progress-steps">
                <div class="progress-step active">📥 下載影片中...</div>
                <div class="progress-step">🎵 轉換音檔中...</div>
                <div class="progress-step">🎤 AI 語音辨識中...</div>
                <div class="progress-step">📝 生成重點摘要中...</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        job_id = st.session_state.get("job_id")

        if not job_id:
            # 第一步：提交任務，取得 job_id
            try:
                response = requests.post(
                    MODAL_WEBHOOK_URL,
                    json={"gdrive_url": st.session_state["gdrive_url"]},
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()

                if result.get("success") and result.get("job_id"):
                    st.session_state["job_id"] = result["job_id"]
                    time.sleep(3)
                    st.rerun()
                else:
                    for key in ["analyzing", "job_id", "start_time"]:
                        st.session_state.pop(key, None)
                    st.error(f"❌ {result.get('error', '提交任務失敗')}")

            except requests.exceptions.RequestException as e:
                for key in ["analyzing", "job_id", "start_time"]:
                    st.session_state.pop(key, None)
                st.error(f"❌ 網路錯誤：{str(e)}")
            except Exception as e:
                for key in ["analyzing", "job_id", "start_time"]:
                    st.session_state.pop(key, None)
                st.error(f"❌ 發生錯誤：{str(e)}")
        else:
            # 第二步：輪詢任務狀態
            try:
                response = requests.post(
                    MODAL_STATUS_URL,
                    json={"job_id": job_id},
                    timeout=30
                )
                response.raise_for_status()
                status_data = response.json()

                if status_data["status"] == "completed":
                    result = status_data["result"]
                    if result.get("success"):
                        st.session_state["summary"] = result.get("summary", [])
                        st.session_state["full_transcript"] = result.get("full_transcript", "")
                        st.session_state["segments"] = result.get("segments", [])
                        for key in ["analyzing", "job_id", "start_time"]:
                            st.session_state.pop(key, None)
                        st.rerun()
                    else:
                        for key in ["analyzing", "job_id", "start_time"]:
                            st.session_state.pop(key, None)
                        st.error(f"❌ {result.get('error', '分析失敗')}")
                        if st.button("🔄 重試"):
                            st.rerun()

                elif status_data["status"] == "processing":
                    time.sleep(5)
                    st.rerun()

                else:
                    for key in ["analyzing", "job_id", "start_time"]:
                        st.session_state.pop(key, None)
                    st.error(f"❌ {status_data.get('error', '未知錯誤')}")
                    if st.button("🔄 重試"):
                        st.rerun()

            except requests.exceptions.RequestException:
                # 暫時性網路錯誤，繼續輪詢
                time.sleep(5)
                st.rerun()
            except Exception as e:
                for key in ["analyzing", "job_id", "start_time"]:
                    st.session_state.pop(key, None)
                st.error(f"❌ 發生錯誤：{str(e)}")

elif "summary" in st.session_state:
    # === 結果頁面 ===

    # 返回按鈕
    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("⬅️ 返回", type="secondary", use_container_width=True):
            for key in ["summary", "full_transcript", "segments", "gdrive_url", "job_id", "start_time"]:
                st.session_state.pop(key, None)
            st.rerun()

    # 成功橫幅
    st.markdown("""
    <div class="success-banner">
        <span class="icon">🎉</span>
        <span class="text">分析完成！已為您擷取影片重點</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 影片播放器（上方，置頂）
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        file_id = extract_file_id(st.session_state.get("gdrive_url", ""))
        if file_id:
            st.markdown(f"""
            <div class="video-sticky">
                <div class="video-wrapper">
                    <div class="video-header">
                        <span class="dot dot-r"></span>
                        <span class="dot dot-y"></span>
                        <span class="dot dot-g"></span>
                        <span style="color: #64748b !important; margin-left: 8px; font-size: 0.85rem;">影片播放器</span>
                    </div>
                    <iframe src="https://drive.google.com/file/d/{file_id}/preview"
                            width="100%" height="400" style="border:none; display:block;"
                            allow="autoplay; encrypted-media" allowfullscreen></iframe>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # 時間軸摘要
    summary_list = st.session_state.get("summary", [])
    summary_count = len(summary_list)

    st.markdown(f"""
    <div class="section-header">
        <div class="section-header-icon">📋</div>
        <span class="section-header-text">時間軸摘要</span>
        <span class="section-header-count">{summary_count} 個重點</span>
    </div>
    """, unsafe_allow_html=True)

    # 組合文字用於複製
    summary_lines = []
    for item in summary_list:
        line = f"{item['time']} {item['title']}"
        if item.get('description'):
            line += f"\n   {item['description']}"
        summary_lines.append(line)
    summary_text = "\n\n".join(summary_lines)

    # 一鍵複製按鈕
    import streamlit.components.v1 as components
    escaped_text = json.dumps(summary_text, ensure_ascii=False)
    components.html(f"""
    <style>
        .copy-btn {{
            background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
            color: white;
            border: none;
            padding: 8px 20px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .copy-btn:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 15px rgba(37, 99, 235, 0.4);
        }}
        .copy-btn:active {{
            transform: scale(0.97);
        }}
        .copy-btn.copied {{
            background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
            box-shadow: 0 2px 8px rgba(22, 163, 74, 0.3);
        }}
    </style>
    <button class="copy-btn" id="copyBtn" onclick="copyText()">
        <span id="copyIcon">📋</span> <span id="copyLabel">複製摘要</span>
    </button>
    <script>
        function copyText() {{
            const text = {escaped_text};
            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.getElementById('copyBtn');
                const icon = document.getElementById('copyIcon');
                const label = document.getElementById('copyLabel');
                btn.classList.add('copied');
                icon.textContent = '✅';
                label.textContent = '已複製！';
                setTimeout(() => {{
                    btn.classList.remove('copied');
                    icon.textContent = '📋';
                    label.textContent = '複製摘要';
                }}, 2000);
            }});
        }}
    </script>
    """, height=50)

    # 時間軸卡片
    col_left, col_main, col_right = st.columns([0.5, 4, 0.5])
    with col_main:
        st.markdown('<div class="timeline-container">', unsafe_allow_html=True)
        for idx, item in enumerate(summary_list):
            safe_title = html_lib.escape(item.get('title', ''))
            safe_desc = html_lib.escape(item.get('description', ''))
            safe_time = html_lib.escape(item.get('time', ''))
            desc_html = f'<div class="point-desc">{safe_desc}</div>' if safe_desc else ''
            delay = round(0.05 + idx * 0.05, 2)
            st.markdown(f"""
            <div class="timeline-item" style="animation-delay: {delay}s;">
                <div class="timeline-dot"></div>
                <div class="timeline-number">#{idx + 1}</div>
                <div class="timeline-card">
                    <span class="time-tag">{safe_time}</span>
                    <div class="point-title">{safe_title}</div>
                    {desc_html}
                </div>
            </div>
            """, unsafe_allow_html=True)

            transcript_lines = item.get('transcript', [])
            if transcript_lines:
                with st.expander(f"📄 {item.get('time', '')} 對應逐字稿（{len(transcript_lines)} 段）"):
                    st.code("\n".join(transcript_lines), language=None)

        st.markdown('</div>', unsafe_allow_html=True)

    # 底部工具區
    st.markdown("<hr>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.expander("📝 純文字版本（可複製）"):
            st.code(summary_text, language=None)
    with col2:
        segments_data = st.session_state.get("segments", [])
        if segments_data:
            with st.expander("📜 完整逐字稿（含時間軸）"):
                timestamped_lines = []
                for seg in segments_data:
                    m = int(seg["start"] // 60)
                    s = int(seg["start"] % 60)
                    timestamped_lines.append(f"[{m:02d}:{s:02d}] {seg['text'].strip()}")
                st.text_area("", "\n".join(timestamped_lines), height=300, label_visibility="collapsed")
        elif st.session_state.get("full_transcript"):
            with st.expander("📜 完整轉錄文字"):
                st.text_area("", st.session_state["full_transcript"], height=200, label_visibility="collapsed")

    # Footer
    st.markdown("""
    <div class="app-footer">
        <div class="footer-divider"></div>
        <div>Powered by AI &nbsp;·&nbsp; Whisper + GPT-4o</div>
        <div style="margin-top: 4px; font-size: 0.8rem;">NN雲端影片重點生成器 &copy; 2026</div>
    </div>
    """, unsafe_allow_html=True)

    # 回到頂部按鈕
    st.markdown("""
    <a href="#top" class="back-to-top" title="回到頂部">↑</a>
    """, unsafe_allow_html=True)

else:
    # === 輸入頁面 ===
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("##### 📹 影片連結")
        gdrive_url = st.text_input(
            "Google Drive 連結",
            placeholder="請貼上 Google Drive 影片連結...",
            label_visibility="collapsed"
        )

        url_is_valid = True
        if gdrive_url and gdrive_url.strip():
            is_valid, result = is_valid_gdrive_url(gdrive_url)
            if not is_valid:
                st.error(f"❌ 請輸入有效的 Google Drive 雲端連結")
                url_is_valid = False

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✨ 開始分析", use_container_width=True, disabled=not url_is_valid or not gdrive_url):
            st.session_state["analyzing"] = True
            st.session_state["gdrive_url"] = gdrive_url
            st.rerun()

        st.markdown("""
        <div class="info-box">
            <h4>💡 使用說明</h4>
            <p>1️⃣ 將<strong>影片檔案</strong>上傳到 Google Drive，設為公開</p>
            <p>2️⃣ 複製分享連結，貼到上方欄位</p>
            <p>3️⃣ 點擊「開始分析」</p>
            <p style="margin-top: 16px; color: #64748b !important; font-size: 0.9rem;">
                📹 支援格式：MP4、MOV、AVI 等 ｜ ⏱️ 長度上限：2 小時 ｜ ⏳ 處理時間：2-15 分鐘
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Footer（輸入頁也有）
    st.markdown("""
    <div class="app-footer" style="margin-top: 60px;">
        <div class="footer-divider"></div>
        <div>Powered by AI &nbsp;·&nbsp; Whisper + GPT-4o</div>
        <div style="margin-top: 4px; font-size: 0.8rem;">NN雲端影片重點生成器 &copy; 2026</div>
    </div>
    """, unsafe_allow_html=True)
