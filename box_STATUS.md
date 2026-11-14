# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-15 04:16:09`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **31** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **33** | **32** | **1** | **31** | **0** | `97.0%` | **521.1 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**11** 站 (34.4%)
- 🟡 **良好** (`300 ~ 600ms`)：**11** 站 (34.4%)
- 🟠 **普通** (`600 ~ 1000ms`)：**8** 站 (25.0%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**2** 站 (6.2%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **83.6** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `百度云 | 采集` | **181.6** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 3 | `红牛 | 采集` | **189.6** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 4 | `无尽 | 采集` | **189.9** | 🟢 極速 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 5 | `ikun | 采集` | **201.6** | 🟢 極速 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 6 | `芒果 | 采集` | **225.4** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 7 | `天涯 | 采集` | **239.4** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 8 | `豪华 | 采集` | **253.7** | 🟢 極速 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 9 | `鸭鸭 | 采集` | **267.5** | 🟢 極速 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 10 | `索尼 | 采集` | **286.7** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 11 | `牛牛 | 采集` | **293.3** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 12 | `樱花 | 采集` | **312.9** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 13 | `极速 | 采集` | **363.8** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 14 | `暴風 | 采集` | **368.2** | 🟡 良好 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 15 | `魔都 | 采集` | **408.3** | 🟡 良好 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 16 | `速播 | 采集` | **423.4** | 🟡 良好 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 17 | `虎牙 | 采集` | **465.4** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 18 | `金鹰 | 采集` | **467.4** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 19 | `光速 | 采集` | **500.4** | 🟡 良好 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 20 | `新浪 | 采集` | **504.5** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 21 | `优质 | 采集` | **522.2** | 🟡 良好 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 22 | `厂长 | 采集` | **567.8** | 🟡 良好 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 23 | `艾旦 | 采集` | **687.4** | 🟠 普通 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 24 | `最大 | 采集` | **702.1** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 25 | `量子 | 采集` | **793.5** | 🟠 普通 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 26 | `360 | 采集` | **834.0** | 🟠 普通 | `code:1 (成功)` | `https://360zy.com/api.php/provide/vod/` |
| 27 | `非凡 | 采集` | **834.1** | 🟠 普通 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 28 | `爱奇艺 | 采集` | **851.9** | 🟠 普通 | `code:1 (成功)` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |
| 29 | `巨量 | 采集` | **871.3** | 🟠 普通 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 30 | `母鸡 | 采集` | **993.3** | 🟠 普通 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 31 | `创享 | 采集` | **1025.0** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |
| 32 | `猫眼 | 采集` | **1767.4** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |

---

### ⚠️ 本次移入 NG 項目 (共 1 筆)
> 📦 **封存檔案**：`collect/NG/box1_ng_20261115_041635.json`

| 站點名稱 | 移入原因 | 網址預覽 |
| :--- | :--- | :--- |
| `ok | 采集` | `連線逾時 (Timeout)` | `https://api.okzyw.net/api.php/provide/vod/` |
