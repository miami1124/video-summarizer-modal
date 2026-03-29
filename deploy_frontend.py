"""
deploy_frontend.py - 部署 Streamlit 前端到 Modal

部署指令: modal deploy deploy_frontend.py
"""

import modal

# 建立 Modal Image - 加入時間戳強制重建
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "streamlit>=1.30.0",
        "requests>=2.31.0",
    )
    .run_commands("echo 'Build: 2026-02-11-v11'")  # 一鍵複製按鈕
    .add_local_file("frontend.py", "/app/frontend.py")
)

app = modal.App("video-analyzer-frontend", image=image)


@app.function(
    timeout=600,
    scaledown_window=300,
)
@modal.concurrent(max_inputs=10)
@modal.web_server(port=8501, startup_timeout=120)
def run_streamlit():
    """啟動 Streamlit 伺服器"""
    import subprocess
    subprocess.Popen([
        "streamlit", "run", "/app/frontend.py",
        "--server.port=8501",
        "--server.address=0.0.0.0",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ])
