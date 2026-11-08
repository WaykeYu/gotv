# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-09 04:04:14`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **31** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **32** | **32** | **0** | **31** | **0** | `100.0%` | **578.6 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**11** 站 (34.4%)
- 🟡 **良好** (`300 ~ 600ms`)：**10** 站 (31.2%)
- 🟠 **普通** (`600 ~ 1000ms`)：**5** 站 (15.6%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**6** 站 (18.8%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **58.8** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `快车 | 采集` | **146.8** | 🟢 極速 | `code:1 (成功)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| 3 | `芒果 | 采集` | **162.1** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 4 | `天涯 | 采集` | **215.9** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 5 | `红牛 | 采集` | **216.1** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 6 | `百度云 | 采集` | **220.5** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 7 | `ok | 采集` | **228.6** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 8 | `牛牛 | 采集` | **255.9** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 9 | `无尽 | 采集` | **261.5** | 🟢 極速 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 10 | `索尼 | 采集` | **278.0** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 11 | `鸭鸭 | 采集` | **281.9** | 🟢 極速 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 12 | `樱花 | 采集` | **336.6** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 13 | `魔都 | 采集` | **347.4** | 🟡 良好 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 14 | `豪华 | 采集` | **374.4** | 🟡 良好 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 15 | `优质 | 采集` | **409.0** | 🟡 良好 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 16 | `光速 | 采集` | **418.0** | 🟡 良好 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 17 | `极速 | 采集` | **446.1** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 18 | `金鹰 | 采集` | **456.8** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 19 | `ikun | 采集` | **456.8** | 🟡 良好 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 20 | `新浪 | 采集` | **490.0** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 21 | `虎牙 | 采集` | **529.3** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 22 | `暴風 | 采集` | **626.6** | 🟠 普通 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 23 | `速播 | 采集` | **689.0** | 🟠 普通 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 24 | `最大 | 采集` | **696.5** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 25 | `猫眼 | 采集` | **714.8** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 26 | `非凡 | 采集` | **849.9** | 🟠 普通 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 27 | `艾旦 | 采集` | **1084.7** | 🔴 遲鈍 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 28 | `量子 | 采集` | **1085.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 29 | `厂长 | 采集` | **1157.0** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 30 | `母鸡 | 采集` | **1294.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 31 | `巨量 | 采集` | **1632.3** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 32 | `创享 | 采集` | **2096.0** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |
