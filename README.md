# 🎬 影片 AI 摘要工具
**Modal × Whisper × GPT-4o × Streamlit**
貼上 Google Drive 連結 → 自動生成逐字稿 + 時間軸重點摘要

🌐 **線上 Demo**：https://drive.google.com/file/d/1WlFblTBHrzTmgia5Kc139ptBN5doQY5p/view?usp=sharing

---

## 背景與痛點

媒體記者拍攝代拍影片上傳雲端後，影片沒有字幕，必須從頭到尾看完才能抓重點，非常耗時。加上部分素材是外語採訪，語言障礙讓問題更嚴重。

## 解決方案

打造一個只需要貼連結的工具，不需要安裝任何軟體，開瀏覽器就能用：

1. 貼上 Google Drive 影片連結
2. Modal 後端下載影片，ffmpeg 提取音訊
3. OpenAI Whisper 自動轉錄逐字稿（支援多語言）
4. GPT-4o 生成時間軸摘要，標注每段重點與時間點

## 進階功能

選填新聞稿網址，系統會自動抓取文章內容，比對影片中對應的時間區間，方便記者確認素材完整度。

## 系統架構

**前端**：Streamlit，部署於 Modal Web Server，無需本地安裝

**後端**：Modal Serverless Function + FastAPI，非同步任務佇列設計（提交任務 → 輪詢狀態 → 取得結果）

**AI**：Whisper API 語音轉文字 + GPT-4o 摘要與比對

**基礎建設**：ffmpeg 音訊處理、長影片自動分段（支援最長 2 小時）

## 實際成果

- ✅ 支援中文、英文、日文、韓文等多語言影片
- ✅ 2–3 分鐘內完成一支 10 分鐘影片的分析
- ✅ 目前於媒體公司內部使用中
- ✅ 使用 Claude Code 搭配 WAT 架構（Workflows / Agents / Tools）開發

## 技術棧

`Modal` `Streamlit` `FastAPI` `OpenAI Whisper` `GPT-4o` `ffmpeg` `Google Drive API` `Claude Code`

---
*Built by Sam｜AI Automation Engineer*
