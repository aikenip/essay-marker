# Auto-mark routine：英文 vs 中文

本站只係交卷匣；批改由老師嘅 Grok Bot 助手完成（唔喺網站呼叫付費 LLM API）。  
登入、憑證、撈 pending、下載圖片、寫回批改嘅流程**不變**；只係按 `subject` 揀評分標準同重寫語言。

API 欄位：`subject` 為 `english` 或 `chinese`（舊交卷缺欄位當 `english`）；`subject_label` 為「英文」／「中文」。

提示詞參考：`emarker/prompt.py` → `get_system_prompt(subject)`、`build_user_prompt(student_note, subject=...)`。

---

## 共用（兩科一樣）

- 登入／Teacher API key／`/api/pending`／下載題目＋作文圖／寫回 `marking_text`：流程不變。
- 批改輸出用 **zh-HK Markdown**。
- 必須有完整 **作文轉寫（Transcription）**；睇唔清用 `[?]`。
- 必須有完整 **建議重寫版**（全文重寫 entire essay），唔可以只改幾段。
- 大約 DSE Level（3／4／5／5*／5**）只係估計，唔扮官方分。
- 問題要用學生原文引用＋ before → after 改寫。

---

## `subject === "english"`（英文作文）

- 對應 HKDSE **English Language Paper 2（Writing）**。
- 題目欄／轉寫／例子／建議重寫版：**全部用英文**（批改說明用中文）。
- 分項：Content、Language、Organisation。
- 留意 task、audience、purpose、tone。
- 建議重寫版：完整一篇 polished English model essay。

---

## `subject === "chinese"`（中文作文）

- 對應 HKDSE **中國語文 寫作卷**（議論／抒情／記敘等常見文體）。
- 轉寫、引用、改寫例子、建議重寫版：**全部用中文**。
- 分項：內容、結構、文辭／表達、審題／文體要求。
- 留意切題、文體是否符合題目、取材同表達。
- 建議重寫版：完整一篇中文範文（全文）。

---

## 畀 routine 用嘅短提示（可直接貼入助手）

When auto-marking a submission from essay-marker:

1. Read `subject` from the API (`english` | `chinese`). Login/API flow is unchanged.
2. If **english**: use English DSE Paper 2 criteria (Content / Language / Organisation). Feedback commentary in zh-HK; transcription, quoted examples, and the full **建議重寫版** must be in **English** (entire essay rewrite required). Question text shown to the marker should be the full original English prompt.
3. If **chinese**: use Chinese DSE Writing criteria (內容、結構、文辭／表達、審題／文體要求). Commentary, transcription, quotes, and the full **建議重寫版** must be in **Chinese** (entire essay rewrite required).
4. Never skip transcription or the full rewrite section. Approximate DSE level only — do not claim official scores.
5. Prefer prompts from `emarker/prompt.py` via `build_user_prompt(note, subject=subject)`.
