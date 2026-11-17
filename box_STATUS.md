# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-18 07:16:11`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **30** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **33** | **31** | **2** | **30** | **0** | `93.9%` | **568.8 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**11** 站 (35.5%)
- 🟡 **良好** (`300 ~ 600ms`)：**9** 站 (29.0%)
- 🟠 **普通** (`600 ~ 1000ms`)：**7** 站 (22.6%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**4** 站 (12.9%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **121.3** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `芒果 | 采集` | **182.2** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 3 | `红牛 | 采集` | **210.4** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 4 | `百度云 | 采集` | **237.3** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 5 | `ikun | 采集` | **237.7** | 🟢 極速 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 6 | `樱花 | 采集` | **269.2** | 🟢 極速 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 7 | `ok | 采集` | **271.1** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 8 | `无尽 | 采集` | **286.0** | 🟢 極速 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 9 | `牛牛 | 采集` | **292.1** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 10 | `天涯 | 采集` | **292.5** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 11 | `极速 | 采集` | **293.2** | 🟢 極速 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 12 | `索尼 | 采集` | **342.2** | 🟡 良好 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 13 | `豪华 | 采集` | **344.3** | 🟡 良好 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 14 | `鸭鸭 | 采集` | **394.9** | 🟡 良好 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 15 | `暴風 | 采集` | **397.1** | 🟡 良好 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 16 | `金鹰 | 采集` | **490.7** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 17 | `虎牙 | 采集` | **515.6** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 18 | `魔都 | 采集` | **546.2** | 🟡 良好 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 19 | `光速 | 采集` | **548.1** | 🟡 良好 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 20 | `优质 | 采集` | **569.9** | 🟡 良好 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 21 | `厂长 | 采集` | **616.5** | 🟠 普通 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 22 | `速播 | 采集` | **625.1** | 🟠 普通 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 23 | `最大 | 采集` | **643.5** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 24 | `新浪 | 采集` | **669.5** | 🟠 普通 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 25 | `猫眼 | 采集` | **736.2** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 26 | `非凡 | 采集` | **855.3** | 🟠 普通 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 27 | `巨量 | 采集` | **993.6** | 🟠 普通 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 28 | `母鸡 | 采集` | **1175.5** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 29 | `量子 | 采集` | **1301.1** | 🔴 遲鈍 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 30 | `艾旦 | 采集` | **1461.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 31 | `创享 | 采集` | **1712.1** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |

---

### ⚠️ 本次移入 NG 項目 (共 2 筆)
> 📦 **封存檔案**：`collect/NG/box1_ng_20261118_071637.json`

| 站點名稱 | 移入原因 | 網址預覽 |
| :--- | :--- | :--- |
| `爱奇艺 | 采集` | `連線逾時 (Timeout)` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |
| `360 | 采集` | `連線逾時 (Timeout)` | `https://360zy.com/api.php/provide/vod/` |
