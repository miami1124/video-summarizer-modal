"""
modal_app.py - Modal Serverless 應用程式入口

功能: 整合所有工具，提供 Google Drive 影片分析 API
部署: modal deploy modal_app.py
本地測試: modal run modal_app.py
"""

import os
import tempfile
import shutil
from pathlib import Path

import modal

# 定義 Modal Image
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "gdown>=4.7.0",
        "pydub>=0.25.1",
        "openai>=1.0.0",
        "python-dotenv>=1.0.0",
        "fastapi[standard]",
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.0",
    )
)

# 建立 Modal App
app = modal.App("video-analyzer", image=image)


# ========== Tool Functions (嵌入版本) ==========

def extract_file_id(url_or_id: str) -> str:
    """從 Google Drive URL 中提取檔案 ID"""
    import re
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url_or_id)
    if match:
        return match.group(1)
    if re.match(r'^[a-zA-Z0-9_-]+$', url_or_id):
        return url_or_id
    raise ValueError(f"無法從輸入中提取 Google Drive 檔案 ID: {url_or_id}")


def download_from_gdrive(url_or_id: str, output_dir: str) -> dict:
    """從 Google Drive 下載影片"""
    import gdown
    try:
        file_id = extract_file_id(url_or_id)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        download_url = f"https://drive.google.com/uc?id={file_id}"
        output_file = gdown.download(
            url=download_url,
            output=str(output_path / f"{file_id}"),
            quiet=False,
            fuzzy=True
        )
        if output_file is None:
            return {
                "success": False,
                "error": "下載失敗。請確認連結為公開狀態（知道連結的人都可以檢視）"
            }
        return {"success": True, "file_path": str(Path(output_file).absolute())}
    except Exception as e:
        return {"success": False, "error": f"下載錯誤: {str(e)}"}


def is_safe_url(url: str) -> tuple[bool, str]:
    """檢查 URL 是否安全（防止 SSRF 攻擊）"""
    from urllib.parse import urlparse
    import socket

    try:
        parsed = urlparse(url)

        # 必須是 http 或 https
        if parsed.scheme not in ['http', 'https']:
            return False, "只支援 http/https 連結"

        # 必須有主機名稱
        if not parsed.hostname:
            return False, "無效的網址格式"

        hostname = parsed.hostname.lower()

        # 禁止 localhost 和內部網路
        blocked_hosts = ['localhost', '127.0.0.1', '0.0.0.0']
        if hostname in blocked_hosts:
            return False, "不允許存取本地網址"

        # 禁止私有 IP 範圍
        try:
            ip = socket.gethostbyname(hostname)
            ip_parts = [int(p) for p in ip.split('.')]

            # 10.x.x.x
            if ip_parts[0] == 10:
                return False, "不允許存取內部網路"
            # 172.16.x.x - 172.31.x.x
            if ip_parts[0] == 172 and 16 <= ip_parts[1] <= 31:
                return False, "不允許存取內部網路"
            # 192.168.x.x
            if ip_parts[0] == 192 and ip_parts[1] == 168:
                return False, "不允許存取內部網路"
            # 127.x.x.x
            if ip_parts[0] == 127:
                return False, "不允許存取本地網址"
            # 169.254.x.x (Link-local / AWS metadata)
            if ip_parts[0] == 169 and ip_parts[1] == 254:
                return False, "不允許存取此網址"

        except socket.gaierror:
            # 無法解析 DNS，讓 requests 處理
            pass

        return True, ""

    except Exception as e:
        return False, f"網址驗證失敗：{str(e)}"


def fetch_news_content(url: str) -> dict:
    """從新聞網址抓取文章內容（含安全性檢查）"""
    import requests
    from bs4 import BeautifulSoup

    # 安全性檢查
    is_safe, error_msg = is_safe_url(url)
    if not is_safe:
        return {"success": False, "error": error_msg}

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)

        # 檢查最終 URL 是否安全（防止重新導向攻擊）
        final_url = response.url
        is_safe_final, error_msg_final = is_safe_url(final_url)
        if not is_safe_final:
            return {"success": False, "error": f"網址重新導向到不安全的位置"}

        response.raise_for_status()
        response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.text, 'html.parser')

        # 移除不需要的元素
        for element in soup.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            element.decompose()

        # 嘗試找到文章標題
        title = ""
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 嘗試找到文章內容（常見的新聞網站結構）
        content = ""

        # 嘗試常見的文章容器
        article_selectors = [
            'article',
            '[class*="article"]',
            '[class*="content"]',
            '[class*="story"]',
            '[class*="post"]',
            '[class*="entry"]',
            '.news-content',
            '#article-content',
            '.article-body',
            'main',
        ]

        for selector in article_selectors:
            article = soup.select_one(selector)
            if article:
                # 取得所有段落文字
                paragraphs = article.find_all(['p', 'h2', 'h3'])
                if paragraphs:
                    content = '\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                    if len(content) > 100:  # 確保有足夠內容
                        break

        # 如果還是找不到，取所有段落
        if not content or len(content) < 100:
            paragraphs = soup.find_all('p')
            content = '\n'.join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])

        if not content:
            return {"success": False, "error": "無法從網頁中提取文章內容"}

        # 清理內容
        content = content.replace('\n\n\n', '\n\n').strip()

        return {
            "success": True,
            "title": title,
            "content": content[:5000]  # 限制長度
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "連線逾時，請稍後再試"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"無法連線到網頁：{str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"抓取新聞內容時發生錯誤：{str(e)}"}


def get_video_duration(video_path: str) -> float:
    """使用 ffprobe 取得影片時長"""
    import subprocess
    import json
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe 執行失敗: {result.stderr}")
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def convert_to_mp3(video_path: str, output_dir: str) -> dict:
    """將影片轉換為 MP3"""
    import subprocess
    MAX_DURATION = 2 * 60 * 60  # 2 hours
    try:
        video_path = Path(video_path)
        duration = get_video_duration(str(video_path))
        if duration > MAX_DURATION:
            return {
                "success": False,
                "error": f"影片時長 ({duration/3600:.1f} 小時) 超過 2 小時限制。請裁剪影片後重試。"
            }
        output_path = Path(output_dir)
        mp3_path = output_path / f"{video_path.stem}.mp3"
        cmd = [
            "ffmpeg", "-i", str(video_path), "-vn",
            "-acodec", "libmp3lame", "-ab", "64k", "-ar", "16000", "-ac", "1",
            "-y", str(mp3_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # 檢查是否為非影片檔案的錯誤
            stderr_lower = result.stderr.lower()
            if "invalid data" in stderr_lower or "no such file" in stderr_lower:
                return {"success": False, "error": "無法處理此檔案，請確認上傳的是影片檔案（MP4、MOV、AVI 等）"}
            if "does not contain" in stderr_lower or "audio" in stderr_lower:
                return {"success": False, "error": "此檔案沒有音訊內容，無法進行語音轉文字"}
            return {"success": False, "error": "檔案格式不支援，請確認上傳的是影片檔案"}
        return {
            "success": True,
            "mp3_path": str(mp3_path.absolute()),
            "file_size_bytes": mp3_path.stat().st_size,
            "duration_seconds": duration
        }
    except RuntimeError as e:
        if "ffprobe" in str(e):
            return {"success": False, "error": "無法讀取此檔案，請確認上傳的是影片檔案（MP4、MOV、AVI 等）"}
        return {"success": False, "error": f"轉換錯誤: {str(e)}"}
    except KeyError:
        return {"success": False, "error": "此檔案不是有效的影片格式，請上傳影片檔案"}
    except Exception as e:
        return {"success": False, "error": "檔案處理失敗，請確認上傳的是影片檔案"}


def chunk_audio(mp3_path: str, output_dir: str, max_size_bytes: int = 24 * 1024 * 1024) -> dict:
    """將音檔切割成多個片段"""
    from pydub import AudioSegment
    WHISPER_MAX = 25 * 1024 * 1024
    try:
        mp3_path = Path(mp3_path)
        file_size = mp3_path.stat().st_size
        if file_size <= WHISPER_MAX:
            return {
                "success": True,
                "chunks": [{"path": str(mp3_path.absolute()), "start_time_seconds": 0.0}],
                "needs_chunking": False
            }
        audio = AudioSegment.from_mp3(str(mp3_path))
        total_ms = len(audio)
        bytes_per_second = file_size / (total_ms / 1000)
        max_chunk_ms = int((max_size_bytes / bytes_per_second) * 1000)
        num_chunks = int(total_ms / max_chunk_ms) + 1
        output_path = Path(output_dir)
        chunks = []
        for i in range(num_chunks):
            start_ms = i * max_chunk_ms
            end_ms = min((i + 1) * max_chunk_ms, total_ms)
            chunk = audio[start_ms:end_ms]
            chunk_path = output_path / f"{mp3_path.stem}_chunk_{i:03d}.mp3"
            chunk.export(str(chunk_path), format="mp3", bitrate="64k")
            chunks.append({
                "path": str(chunk_path.absolute()),
                "start_time_seconds": start_ms / 1000
            })
        return {"success": True, "chunks": chunks, "needs_chunking": True}
    except Exception as e:
        return {"success": False, "error": f"切割錯誤: {str(e)}"}


def transcribe_audio(audio_paths: list, time_offsets: list, api_key: str) -> dict:
    """使用 Whisper API 並行轉錄多個音檔片段"""
    from openai import OpenAI
    from concurrent.futures import ThreadPoolExecutor, as_completed
    client = OpenAI(api_key=api_key)

    def _transcribe_chunk(audio_path: str, offset: float):
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )
        segments = []
        for seg in response.segments:
            segments.append({
                "start": seg.start + offset,
                "end": seg.end + offset,
                "text": seg.text
            })
        return response.text, segments

    try:
        # 單一片段直接處理，不需要執行緒池
        if len(audio_paths) == 1:
            text, segments = _transcribe_chunk(audio_paths[0], time_offsets[0])
            return {
                "success": True,
                "full_transcript": text,
                "segments": segments
            }

        # 多片段並行處理
        all_segments = []
        all_texts = [None] * len(audio_paths)
        max_workers = min(len(audio_paths), 4)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, (path, offset) in enumerate(zip(audio_paths, time_offsets)):
                future = executor.submit(_transcribe_chunk, path, offset)
                futures[future] = i

            for future in as_completed(futures):
                i = futures[future]
                text, segments = future.result()
                all_texts[i] = text
                all_segments.extend(segments)

        all_segments.sort(key=lambda x: x["start"])
        return {
            "success": True,
            "full_transcript": " ".join(all_texts),
            "segments": all_segments
        }
    except Exception as e:
        return {"success": False, "error": f"轉錄錯誤: {str(e)}"}


def summarize_transcript(segments: list, api_key: str) -> dict:
    """使用 GPT-4o 生成摘要"""
    import json
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    # 計算影片總長度（秒）
    if segments:
        video_duration_seconds = max(seg["end"] for seg in segments)
        video_duration_minutes = video_duration_seconds / 60
        # 每 1.5 分鐘約 1 個重點，確保更詳細的覆蓋
        min_points = max(10, int(video_duration_minutes / 1.5))
        max_points = max(20, int(video_duration_minutes * 1.2))
    else:
        min_points, max_points = 10, 20
        video_duration_minutes = 0

    SYSTEM_PROMPT = f"""你是一個專業的影片內容分析師。你的任務是根據影片的轉錄文字，生成一份**精確且詳細**的時間軸重點摘要。

## 重要原則（必須遵守）
- **只能使用轉錄文字中實際出現的內容**，絕對不能編造或推測
- **時間必須精確**：標記的時間點必須是該主題「真正開始被討論」的時間，不是提及關鍵詞的時間
- 如果一個主題從 09:00 開始討論到 12:00，時間應標記為 09:00-12:00 這個範圍內真正開始深入討論的時間點
- title 和 description 必須準確反映該時間點講者實際說的內容
- 使用轉錄文字中的原話或關鍵詞彙
- **必須涵蓋整部影片的內容，從開頭到結尾**

## 時間標記原則
- 仔細閱讀逐字稿的時間戳，找出每個主題「真正開始」的時間點
- 如果講者在某時間點只是「提到」某件事，但後來才「詳細說明」，應該標記詳細說明開始的時間
- 每個時間點之間應該有合理的間隔，避免連續多個重點擠在相近的時間

## 輸出規則
1. 必須使用繁體中文
2. 時間格式為 MM:SS（例如：02:30），必須精確對應轉錄文字中的時間戳
3. 每個重點必須包含：
   - time：該主題真正開始被討論的時間點
   - title：該段落的核心主題（10-25 字），使用講者實際提到的詞彙
   - description：詳細說明該段落的具體內容（50-120 字），包含講者提到的具體細節、數字、人名等資訊
4. 這部影片約 {video_duration_minutes:.0f} 分鐘，請提取 {min_points}-{max_points} 個重點，**平均分布在整部影片中**
5. 重點要依照時間順序排列
6. **最後一個重點的時間必須接近影片結尾**
7. description 要盡量詳細，包含講者提到的所有重要資訊

## 輸出格式
請以 JSON 格式輸出，結構如下：
{{
  "summary": [
    {{"time": "00:00", "title": "重點標題", "description": "詳細描述該段落的具體內容，包含講者提到的細節"}},
    ...
  ]
}}

只輸出 JSON，不要有其他文字。"""
    try:
        lines = []
        for seg in segments:
            minutes = int(seg["start"] // 60)
            seconds = int(seg["start"] % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg['text'].strip()}")
        transcript = "\n".join(lines)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"請根據以下影片轉錄文字，生成時間軸重點摘要：\n\n{transcript}"}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return {"success": True, "summary": result.get("summary", [])}
    except Exception as e:
        return {"success": False, "error": f"摘要生成錯誤: {str(e)}"}


def attach_transcript_to_summary(summary: list, segments: list) -> list:
    """將逐字稿片段依時間範圍附加到對應的摘要重點"""
    def time_to_seconds(t: str) -> float:
        try:
            parts = t.split(":")
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 0.0

    parsed = []
    for item in summary:
        parsed.append({**item, "_start_sec": time_to_seconds(item.get("time", "00:00"))})
    parsed.sort(key=lambda x: x["_start_sec"])

    result = []
    for i, item in enumerate(parsed):
        start_sec = item["_start_sec"]
        end_sec = parsed[i + 1]["_start_sec"] if i + 1 < len(parsed) else float("inf")

        transcript_lines = []
        for seg in segments:
            if start_sec <= seg["start"] < end_sec:
                m = int(seg["start"] // 60)
                s = int(seg["start"] % 60)
                transcript_lines.append(f"[{m:02d}:{s:02d}] {seg['text'].strip()}")

        item_out = {k: v for k, v in item.items() if not k.startswith("_")}
        item_out["transcript"] = transcript_lines
        result.append(item_out)

    return result


def match_news_with_transcript(segments: list, news_script: str, api_key: str) -> dict:
    """使用 GPT-4o 比對新聞稿與逐字稿，找出時間對應"""
    import json
    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    SYSTEM_PROMPT = """你是一個專業的影片內容分析師。你的任務是將新聞稿的段落與影片逐字稿進行比對，找出對應關係。

## 任務說明
1. 仔細閱讀新聞稿，將其拆分成多個主要段落或主題
2. 在影片逐字稿中尋找與每個新聞稿段落相關的內容
3. 即使只是部分相關或主題類似，也應該建立配對
4. 盡可能找出所有可能的對應關係

## 判斷相關的標準（寬鬆判斷）
- 討論相同或相似的主題
- 提到相同的人物、地點、事件
- 使用相似的關鍵詞
- 描述相關的情況或背景
- 即使用詞不同，但講的是同一件事

## 重要：盡量找出配對
- 新聞稿通常是根據影片內容撰寫的，所以應該能找到對應
- 不要因為用詞略有不同就放棄配對
- 優先找出有對應的部分，而不是專注於無法配對的部分

## 輸出規則
1. 必須使用繁體中文
2. 時間格式為 MM:SS-MM:SS（例如：02:30-05:15）
3. 每個配對必須包含：
   - time_range：對應的時間區間（根據逐字稿的時間戳）
   - news_paragraph：新聞稿中對應的段落原文（直接引用，20-80 字）
   - video_content：該時間區間的影片內容摘要（20-50 字）
   - match_reason：配對原因（10-20 字）
4. 只有當新聞稿與影片內容完全無關時，才回傳空陣列

## 輸出格式
請以 JSON 格式輸出：
{
  "matches": [
    {
      "time_range": "00:00-02:30",
      "news_paragraph": "新聞稿原文段落...",
      "video_content": "影片中對應的內容...",
      "match_reason": "都在討論某某主題"
    }
  ]
}

只輸出 JSON，不要有其他文字。"""

    try:
        # 準備逐字稿
        lines = []
        for seg in segments:
            minutes = int(seg["start"] // 60)
            seconds = int(seg["start"] % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg['text'].strip()}")
        transcript = "\n".join(lines)

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"請比對以下新聞稿與影片逐字稿，找出對應的時間區間：\n\n## 新聞稿\n{news_script}\n\n## 影片逐字稿\n{transcript}"}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return {
            "success": True,
            "matches": result.get("matches", []),
            "no_match_reason": result.get("no_match_reason", "")
        }
    except Exception as e:
        return {"success": False, "error": f"新聞稿比對錯誤: {str(e)}"}


# ========== Modal Function ==========

@app.function(
    secrets=[modal.Secret.from_name("openai-secret")],
    timeout=1200,  # 20 分鐘 timeout（支援長影片）
    memory=4096,  # 4GB 記憶體（處理大檔案）
)
def analyze_video(gdrive_url: str, news_url: str = "") -> dict:
    """
    分析 Google Drive 影片，生成時間軸摘要

    Args:
        gdrive_url: Google Drive 公開連結
        news_url: 新聞稿網址（選填），用於抓取內容並比對時間軸

    Returns:
        dict: {
            "success": bool,
            "summary": [...],
            "full_transcript": str,
            "news_matching": [...] (如果有提供新聞稿網址),
            "error": str (失敗時)
        }
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"success": False, "error": "未設定 OPENAI_API_KEY"}

    # 建立暫存目錄
    work_dir = tempfile.mkdtemp()

    try:
        print(f"[1/5] 下載影片: {gdrive_url}")
        result = download_from_gdrive(gdrive_url, work_dir)
        if not result["success"]:
            return result
        video_path = result["file_path"]

        print(f"[2/5] 轉換為 MP3")
        result = convert_to_mp3(video_path, work_dir)
        if not result["success"]:
            return result
        mp3_path = result["mp3_path"]

        print(f"[3/5] 檢查並切割音檔")
        result = chunk_audio(mp3_path, work_dir)
        if not result["success"]:
            return result
        chunks = result["chunks"]
        audio_paths = [c["path"] for c in chunks]
        time_offsets = [c["start_time_seconds"] for c in chunks]

        print(f"[4/5] Whisper 轉錄 ({len(chunks)} 個片段)")
        result = transcribe_audio(audio_paths, time_offsets, api_key)
        if not result["success"]:
            return result
        segments = result["segments"]
        full_transcript = result["full_transcript"]

        print(f"[5/5] GPT-4o 生成摘要")
        result = summarize_transcript(segments, api_key)
        if not result["success"]:
            return result

        enriched_summary = attach_transcript_to_summary(result["summary"], segments)
        response_data = {
            "success": True,
            "summary": enriched_summary,
            "full_transcript": full_transcript,
            "segments": segments
        }

        # 如果有新聞稿網址，抓取內容並進行比對
        if news_url and news_url.strip():
            print(f"[6/7] 抓取新聞稿內容: {news_url}")
            news_result = fetch_news_content(news_url)

            if news_result["success"]:
                news_content = news_result["content"]
                print(f"[7/7] 比對新聞稿與逐字稿")
                match_result = match_news_with_transcript(segments, news_content, api_key)
                if match_result["success"]:
                    response_data["news_matching"] = match_result["matches"]
                    if match_result.get("no_match_reason"):
                        response_data["no_match_reason"] = match_result["no_match_reason"]
            else:
                # 抓取失敗時記錄錯誤但不中斷整個流程
                response_data["news_matching"] = []
                response_data["no_match_reason"] = f"無法抓取新聞稿內容：{news_result['error']}"

        return response_data

    finally:
        # 清理暫存目錄
        shutil.rmtree(work_dir, ignore_errors=True)


# ========== Web Endpoint ==========

@app.function()
@modal.fastapi_endpoint(method="POST")
def analyze_video_webhook(request: dict) -> dict:
    """
    提交分析任務，立即回傳 job_id 供前端輪詢

    Request Body:
        {
            "gdrive_url": "https://drive.google.com/...",
            "news_url": "https://www.nownews.com/..."  (選填)
        }

    Returns:
        dict: {"success": True, "job_id": "..."}
    """
    gdrive_url = request.get("gdrive_url")
    if not gdrive_url:
        return {"success": False, "error": "缺少 gdrive_url 參數"}

    news_url = request.get("news_url", "")

    # 非同步啟動分析任務，立即回傳 job_id
    call = analyze_video.spawn(gdrive_url, news_url)
    return {"success": True, "job_id": call.object_id}


@app.function()
@modal.fastapi_endpoint(method="POST")
def check_status(request: dict) -> dict:
    """
    查詢分析任務狀態

    Request Body:
        {"job_id": "..."}

    Returns:
        {"status": "processing"} 或
        {"status": "completed", "result": {...}} 或
        {"status": "error", "error": "..."}
    """
    from modal.functions import FunctionCall

    job_id = request.get("job_id", "")
    if not job_id:
        return {"status": "error", "error": "缺少 job_id 參數"}

    try:
        call = FunctionCall.from_id(job_id)
        result = call.get(timeout=0)
        return {"status": "completed", "result": result}
    except TimeoutError:
        return {"status": "processing"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ========== Local Entry Point ==========

@app.local_entrypoint()
def main(gdrive_url: str):
    """
    本地測試入口

    用法: modal run modal_app.py --gdrive-url "https://drive.google.com/..."
    """
    import json
    result = analyze_video.remote(gdrive_url)
    print("\n" + "=" * 50)
    print("分析結果")
    print("=" * 50)
    print(json.dumps(result, indent=2, ensure_ascii=False))
