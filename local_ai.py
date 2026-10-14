"""把子任務交給本機 Ollama 模型：python local_ai.py "指示"（或從 stdin 讀入）。
會遵守 Bot 的 GPU 守護：GPU 暫停或 ComfyUI 生成中時不呼叫模型，回傳代碼 2。"""
import json
import os
import sys
import time

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def model() -> str:
    """Bot 自動挑選的模型（auto_model.txt）；找不到就用 Ollama 最大的已安裝模型。"""
    try:
        with open(os.path.join(BASE_DIR, "auto_model.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        tags = requests.get(f"{HOST}/api/tags", timeout=10).json().get("models", [])
        return max(tags, key=lambda m: m.get("size", 0))["name"]


def gpu_busy() -> str:
    try:
        with open(os.path.join(BASE_DIR, "gpu_state.json"), encoding="utf-8") as f:
            s = json.load(f)
    except (OSError, ValueError):
        return ""
    if time.time() - s.get("time", 0) > 60:   # Bot 沒在跑，沒有守護狀態可參考
        return ""
    if s.get("paused"):
        return f"GPU 暫停中（{s.get('reason', '')}）"
    return "ComfyUI 正在生成圖片/影片" if s.get("generating") else ""


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    prompt = " ".join(sys.argv[1:]) or sys.stdin.read()
    if not prompt.strip():
        sys.exit(__doc__)
    busy = gpu_busy()
    if busy:
        print(f"本機模型目前不可用：{busy}，請自行完成這個子任務。")
        sys.exit(2)
    r = requests.post(f"{HOST}/api/chat", timeout=600, json={
        "model": model(), "stream": False, "think": False,
        "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    print(r.json()["message"]["content"].strip())


if __name__ == "__main__":
    main()
