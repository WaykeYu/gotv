# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-14 05:45:38`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **31** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **34** | **32** | **2** | **31** | **0** | `94.1%` | **502.8 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**10** 站 (31.2%)
- 🟡 **良好** (`300 ~ 600ms`)：**11** 站 (34.4%)
- 🟠 **普通** (`600 ~ 1000ms`)：**10** 站 (31.2%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**1** 站 (3.1%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **112.4** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `红牛 | 采集` | **192.1** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 3 | `ok | 采集` | **214.8** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 4 | `鸭鸭 | 采集` | **217.6** | 🟢 極速 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 5 | `无尽 | 采集` | **225.3** | 🟢 極速 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 6 | `百度云 | 采集` | **233.1** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 7 | `天涯 | 采集` | **266.7** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 8 | `索尼 | 采集` | **267.7** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 9 | `豪华 | 采集` | **283.7** | 🟢 極速 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 10 | `芒果 | 采集` | **299.6** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 11 | `ikun | 采集` | **328.8** | 🟡 良好 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 12 | `厂长 | 采集` | **339.7** | 🟡 良好 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 13 | `暴風 | 采集` | **347.3** | 🟡 良好 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 14 | `樱花 | 采集` | **379.1** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 15 | `牛牛 | 采集` | **381.4** | 🟡 良好 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 16 | `魔都 | 采集` | **402.3** | 🟡 良好 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 17 | `极速 | 采集` | **426.0** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 18 | `金鹰 | 采集` | **452.4** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 19 | `虎牙 | 采集` | **494.9** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 20 | `速播 | 采集` | **495.5** | 🟡 良好 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 21 | `新浪 | 采集` | **514.1** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 22 | `猫眼 | 采集` | **607.9** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 23 | `光速 | 采集` | **625.1** | 🟠 普通 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 24 | `艾旦 | 采集` | **695.9** | 🟠 普通 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 25 | `优质 | 采集` | **724.1** | 🟠 普通 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 26 | `360 | 采集` | **769.6** | 🟠 普通 | `code:1 (成功)` | `https://360zy.com/api.php/provide/vod/` |
| 27 | `非凡 | 采集` | **801.1** | 🟠 普通 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 28 | `爱奇艺 | 采集` | **860.9** | 🟠 普通 | `code:1 (成功)` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |
| 29 | `母鸡 | 采集` | **872.4** | 🟠 普通 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 30 | `量子 | 采集` | **898.8** | 🟠 普通 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 31 | `巨量 | 采集` | **990.8** | 🟠 普通 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 32 | `创享 | 采集` | **1369.1** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |

---

### ⚠️ 本次移入 NG 項目 (共 2 筆)
> 📦 **封存檔案**：`collect/NG/box1_ng_20261114_054604.json`

| 站點名稱 | 移入原因 | 網址預覽 |
| :--- | :--- | :--- |
| `快车 | 采集` | `連線逾時 (Timeout)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| `最大 | 采集` | `連線逾時 (Timeout)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam3u8/` |
