# liwanwen.com 接入 Google Search Console 和 GA4（操作步骤）

这些步骤需要用你自己的 Google 账号来操作。全部做完后，工具和案例文档才能引用**真实的收录与访问数据**。在拿到 Search Console 数据之前，案例里一律不写"排名提升"或"流量提升"。

前提：用浏览器打开 https://liwanwen.com 能正常显示网站。

---

## 一、Google Search Console（看收录、搜索展示、点击）

### 1. 添加资源
1. 打开 https://search.google.com/search-console ，用你的 Google 账号登录。
2. 点左上角的资源下拉框，选 **"添加资源"**。
3. 选左边的 **"网域（Domain）"**，输入 `liwanwen.com`（不加 https 和 www），然后点继续。
   - 选"网域"的好处是 `https`、`http`、`www` 三种网址的数据会合并到一起看。

### 2. 用 DNS 验证你是域名的所有者
Google 会给你一串 TXT 记录，格式是 `google-site-verification=xxxxxxxx`。你的 DNS 现在由 Netlify 管理，所以这条记录要加在 Netlify 里：
1. 打开 Netlify，进入 **DNS → liwanwen.com → Add new record**。
2. 按下面填写：
   - Record type：**TXT**
   - Name：`@`，或者留空，也就是主域名本身
   - Value：粘贴 Google 给的整串 `google-site-verification=…`
   - TTL：保持默认
3. 保存后回到 Search Console，点 **"验证"**。
   - 如果提示验证失败，等 10–60 分钟让 DNS 生效，再点一次"验证"。

### 3. 提交 sitemap
- 前提：网站上已经有 `https://liwanwen.com/sitemap.xml`。目前**还没有**这个文件，它在修改清单里，需要你确认后才会加上。
- Search Console 左侧菜单选 **"站点地图"**，输入 `sitemap.xml`，点 **"提交"**。

### 4. 请求收录首页（可选）
- 在顶部的"网址检查"栏输入 `https://liwanwen.com/`，然后点 **"请求编入索引"**。
- Google 不保证收录时间。新网站通常要几天到几周。

### 5. 之后去哪里看数据
| 想看什么 | 菜单位置 |
|---|---|
| 收录了几个页面、哪些没收录、为什么 | 编入索引 → 网页 |
| 搜索展示次数、点击次数、平均排名、搜索词 | 效果 → 搜索结果 |
| 手机体验、Core Web Vitals 真实用户数据 | 体验 → Core Web Vitals（流量太少时不会显示数据） |

**记录数据的方法**：在效果报告右上角点 **"导出"**，下载 CSV，按日期保存（例如 `gsc-2026-11-01.csv`）。案例里只引用导出文件里的数字。

---

## 二、Google Analytics 4（看访问人数、来源、点击行为）

### 1. 创建媒体资源
1. 打开 https://analytics.google.com ，点 **"开始衡量"**，或者进入 **管理 → 创建 → 媒体资源**。
2. 账号名称和媒体资源名称都可以填 `liwanwen.com`。时区选你所在的时区，币种选 EUR。
3. 选择平台时选 **"网站"**：网址填 `https://liwanwen.com`，数据流名称填 `liwanwen.com web`。
4. 创建完成后会显示一个 **衡量 ID**，格式是 `G-XXXXXXXXXX`。把这个 ID 告诉我就行，它会公开出现在网页代码里，不属于密钥。

### 2. 在网站上安装跟踪代码
这一步要修改网站代码，在每个页面的 `<head>` 里加一小段 gtag 脚本。修改前我会先把代码给你看，你确认后再改，改完需要重新部署到 Netlify。

### 3. 在欧盟上线前要先确认：Cookie 同意
GA4 会在访客浏览器里设置 cookie。按照欧盟的 GDPR 和 ePrivacy 规定，**访客同意之前不应该加载 GA4**。这一点我不是法律顾问，建议你自己确认后再决定。常见的做法有三种：
- **A. 加一个简单的 cookie 同意横幅**：访客点"接受"之后才加载 GA4。推荐这种做法。
- **B. 使用 Google Consent Mode v2**：访客同意之前，只发送不带 cookie 的匿名信号。
- **C. 不用 GA4，改用不需要 cookie 的统计工具**：比如 Netlify Analytics（付费）或 Plausible（付费）。

你确定选哪一种之后，我再写对应的代码。

### 4. 验证安装是否成功
- GA4 左侧菜单进 **报告 → 实时**，然后用手机打开 liwanwen.com，大约 30 秒内应该能看到 1 位活跃用户。
- 如果你选了方案 A，记得先在横幅上点"接受"。

---

## 三、记录真实数据的时间节点（建议）

| 时间 | 做什么 |
|---|---|
| 上线当天 | 用本工具跑一次 before 检查（已做，见 data/history） |
| 修改后部署当天 | 用本工具跑 after 检查，生成前后对比 |
| 修改后第 2 周、第 4 周、第 8 周 | 导出一次 Search Console 效果报告，并截图 GA4 的"获客"报告 |

案例文档只写导出文件里的真实数字。数据太少时，就直接写"样本太小，暂无结论"。
