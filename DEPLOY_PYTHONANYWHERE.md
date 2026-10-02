# PythonAnywhere 免費版部署（Beginner）

以下步驟適用於 PythonAnywhere 免費 Beginner 帳戶。介面名稱可能會有少許改動；Python 版本請以帳戶當時可選的版本為準。

## 1. 開戶

1. 到 <https://www.pythonanywhere.com/> 註冊／登入。
2. 免費 Web app 必須使用 `*.pythonanywhere.com` 子網域（例如 `yourname.pythonanywhere.com`），不能使用自訂網域。
3. 免費版只有一個 Web app，並受 CPU 秒數／配額限制。

## 2. 上載程式碼

方法 A（較簡單）：

1. 在本機上載 `essay-marker-pythonanywhere.zip`（Files tab）。
2. 在 `/home/USERNAME/` 解壓，確保最後的專案路徑是 `/home/USERNAME/essay-marker/`，而不是多一層 `/home/USERNAME/essay-marker/essay-marker/`。

方法 B：在 PythonAnywhere 的 Bash console 使用 Git clone（如果專案已放到可存取的 Git repository）：

```bash
cd ~
git clone YOUR_REPOSITORY_URL essay-marker
cd ~/essay-marker
```

也可以在 Files tab 逐個上載專案檔案。請勿上載本機 `.venv/`、`__pycache__/`、舊的 `data/app.db` 或私人學生圖片。

## 3. Bash console：建立 virtualenv 及安裝套件

```bash
cd ~/essay-marker
mkvirtualenv --python=python3.10 essay-marker
pip install -r requirements.txt
```

如果帳戶沒有 Python 3.10，請在 `mkvirtualenv` 使用當時可選的最高 Python 3.x（例如 `python3.12`）：

```bash
mkvirtualenv --python=python3.X essay-marker
pip install -r requirements.txt
```

把 `3.X` 換成你的 Bash console 實際提供的版本。建立 virtualenv 後，`pip` 會在已啟用的 `essay-marker` virtualenv 內執行。

## 4. Web tab 設定

1. 開啟 **Web** tab，按 **Add a new web app**。
2. 選擇免費的 `*.pythonanywhere.com` 網址。
3. 選 **Manual configuration**，再選可用的 **Python 3.x**。
4. 填寫：
   - **Source code**：`/home/USERNAME/essay-marker`
   - **Working directory**：`/home/USERNAME/essay-marker`
   - **Virtualenv**：`/home/USERNAME/.virtualenvs/essay-marker`
5. 將 `USERNAME` 換成你的 PythonAnywhere 使用者名稱。

### WSGI file

在 Web tab 的 **WSGI configuration file** 連結中，刪除原有內容，貼上以下完整內容（把 `USERNAME` 換成你的使用者名稱）：

```python
import os
import sys

project_dir = "/home/USERNAME/essay-marker"
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Secret key is configured in the Web tab environment variables.
from app import app as application
```

這段內容與專案根目錄的 `wsgi.py` 相符；亦可直接參考／複製該檔案。

### Static files（可選）

如需由 PythonAnywhere 直接服務 CSS，可加入：

- **URL**：`/static/`
- **Directory**：`/home/USERNAME/essay-marker/static/`

### Environment variable

在 Web tab 的 environment variables（如該介面提供）加入：

- `FLASK_SECRET_KEY` = 一個長而隨機的秘密字串

不要把真正的 secret key 寫入 Git 或 `wsgi.py`。本專案會使用 `FLASK_SECRET_KEY`；如未設定，程式只會退回開發用預設值，不適合公開部署。

## 5. 啟動及測試

1. 儲存 WSGI 檔案。
2. 按 **Reload**（或 **Reload essay-marker**）Web app。
3. 開啟你的 `https://USERNAME.pythonanywhere.com/`。
4. 預設登入：
   - 老師：`teacher` / `teacher123`
   - 學生：`student1` / `student123`

上線後請盡快在應用程式內改用較安全的帳戶密碼（如功能已提供），並妥善保存 secret key。

## 資料、配額及日後批改

- SQLite 資料庫會寫入專案的 `data/app.db`；上載圖片會寫入 `uploads/`。這些檔案留在 PythonAnywhere 的持久化檔案系統，與免費 Render 不同，重載 Web app 不會因部署而消失。
- Beginner 免費版受 CPU 秒數及其他配額限制；配額接近用盡時網站可能休眠或暫時不可用。免費版亦只有一個 Web app。
- 老師日後可在 **Files** tab 下載 `data/app.db` 及 `uploads/` 備份／取回批改資料。
- Grok Bot 在本機 box 上不會自動看到 PythonAnywhere 的檔案；如要在聊天中協助批改，請先從 PythonAnywhere 下載或分享相關檔案，然後貼上／告訴助手。暫時直接把學生作品上載到 PA 的 upload inbox，再由老師使用網站的 teacher marking/save UI 批改即可。

## 常見檢查

- 顯示 `ModuleNotFoundError`：確認 Source code、Working directory 及 WSGI 中的 `/home/USERNAME/essay-marker` 完全一致，並確認 virtualenv 已安裝 `requirements.txt`。
- CSS 沒有載入：檢查 Static files 的 `/static/` 對應至 `/home/USERNAME/essay-marker/static/`，然後 Reload。
- 修改程式、WSGI 或環境變數後，都要在 Web tab 按 Reload。

### Short English checklist

Create a free Beginner account, upload/clone the project to `/home/USERNAME/essay-marker`, create a virtualenv with the highest available Python 3.x, and run `pip install -r requirements.txt`. In **Web → Add a new web app**, choose **Manual configuration**, set source and working directory to the project path, set the virtualenv path, paste the WSGI snippet, set `FLASK_SECRET_KEY`, and Reload. SQLite and uploads persist on PythonAnywhere's filesystem, but free CPU quotas and the `pythonanywhere.com` subdomain apply.
