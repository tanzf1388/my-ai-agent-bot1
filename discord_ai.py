import os
import re
import ast
import json
import sys
import textwrap
import base64
import asyncio
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import urlparse

import discord
from discord.ext import commands, tasks
import requests
from bs4 import BeautifulSoup
import yfinance as yf
from ddgs import DDGS

from rapidocr_onnxruntime import RapidOCR
from pydantic import BaseModel, Field

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain.tools import tool
from langchain_community.tools import WikipediaQueryRun
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama

# 初始化本機 RapidOCR 引擎
ocr_engine = RapidOCR()

# ===========================================================================
# 📁 全域預設路徑、設定持久化與中文字型自動註冊
# ===========================================================================
PDF_OUTPUT_DIR = os.path.abspath("./generated_pdfs")
DOCS_REF_DIR = os.path.abspath("./reference_docs")
CONFIG_FILE = os.path.abspath("./config.json")

os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)
os.makedirs(DOCS_REF_DIR, exist_ok=True)

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_model": "qwen3.5:9b"}

def save_config(data: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"儲存設定檔失敗 {e}")

sys_config = load_config()
active_model_name = sys_config.get("current_model", "qwen3.5:9b")

PDF_FONT_NAME = "Helvetica"
possible_fonts = [
    ("MSJH", "C:/Windows/Fonts/msjh.ttc", 0),
    ("MSJH", "C:/Windows/Fonts/msjh.ttf", None),
    ("KAIU", "C:/Windows/Fonts/kaiu.ttf", None),
]

for item in possible_fonts:
    font_alias, font_path, sub_idx = item[0], item[1], item[2]
    if os.path.exists(font_path):
        try:
            if sub_idx is not None:
                pdfmetrics.registerFont(TTFont(font_alias, font_path, subfontIndex=sub_idx))
            else:
                pdfmetrics.registerFont(TTFont(font_alias, font_path))
            PDF_FONT_NAME = font_alias
            break
        except Exception:
            pass

# ---------------------------------------------------------------------------
# 1. Token 與權限設定
# ---------------------------------------------------------------------------
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise RuntimeError("找不到 DISCORD_TOKEN 環境變數 請先設定 $env:DISCORD_TOKEN")

ENABLE_USER_WHITELIST = False
ALLOWED_USER_IDS = {1533017055736107045}

# ---------------------------------------------------------------------------
# 2. 對話記憶庫 (Memory) & 自動清理
# ---------------------------------------------------------------------------
MAX_HISTORY_LEN = 30
channel_memories = defaultdict(list)

def clean_old_memories(channel_id: int = None):
    cutoff_date = datetime.now() - timedelta(days=150)
    if channel_id is not None:
        channel_memories[channel_id] = [
            item for item in channel_memories[channel_id]
            if item[0] >= cutoff_date
        ]
    else:
        for cid in list(channel_memories.keys()):
            channel_memories[cid] = [
                item for item in channel_memories[cid]
                if item[0] >= cutoff_date
            ]
            if not channel_memories[cid]:
                del channel_memories[cid]

def format_chat_history(channel_id: int) -> str:
    clean_old_memories(channel_id)
    history = channel_memories[channel_id]
    if not history:
        return "無歷史對話"
    formatted = []
    for timestamp, user_msg, ai_msg in history:
        time_str = timestamp.strftime("%Y-%m-%d %H:%M")
        formatted.append(f"[{time_str}] User: {user_msg}\nAI: {ai_msg}")
    return "\n---\n".join(formatted)

def add_chat_history(channel_id: int, user_msg: str, ai_msg: str):
    now = datetime.now()
    channel_memories[channel_id].append((now, user_msg, ai_msg))
    clean_old_memories(channel_id)
    if len(channel_memories[channel_id]) > MAX_HISTORY_LEN:
        channel_memories[channel_id].pop(0)

# ---------------------------------------------------------------------------
# 3. Pydantic 工具參數 Schema
# ---------------------------------------------------------------------------
class PDFInputSchema(BaseModel):
    filename: str = Field(default="report.pdf", description="PDF 檔案名稱 例如 report.pdf")
    title: str = Field(default="分析報告", description="PDF 文件標題")
    content: str = Field(default="", description="PDF 完整內文資料")
    category: str = Field(default="一般", description="文件分類資料夾名稱 例如 物理 數學 股票 等")
    output_dir: str = Field(default="", description="指定儲存 PDF 的自訂目標資料夾路徑")

class TXTInputSchema(BaseModel):
    filename: str = Field(default="output.txt", description="TXT 檔案名稱 例如 note.txt")
    content: str = Field(default="", description="TXT 檔案的文字內容")
    category: str = Field(default="一般", description="文件分類資料夾名稱 例如 物理 數學 股票 等")
    output_dir: str = Field(default="", description="指定儲存 TXT 的自訂目標資料夾路徑")

class DocsInputSchema(BaseModel):
    query: str = Field(default="all", description="欲檢索比對之學科主題或關鍵字 例如 物理 微積分 數學 英文 等")
    folder_path: str = Field(default="", description="指定資料夾路徑或名稱 預設留空即可全文與 OCR 檢索參考資料庫")

class StockInputSchema(BaseModel):
    ticker: str = Field(description="股票代碼")

class WebSearchSchema(BaseModel):
    query: str = Field(description="搜尋關鍵字")

class WebFetchSchema(BaseModel):
    url: str = Field(description="目標網頁 URL")

class UpgradeModelSchema(BaseModel):
    model_name: str = Field(default="qwen3.5:9b", description="欲拉取與切換的 Ollama 模型名稱 例如 qwen3.5:14b 或 llama3:latest")

class SelfUpdateSchema(BaseModel):
    confirm: bool = Field(default=True, description="確認執行程式碼 Git 拉取更新與自動重啟")

class DeleteModelSchema(BaseModel):
    model_name: str = Field(default="all", description="欲刪除的模型名稱；若輸入 all 則清理除了當前運作模型外的所有模型")

# ---------------------------------------------------------------------------
# 4. Helper 工具函數
# ---------------------------------------------------------------------------
def sanitize_filename(filename: str) -> str:
    clean = str(filename).strip().strip("'\"")
    clean = os.path.basename(clean)
    clean = re.sub(r'[\\/*?:"<>|\r\n]', "", clean)
    return clean if clean else "report.pdf"

def sanitize_category(category: str) -> str:
    clean = str(category).strip().strip("'\"")
    clean = re.sub(r'[\\/*?:"<>|\r\n]', "", clean)
    return clean if clean else "一般"

def parse_raw_json_input(raw_input: str) -> dict:
    if not isinstance(raw_input, str):
        return {}
    s = raw_input.strip()
    s = re.sub(r'^```json\s*', '', s)
    s = re.sub(r'^```\s*', '', s)
    s = re.sub(r'\s*```$', '', s)
    try:
        res = json.loads(s)
        if isinstance(res, dict):
            return res
    except Exception:
        pass
    try:
        res = ast.literal_eval(s)
        if isinstance(res, dict):
            return res
    except Exception:
        pass
    return {}

def is_safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.hostname or "").lower()
        blocked_hosts = ("localhost", "127.0.0.1", "0.0.0.0", "::1")
        if host in blocked_hosts or host.startswith("192.168.") or host.startswith("10.") or host.startswith("172."):
            return False
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# 5. Agent 工具庫 (Tools)
# ---------------------------------------------------------------------------
@tool("upgrade_ai_model", args_schema=UpgradeModelSchema)
def upgrade_ai_model(model_name: str = "qwen3.5:9b") -> str:
    """下載、升級並持久化熱切換本機 Ollama LLM 模型"""
    global llm_text, agent, agent_executor
    clean_model = model_name.strip().lower()
    
    try:
        process = subprocess.run(
            ["ollama", "pull", clean_model],
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if process.returncode != 0:
            return f"下載模型 {clean_model} 失敗 錯誤資訊 {process.stderr}"

        llm_text.model = clean_model
        save_config({"current_model": clean_model})
        
        agent = create_react_agent(llm_text, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=25,
        )
        
        return f"模型已成功下載並熱切換為【{clean_model}】設定已永久保存 下次重啟將繼續使用此模型"
    
    except Exception as e:
        return f"升級模型時發生錯誤 {str(e)}"

@tool("delete_ollama_model", args_schema=DeleteModelSchema)
def delete_ollama_model(model_name: str = "all") -> str:
    """刪除指定或所有未使用的 Ollama 本機模型以釋放硬碟容量"""
    global llm_text
    current_running = getattr(llm_text, "model", "").lower()
    
    try:
        list_res = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=30)
        if list_res.returncode != 0:
            return f"無法取得模型列表 {list_res.stderr}"

        lines = [line.strip() for line in list_res.stdout.splitlines() if line.strip()]
        if len(lines) <= 1:
            return "目前本機沒有任何已下載的模型"

        downloaded_models = []
        for line in lines[1:]:
            parts = line.split()
            if parts:
                downloaded_models.append(parts[0])

        target = model_name.strip().lower()
        deleted_count = 0
        skipped = []

        for m in downloaded_models:
            if m.lower() == current_running:
                skipped.append(m)
                continue

            if target == "all" or target == m.lower():
                rm_res = subprocess.run(["ollama", "rm", m], capture_output=True, text=True, timeout=60)
                if rm_res.returncode == 0:
                    deleted_count += 1

        msg = f"清理完成 共刪除 {deleted_count} 個模型"
        if skipped:
            msg += f"（已保留當前運行中的模型 {', '.join(skipped)}）"
        return msg

    except Exception as e:
        return f"清理模型時發生錯誤 {str(e)}"

@tool("self_update_codebase", args_schema=SelfUpdateSchema)
def self_update_codebase(confirm: bool = True) -> str:
    """從 Git 遠端倉庫拉取最新的程式碼並重啟 Bot"""
    if not confirm:
        return "已取消自我更新"
        
    try:
        git_res = subprocess.run(["git", "pull"], capture_output=True, text=True, timeout=30)
        if git_res.returncode != 0:
            return f"Git 更新失敗 {git_res.stderr}"

        output_msg = f"程式碼拉取成功\n{git_res.stdout}\n系統即將自動重啟"
        asyncio.get_event_loop().call_later(2, lambda: os.execv(sys.executable, [sys.executable] + sys.argv))
        return output_msg
        
    except Exception as e:
        return f"自我更新過程發生錯誤 {str(e)}"

@tool("get_stock_data", args_schema=StockInputSchema)
def get_stock_data(ticker: str) -> str:
    """查詢指定股票代碼的實時股價與當日行情"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info
        last_price = info.last_price
        previous_close = info.previous_close
        change_pct = ((last_price - previous_close) / previous_close) * 100
        return (f"股票數據 {ticker}\n"
                f"當前價格 {last_price:.2f}\n"
                f"昨日收盤 {previous_close:.2f}\n"
                f"當日漲跌 {change_pct:+.2f}%\n"
                f"資料來源 Yahoo Finance\n")
    except Exception as e:
        return f"無法取得股票 {ticker} 的資料 {str(e)}"

@tool("web_search", args_schema=WebSearchSchema)
def web_search(query: str) -> str:
    """用於在網路上搜尋最新的新聞 股市盤勢 時事 補充資訊或外部資料"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, timelimit='d', max_results=5))
            if not results:
                return "未找到搜尋結果"
            output = []
            for r in results:
                output.append(f"標題 {r.get('title')}\n內容 {r.get('body')}\n網址 {r.get('href')}\n")
            return "\n".join(output)
    except Exception as e:
        return f"搜尋時發生錯誤 {str(e)}"

@tool("fetch_webpage_content", args_schema=WebFetchSchema)
def fetch_webpage_content(url: str) -> str:
    """讀取公開網址 URL 的內文內容"""
    if not is_safe_url(url):
        return "錯誤 不允許存取不安全的網址或內網位址"

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
        text = soup.get_text(separator='\n')
        lines = (line.strip() for line in text.splitlines())
        clean_text = '\n'.join(chunk for chunk in lines if chunk)
        return f"來源網址 {url}\n" + (clean_text[:1200] if len(clean_text) > 1200 else clean_text)
    except Exception as e:
        return f"無法讀取該網頁 {str(e)}"

@tool("generate_pdf_report", args_schema=PDFInputSchema)
def generate_pdf_report(filename: str = "report.pdf", title: str = "分析報告", content: str = "", category: str = "一般", output_dir: str = "") -> str:
    """生成 PDF 檔案並依據 category 自動分類儲存至對應資料夾"""
    parsed = parse_raw_json_input(filename)
    if parsed:
        filename = parsed.get("filename", filename)
        title = parsed.get("title", title)
        content = parsed.get("content", content)
        category = parsed.get("category", category)
        output_dir = parsed.get("output_dir", output_dir)

    clean_name = sanitize_filename(str(filename))
    if not clean_name.lower().endswith(".pdf"):
        clean_name += ".pdf"

    cat_folder = sanitize_category(category)
    if output_dir and str(output_dir).strip():
        target_dir = os.path.abspath(str(output_dir).strip())
    else:
        target_dir = os.path.join(PDF_OUTPUT_DIR, cat_folder)

    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        return f"無法建立目標資料夾 {target_dir} {str(e)}"

    file_path = os.path.join(target_dir, clean_name)
    try:
        c = canvas.Canvas(file_path, pagesize=letter)
        _, height = letter
        c.setFont(PDF_FONT_NAME, 16)
        c.drawString(50, height - 50, str(title or "分析報告"))
        c.setFont(PDF_FONT_NAME, 10)
        y_position = height - 80

        raw_content = str(content or "無內文資料")
        lines = raw_content.split("\n")

        for line in lines:
            wrapped_lines = textwrap.wrap(line, width=45) if line.strip() else [""]
            for w_line in wrapped_lines:
                if y_position < 50:
                    c.showPage()
                    c.setFont(PDF_FONT_NAME, 10)
                    y_position = height - 50
                c.drawString(50, y_position, w_line)
                y_position -= 15

        c.save()
        return f"PDF 成功生成並儲存於 {file_path}"
    except Exception as e:
        return f"生成 PDF 失敗 {str(e)}"

@tool("generate_txt_file", args_schema=TXTInputSchema)
def generate_txt_file(filename: str = "output.txt", content: str = "", category: str = "一般", output_dir: str = "") -> str:
    """生成純文字 .txt 檔案並依據 category 自動分類儲存至對應資料夾"""
    parsed = parse_raw_json_input(filename)
    if parsed:
        filename = parsed.get("filename", filename)
        content = parsed.get("content", content)
        category = parsed.get("category", category)
        output_dir = parsed.get("output_dir", output_dir)

    clean_name = sanitize_filename(str(filename))
    if not clean_name.lower().endswith(".txt"):
        clean_name += ".txt"

    cat_folder = sanitize_category(category)
    if output_dir and str(output_dir).strip():
        target_dir = os.path.abspath(str(output_dir).strip())
    else:
        target_dir = os.path.join(PDF_OUTPUT_DIR, cat_folder)

    try:
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, clean_name)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(content))
        return f"TXT 成功生成並儲存於 {file_path}"
    except Exception as e:
        return f"生成 TXT 失敗 {str(e)}"

@tool("read_local_reference_docs", args_schema=DocsInputSchema)
def read_local_reference_docs(query: str = "all", folder_path: str = "") -> str:
    """通用調閱工具 自動比對並進入任意學科/分類子資料夾 深度遞迴讀取所有照片與檔案內容"""
    parsed = parse_raw_json_input(query)
    if parsed:
        query = parsed.get("query", query)
        folder_path = parsed.get("folder_path", folder_path)

    raw_query = str(query).strip()
    raw_fp = str(folder_path).strip()

    if len(raw_fp) > 50:
        raw_fp = ""

    candidates = []
    for raw in [raw_fp, raw_query]:
        clean = re.sub(r'[^\w\u4e00-\u9fa5]', '', raw)
        if clean and clean.lower() != "all":
            candidates.append(clean)

    target_dir = None
    is_specific_subfolder = False
    base_search_dirs = [os.path.abspath(DOCS_REF_DIR), os.path.abspath(PDF_OUTPUT_DIR)]

    for base_dir in base_search_dirs:
        if not os.path.exists(base_dir):
            continue
        
        existing_subdirs = [
            d for d in os.listdir(base_dir) 
            if os.path.isdir(os.path.join(base_dir, d))
        ]

        for cand in candidates:
            direct_path = os.path.join(base_dir, cand)
            if os.path.exists(direct_path) and os.path.isdir(direct_path):
                target_dir = direct_path
                is_specific_subfolder = True
                break

            for sub_name in existing_subdirs:
                if cand.lower() in sub_name.lower() or sub_name.lower() in cand.lower():
                    target_dir = os.path.join(base_dir, sub_name)
                    is_specific_subfolder = True
                    break
            if target_dir:
                break
        if target_dir:
            break

    if not target_dir:
        target_dir = os.path.abspath(DOCS_REF_DIR)

    inspected_files_count = 0
    matched_contents = []

    for root, dirs, files in os.walk(target_dir):
        for file_name in files:
            ext = os.path.splitext(file_name)[1].lower()
            allowed_exts = ['.txt', '.md', '.pdf', '.jpg', '.jpeg', '.png', '.webp']
            if ext not in allowed_exts:
                continue

            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, start=os.getcwd())
            text_content = ""

            try:
                if ext in ['.txt', '.md']:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        text_content = f.read()
                elif ext == '.pdf':
                    reader = PdfReader(full_path)
                    for page in reader.pages:
                        text_content += page.extract_text() or ""
                elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
                    ocr_result, _ = ocr_engine(full_path)
                    if ocr_result:
                        text_content = "\n".join([line[1] for line in ocr_result])

                inspected_files_count += 1

                is_matched = False
                if is_specific_subfolder or not candidates:
                    is_matched = True
                else:
                    for cand in candidates:
                        if (cand.lower() in file_name.lower()) or (cand.lower() in full_path.lower()) or (cand.lower() in text_content.lower()):
                            is_matched = True
                            break

                if is_matched:
                    snippet = text_content[:1200] if text_content.strip() else "照片或檔案無辨識出清晰文字內容"
                    matched_contents.append(
                        f"📄 檔案相對路徑 {rel_path}\n"
                        f"📍 完整本機路徑 {full_path}\n"
                        f"內文與 OCR 辨識結果\n{snippet}"
                    )
            except Exception:
                continue

    if inspected_files_count == 0:
        return f"已檢索資料夾 {target_dir} 但未找到任何相關檔案或圖片"

    dir_name = os.path.basename(target_dir)
    return (
        f"已成功調閱【{dir_name}】資料夾內共 {inspected_files_count} 個檔案與照片 OCR 內容\n"
        f"資料內容如下\n\n" + "\n---\n".join(matched_contents)
    )

api_wrapper = WikipediaAPIWrapper(top_k_results=2, doc_content_chars_max=1000)
wikipedia_tool = WikipediaQueryRun(api_wrapper=api_wrapper)

tools = [
    get_stock_data,
    web_search,
    fetch_webpage_content,
    wikipedia_tool,
    generate_pdf_report,
    generate_txt_file,
    read_local_reference_docs,
    upgrade_ai_model,
    delete_ollama_model,
    self_update_codebase
]

# ---------------------------------------------------------------------------
# 6. Prompt 範本 (含防虛構與模型自我更新規約)
# ---------------------------------------------------------------------------
today_str = datetime.now().strftime("%Y年%m月%d日")

template = f"""Answer the following questions as best you can. Today's date is {today_str}.

You have access to the following tools:
{{tools}}

Use the following format strictly:
Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{{tool_names}}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question in Traditional Chinese.

RULES:
1. NEVER say "I don't have real-time data" or "I am an AI model".
2. STRICT REALITY CHECK: NEVER claim a PDF or TXT file is created in Final Answer UNLESS you actually called `generate_pdf_report` or `generate_txt_file` AND received a success Observation.
3. KNOWLEDGE INTEGRATION STRATEGY:
   - Step 1: ALWAYS call `read_local_reference_docs` FIRST to search internal files and subfolders.
   - Step 2: If user asks to generate PDFs or TXTs, you MUST execute `Action: generate_pdf_report` or `generate_txt_file` for EACH required file!
4. STRICT REACT FORMAT: Every `Thought:` line MUST be directly followed by either `Action:` + `Action Input:` OR `Final Answer:`.
5. MODEL UPGRADE & SELF UPDATE:
   - If user asks to upgrade or change model, call `upgrade_ai_model(model_name="...")`.
   - If user asks to delete unused models, call `delete_ollama_model(model_name="...")`.
   - If user asks to update codebase or self update, call `self_update_codebase()`.

[🚫 防虛構與強制工具執行規約]
- 嚴禁在沒有呼叫 `generate_pdf_report` 或未取得 Observation 成功結果前，宣稱 PDF 檔案已生成。
- 若使用者要求生成多份 PDF，你必須針對每一份 PDF 獨立呼叫一次 `generate_pdf_report`！

[🚫 極簡標點符號與排版規則 (STRICT PUNCTUATION RULES)]
- 嚴禁使用任何非必要的標點符號 包括全形冒號（：） 半形冒號（:） 句號（。） 逗號（，） 頓號（、） 中點（·） 括號（（）） 與雙引號。
- 嚴禁使用 Markdown 標題符號（# ##）與粗體符號（**）。
- 所有項目名稱 標題與內文之間 一律使用單一空格或換行進行分隔。
- 僅允許保留必要的數學運算符號（+ - * / = ^） 單位符號與小數點（.）。

[💡 測驗與連續提問模式協議 (QUIZ PROTOCOL)]
當使用者要求「測試我」、「連續提問」、「出題」、「根據程度詢問」時，你必須自動切換為【動態主考官】角色：
- 階段 1：呼叫 `read_local_reference_docs` 檢視檔案內文確認學科資料 接著在心中規劃題目 每次回覆只能丟出一道題目。
- 階段 2：對答與批改 判斷答案是否正確 錯誤時嚴禁進入下一題 必須詳細講解直到使用者表達理解。
- 階段 3：測驗結束後呼叫 `generate_txt_file` 生成報告檔案。

[🚫 DISCORD MATH FORMATTING (CRITICAL)]
Discord CANNOT render LaTeX markup. NEVER output LaTeX syntax or tags such as `\\frac`, `\\lim`, `\\to`, `\\neq`, `$`, or `$$`.
Always render mathematical equations using clear plain text and standard Unicode symbols:
- Fractions: Use `(a + b) / (c + d)` or `a / b`
- Limits: Use `lim (x -> 2)`
- Powers: Use `x^2`, `x^3`, or `x^n`
- Symbols: Use `->`, `!=`, `sqrt()`, `+/-`, `*`, `/`

Begin!

Conversation History:
{{chat_history}}

Question: {{input}}
Thought:{{agent_scratchpad}}"""

prompt = PromptTemplate.from_template(template)

# ---------------------------------------------------------------------------
# 7. 模型初始化 (根據 config.json 動態載入模型)
# ---------------------------------------------------------------------------
llm_text = ChatOllama(
    model=active_model_name,
    temperature=0,
    validate_model_on_init=True,
)

llm_vision = ChatOllama(
    model="llava",
    temperature=0,
    validate_model_on_init=True,
)

agent = create_react_agent(llm_text, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=25,
)

# ---------------------------------------------------------------------------
# 8. Discord Bot 事件處理
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@tasks.loop(hours=24)
async def auto_clean_memories_task():
    clean_old_memories()

@bot.event
async def on_ready():
    if not auto_clean_memories_task.is_running():
        auto_clean_memories_task.start()
    print(f"🤖 Qwen3.5 全功能 Bot 已上線 當前模型【{llm_text.model}】 帳號 {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if ENABLE_USER_WHITELIST and message.author.id not in ALLOWED_USER_IDS:
        return

    if bot.user.mentioned_in(message) or isinstance(message.channel, discord.DMChannel):
        clean_input = (
            message.content
            .replace(f"<@{bot.user.id}>", "")
            .replace(f"<@!{bot.user.id}>", "")
            .strip()
        )

        async with message.channel.typing():
            ocr_prefix = ""
            image_b64 = None
            if message.attachments:
                for att in message.attachments:
                    if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp']):
                        try:
                            img_bytes = await att.read()
                            image_b64 = base64.b64encode(img_bytes).decode('utf-8')

                            ocr_result, _ = ocr_engine(img_bytes)
                            if ocr_result:
                                extracted_text = "\n".join([line[1] for line in ocr_result])
                                ocr_prefix = f"圖片辨識出的文字內容\n{extracted_text}\n\n"
                            break
                        except Exception as e:
                            ocr_prefix = f"圖片 OCR 辨識失敗 {str(e)}\n\n"

            if image_b64 and not ocr_prefix.strip():
                try:
                    vision_prompt = clean_input if clean_input else "請詳細分析並描述這張圖片的畫面內容與細節"
                    v_msg = HumanMessage(content=[
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"}
                    ])
                    v_res = await asyncio.to_thread(llm_vision.invoke, [v_msg])
                    answer = v_res.content
                    add_chat_history(message.channel.id, f"[圖片分析] {clean_input}", answer)
                    await message.reply(answer)
                    return
                except Exception as e:
                    await message.reply(f"視覺模型分析失敗 {str(e)}")
                    return

            reply_context = ""
            if message.reference and message.reference.message_id:
                try:
                    ref_msg = await message.channel.fetch_message(message.reference.message_id)
                    reply_context = f"[正在回覆訊息 '{ref_msg.author.display_name}' {ref_msg.content}]\n"
                except Exception:
                    pass

            history_text = format_chat_history(message.channel.id)

            quiz_reminder = ""
            if any(kw in (history_text + clean_input) for kw in ["測試我", "連續詢問", "出題", "測驗"]):
                quiz_reminder = (
                    "\n[⚠️ 提醒 必須先調用 read_local_reference_docs 讀取並檢視檔案與照片 OCR 內文]"
                )

            full_user_input = f"{reply_context}{ocr_prefix}{clean_input if clean_input else '請整理並解答圖片中的問題'}{quiz_reminder}"

            try:
                res = await asyncio.to_thread(
                    agent_executor.invoke,
                    {
                        "input": full_user_input,
                        "chat_history": history_text
                    }
                )

                answer = res.get("output", "抱歉 無法回應")
                add_chat_history(message.channel.id, clean_input or "[傳送了圖片]", answer)

                file_matches = re.findall(r'([A-Za-z]:\\[^\n\s]+\.(?:pdf|txt)|\./[^\n\s]+\.(?:pdf|txt))', answer)
                discord_files = []
                for fpath in set(file_matches):
                    clean_fp = fpath.strip().strip("'\"")
                    if os.path.exists(clean_fp):
                        discord_files.append(discord.File(clean_fp))

                if len(answer) > 2000:
                    chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
                    first = True
                    for chunk in chunks:
                        if first:
                            await message.reply(chunk, files=discord_files if first and discord_files else None)
                            first = False
                        else:
                            await message.channel.send(chunk)
                else:
                    await message.reply(answer, files=discord_files if discord_files else None)

            except Exception as e:
                await message.reply(f"處理訊息時發生錯誤 {str(e)}")

# ---------------------------------------------------------------------------
# 9. 啟動入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN, reconnect=True)