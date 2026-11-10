# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-10 08:16:09`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **32** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **34** | **34** | **0** | **32** | **0** | `100.0%` | **909.6 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**9** 站 (26.5%)
- 🟡 **良好** (`300 ~ 600ms`)：**9** 站 (26.5%)
- 🟠 **普通** (`600 ~ 1000ms`)：**8** 站 (23.5%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**8** 站 (23.5%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **162.7** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `芒果 | 采集` | **211.8** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 3 | `魔都 | 采集` | **225.4** | 🟢 極速 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 4 | `红牛 | 采集` | **230.4** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 5 | `百度云 | 采集` | **267.3** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 6 | `牛牛 | 采集` | **268.8** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 7 | `索尼 | 采集` | **269.3** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 8 | `ok | 采集` | **279.4** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 9 | `天涯 | 采集` | **290.2** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 10 | `快车 | 采集` | **333.3** | 🟡 良好 | `code:1 (成功)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| 11 | `无尽 | 采集` | **346.4** | 🟡 良好 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 12 | `鸭鸭 | 采集` | **397.6** | 🟡 良好 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 13 | `优质 | 采集` | **407.0** | 🟡 良好 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 14 | `ikun | 采集` | **429.4** | 🟡 良好 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 15 | `豪华 | 采集` | **431.9** | 🟡 良好 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 16 | `极速 | 采集` | **499.1** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 17 | `樱花 | 采集` | **531.0** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 18 | `金鹰 | 采集` | **552.0** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 19 | `虎牙 | 采集` | **664.4** | 🟠 普通 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 20 | `光速 | 采集` | **676.3** | 🟠 普通 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 21 | `最大 | 采集` | **680.3** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 22 | `暴風 | 采集` | **695.2** | 🟠 普通 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 23 | `新浪 | 采集` | **722.8** | 🟠 普通 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 24 | `猫眼 | 采集` | **758.6** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 25 | `速播 | 采集` | **831.8** | 🟠 普通 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 26 | `艾旦 | 采集` | **964.5** | 🟠 普通 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 27 | `量子 | 采集` | **1024.9** | 🔴 遲鈍 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 28 | `360 | 采集` | **1106.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://360zy.com/api.php/provide/vod/` |
| 29 | `母鸡 | 采集` | **1216.9** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 30 | `非凡 | 采集` | **1266.3** | 🔴 遲鈍 | `403 (防護放行)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 31 | `巨量 | 采集` | **1417.3** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 32 | `爱奇艺 | 采集` | **1485.1** | 🔴 遲鈍 | `code:1 (成功)` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |
| 33 | `创享 | 采集` | **2238.4** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |
| 34 | `厂长 | 采集` | **9044.4** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
