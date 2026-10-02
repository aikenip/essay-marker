# DSE 英文作文交卷匣（Essay Marker）

香港中學老師用的簡單網站：**只負責學生登入同交卷（上傳題目／作文圖片）**。  
批改唔會喺網站呼叫 API，而係由老師的 **Grok 助手**（或老師喺網頁貼上批改）完成。

> 本站只負責交卷；批改由老師的 Grok 助手處理。

## 功能

- Session 登入（老師／學生）
- 學生上傳題目圖 + 作文圖 → 狀態「待批改」
- 老師查看所有交卷同圖片縮圖
- 老師可喺詳情頁貼上批改；或用 CLI 寫回（畀 Bot 用）
- SQLite 儲存用戶同交卷歷史

## 快速開始

```bash
cd /workspace/essay-marker

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

./start.sh
# 或：python app.py
```

瀏覽器：http://127.0.0.1:5000 （監聽 `0.0.0.0:5000`）  
**不需要** `XAI_API_KEY` / `GEMINI_API_KEY`。

## 示範帳號

| 用戶名   | 密碼       | 角色   |
|----------|------------|--------|
| teacher  | teacher123 | 老師   |
| student1 | student123 | 學生   |
| student2 | student123 | 學生   |

## 交卷檔案位置

```
uploads/<submission_id>/
  question_01.jpg
  question_02.png
  essay_01.jpg
  essay_02.jpg
  …
```

## 寫回批改（老師 UI 或 Bot CLI）

**老師網頁：** 打開交卷詳情 → 「寫入／更新批改」文字框 → 儲存。

**CLI（Grok Bot）：**

```bash
cd /workspace/essay-marker
source .venv/bin/activate
python scripts/save_marking.py --id 3 --file /path/to/marking.md
# 或
python scripts/save_marking.py --id 3 --text "# 總評\n…"
# 或
cat marking.md | python scripts/save_marking.py --id 3 --stdin
```

成功後 `status=marked`，學生可喺網站睇到批改。

## 目錄

```
essay-marker/
  app.py
  emarker/
    db.py
    prompt.py          # 批改結構參考（畀助手用，網站唔再呼叫 LLM）
  scripts/save_marking.py
  templates/
  static/style.css
  uploads/
  data/app.db
  requirements.txt
  start.sh
```

## Deploy on Render

1. Push this project to GitHub.
2. In Render, choose **New Web Service** and connect the repository.
3. Select the **Free** plan and deploy (the included `render.yaml` can also be used as a Blueprint).
4. Set `FLASK_SECRET_KEY` in the service environment (Render can generate a value).

注意：Render free tier 沒有 persistent disk，所以 SQLite 同 `uploads/` 係 ephemeral；redeploy/restart 後可能會 reset。之後如加 paid disk，請設定 `DATA_DIR=/var/data` 同 `UPLOAD_DIR=/var/data/uploads`。
