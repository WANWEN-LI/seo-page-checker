# 项目状态（2026-10-19）

给新的对话窗口用：先读这个文件，再继续工作。

## 已完成
- **SEO 工具**：仓库 https://github.com/WANWEN-LI/seo-page-checker（公开，MIT），59 个测试。README、中英文案例（`portfolio/case-study-*.md`）和截图都已更新。
- **网站 liwanwen.com**：托管在 Netlify，站点 `nimble-cactus-619ce1`，site id `83896ecc-bc00-4e9e-9546-a734251f4d76`，DNS 也在 Netlify。
  - 源文件：`~/Documents/Codex/2026-10-16/wo-x/outputs/wanwen-portfolio/dist`
  - 部署：`npx netlify-cli deploy --prod --site <site id> --dir <dist>`（命令行已登录）
  - 修改前的备份：`wanwen-portfolio/dist-before-seo-2026-10-18`
- **展示页** `/seo-checker/`：51 秒视频，两个真实的前后对比。
  - 演示店铺 `/petal/`：Lighthouse 66 → 100，LCP 50.0 s → 1.9 s
  - 作品集 About 页：Lighthouse 63 → 92
  - 视频制作流程：`wanwen-portfolio/video-engine/`（场景页 `seo_scene.html`，截图脚本 `petal_shots.mjs`）
  - 重新生成展示页：在 SEO 工具仓库里运行 `python scripts/build_showcase.py <dist>/seo-checker`
- **首页**：SEO 工具的精选区块排第一，项目排序为 SEO → 邮件自动化 → London Home Finder。
- **简历**：网站版 PDF 已更新。源文件是 `career-ops/output/cv-wanwen-li-web.html`，`cv.md` 和 `article-digest.md` 已同步，经历统一写为 5 年（2 年任职 + 3 年创业）。
- **Photography 页**：头像改为 WebP，Lighthouse 中位数 91，LCP 3.0 s。
- **关键词**：首页、About、Projects 的 title 和 description 已加入 growth / marketing analytics。
- **Search Console**：TXT 验证记录已加到 Netlify DNS。

## 进行中 / 待办
- **GA4**（衡量 ID `G-8566HQJMFM`）：先同意、再加载的横幅已接到 6 个页面（`dist/assets/analytics-consent.js`），2026-10-19 已上线。线上检查了首页、About、/seo-checker/、/petal/：横幅都会出现；点"接受"前对 Google 的请求为 0，点"接受"后才加载 gtag 并发送数据。
- **Search Console**：在"站点地图"里提交完整网址 `https://liwanwen.com/sitemap.xml`。
- 等 Search Console 积累 2–4 周数据后，导出效果报告，再更新案例文档。只引用真实数据。

## 原则
只写真实测量过的数字；修改网站前先列清单，确认后再改；部署前先预览；截图和视频里不放个人照片和私人信息；提交作者邮箱用 wanwenli.contact@gmail.com。
