name: Check Spiders & JS Health

on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:
  push:
    paths:
      - 'py/**.py'
      - 'js/**'

jobs:
  check:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests bs4 lxml pycryptodome urllib3

      - name: Run Unified Health Checker
        run: |
          python - << 'EOF'
          import os
          import sys
          import re
          import importlib.util
          import inspect
          import requests
          from concurrent.futures import ThreadPoolExecutor, as_completed
          from datetime import datetime

          BASE_DIR = os.getcwd()
          PY_DIR = os.path.join(BASE_DIR, "py")
          JS_DIR = os.path.join(BASE_DIR, "js")
          REPORT_FILE = os.path.join(BASE_DIR, "SPIDER_STATUS.md")
          TIMEOUT = 10
          MAX_WORKERS = 10

          def extract_urls(code: str) -> list:
              """精確匹配 Python 與 JS 常見的站點宣告語法"""
              patterns = [
                  r'''(?:host|site|siteUrl|baseUrl|url|WEB_SITE)\s*[:=]\s*['"](https?://[^'"]+)['"]''',
                  r'''['"](https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?)['"]'''
              ]
              urls = []
              # 排除內部常見非目標網址
              skip_hosts = ["github.com", "googlevideo", "w3.org", "schema.org", "jsdelivr.net", "baidu.com", "qq.com", "unpkg.com"]
              for pat in patterns:
                  found = re.findall(pat, code, re.IGNORECASE)
                  for u in found:
                      if not any(skip in u for skip in skip_hosts) and u not in urls:
                          urls.append(u)
              return urls

          def test_url_alive(url: str) -> tuple:
              try:
                  headers = {
                      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                      "Referer": url
                  }
                  resp = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
                  if resp.status_code >= 400:
                      resp = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True)
                  if resp.status_code < 400:
                      return True, f"HTTP {resp.status_code}"
                  return False, f"HTTP {resp.status_code}"
              except Exception as e:
                  return False, str(e)[:35]

          def check_spider_file(file_info: tuple) -> dict:
              file_type, rel_path, full_path = file_info
              start_time = datetime.now()
              result = {
                  "type": file_type,
                  "file": rel_path,
                  "status": "❌ 異常",
                  "detail": "未知錯誤",
                  "latency_ms": 0
              }

              # 讀取檔案內容
              try:
                  with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                      code = f.read()
              except Exception as e:
                  result["detail"] = f"無法讀取: {str(e)[:30]}"
                  return result

              # 1. 若為 Python 腳本，優先嘗試動態執行模組介面
              if file_type == "Python":
                  filename = os.path.basename(full_path)
                  try:
                      mod_name = f"mod_{os.path.splitext(filename)[0]}"
                      spec = importlib.util.spec_from_file_location(mod_name, full_path)
                      module = importlib.util.module_from_spec(spec)
                      sys.modules[mod_name] = module
                      spec.loader.exec_module(module)

                      spider = None
                      for attr in dir(module):
                          obj = getattr(module, attr)
                          if inspect.isclass(obj) and obj.__module__ == module.__name__:
                              if "Spider" in attr or hasattr(obj, "homeContent"):
                                  spider = obj()
                                  break

                      if spider:
                          if hasattr(spider, "init"):
                              try: spider.init()
                              except Exception: pass
                          if hasattr(spider, "homeContent"):
                              res = spider.homeContent(True)
                              if res and isinstance(res, (dict, list, str)):
                                  cost = int((datetime.now() - start_time).total_seconds() * 1000)
                                  return {**result, "status": "✅ 正常", "detail": "homeContent 響應成功", "latency_ms": cost}
                  except Exception:
                      pass

              # 2. 靜態提取 URL 連線測試（適用 JS 腳本與動態執行受限的 Python）
              urls = extract_urls(code)
              if urls:
                  target_url = urls[0]
                  alive, msg = test_url_alive(target_url)
                  cost = int((datetime.now() - start_time).total_seconds() * 1000)
                  if alive:
                      result["status"] = "✅ 正常" if file_type == "JS" else "⚠️ 站點存活(載入受限)"
                      result["detail"] = f"站點可連線 ({msg}): {target_url}"
                  else:
                      result["status"] = "❌ 失效"
                      result["detail"] = f"連線失敗 ({msg}): {target_url}"
                  result["latency_ms"] = cost
              else:
                  result["detail"] = "未偵測到有效網站 URL"

              return result

          # 收集所有檔案清單
          target_files = []

          # py/ 目錄掃描
          if os.path.exists(PY_DIR):
              for root, _, files in os.walk(PY_DIR):
                  for f in files:
                      if f.endswith(".py") and not f.startswith("__"):
                          full = os.path.join(root, f)
                          target_files.append(("Python", os.path.relpath(full, BASE_DIR), full))

          # js/ 目錄與所有子資料夾掃描
          if os.path.exists(JS_DIR):
              for root, _, files in os.walk(JS_DIR):
                  for f in files:
                      if f.endswith(".js"):
                          full = os.path.join(root, f)
                          target_files.append(("JS", os.path.relpath(full, BASE_DIR), full))

          if not target_files:
              print("未找到任何 py 或 js 檔案，結束檢測。")
              sys.exit(0)

          print(f"共發現 {len(target_files)} 個目標腳本，開始並行檢測...")
          results = []
          with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
              future_map = {executor.submit(check_spider_file, item): item for item in target_files}
              for future in as_completed(future_map):
                  r = future.result()
                  results.append(r)
                  print(f"[{r['type']}][{r['status']}] {r['file']} -> {r['detail']}")

          # 依類型與狀態排序
          results.sort(key=lambda x: (x["type"], x["status"], x["file"]))

          # 數據統計
          def calc_stats(sub_list):
              total = len(sub_list)
              ok = sum(1 for r in sub_list if "✅" in r["status"])
              warn = sum(1 for r in sub_list if "⚠️" in r["status"])
              fail = sum(1 for r in sub_list if "❌" in r["status"])
              rate = round(((ok + warn) / total * 100), 2) if total > 0 else 0
              return total, ok, warn, fail, rate

          tot_all, ok_all, warn_all, fail_all, rate_all = calc_stats(results)
          py_stats = calc_stats([r for r in results if r["type"] == "Python"])
          js_stats = calc_stats([r for r in results if r["type"] == "JS"])

          now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
          md = [
              "# 🕷️ 影音網站爬蟲 (PY & JS) 有效性檢測報告\n",
              f"> **檢測時間**：`{now_str}`  \n",
              f"> **總體概況**：共檢測 **{tot_all}** 個檔案 ｜ ✅ 正常：**{ok_all}** ｜ ⚠️ 警告：**{warn_all}** ｜ ❌ 失效：**{fail_all}** ｜ **總可用率：{rate_all}%**\n",
              "### 📊 分類統計\n",
              f"- **Python (`py/`)**：共 **{py_stats[0]}** 個 ｜ 可用 **{py_stats[1] + py_stats[2]}** ｜ 失效 **{py_stats[3]}** ｜ 可用率 **{py_stats[4]}%**",
              f"- **JavaScript (`js/`)**：共 **{js_stats[0]}** 個 ｜ 可用 **{js_stats[1] + js_stats[2]}** ｜ 失效 **{js_stats[3]}** ｜ 可用率 **{js_stats[4]}%**\n",
              "### 📝 詳細檢測結果\n",
              "| 類型 | 檔案路徑 | 狀態 | 耗時 (ms) | 檢測資訊 |",
              "| :---: | :--- | :---: | :---: | :--- |"
          ]

          for r in results:
              md.append(f"| {r['type']} | `{r['file']}` | {r['status']} | {r['latency_ms']} | {r['detail']} |")

          with open(REPORT_FILE, "w", encoding="utf-8") as f:
              f.write("\n".join(md))
          EOF

      - name: Commit & Push Report
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add SPIDER_STATUS.md
          if git diff --staged --quiet; then
            echo "報告無任何變動，跳過提交。"
          else
            git commit -m "chore(auto): 更新 py 及 js 影音網站有效性報告 [skip ci]"
            git push
          fi
