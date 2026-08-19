# Requirements Document

## Introduction

JavLibrary 是 mdcx 的核心刮削源之一，但其页面受 Cloudflare 保护。当前 mdcx 使用普通 HTTP 请求访问 JavLibrary，遇到 CF JS challenge 时直接失败。已有 TRAWL/FlareSolverr 适配层作为 CF bypass 机制，但 TRAWL（Camoufox/Firefox 内核）实测过不了 JavLibrary 的 CF 挑战。

经实测验证，Selenium + Edge headless 模式能稳定通过 JavLibrary 的 CF JS challenge 并完成全字段刮削（cn/ja 双语言验证通过）。本特性将 Selenium + Edge 作为 JavLibrary 的 CF bypass 后端集成进 mdcx，同时为 JavLibrary 爬虫补充 DMM 高清封面升级能力，与 JavBus/JavDB 等爬虫对齐。

## Scope

- **适用站点**：仅 JavLibrary。JavDB/Lulubar/MissAV 经实测 Selenium+Edge 方案无法自动过 CF（JavDB 需手动交互、Lulubar 用 Turnstile、MissAV 连接被直接关闭），不在本特性范围内。
- **触发条件**：普通 HTTP 请求遇到 CF challenge 时，自动 fallback 到 Selenium+Edge。
- **附加能力**：JavLibrary 刮削结果补充 DMM 高清封面升级（cover/poster），复用现有 `dmm_direct.upgrade_dmm_cover`。

## Glossary

- **CF challenge**：Cloudflare 防护挑战，包括 JS challenge、managed challenge、Turnstile 等。JavLibrary 使用 JS challenge（低级防护）。
- **Selenium+Edge headless**：使用 Microsoft Edge 浏览器以无头模式运行 Selenium WebDriver，通过真实浏览器引擎渲染绕过 CF JS challenge。
- **Fallback**：普通 HTTP 请求失败时，自动切换到备用获取方式（Selenium）。
- **DMM 高清封面升级**：将爬虫获取的低清/水印封面替换为 DMM CDN 上的高清版本（pl.jpg/ps.jpg），复用 `mdcx/crawlers/dmm_direct.py` 的 `upgrade_dmm_cover` 函数。
- **Selenium Manager**：Selenium 4.6+ 内置的 driver 自动管理器，自动下载匹配版本的 msedgedriver，无需手动打包 driver。
- **page_source tbody 问题**：Selenium `driver.page_source` 返回的 HTML 经浏览器 DOM 序列化后会自动补全 `<tbody>` 标签，导致 mdcx 现有 xpath（`/table/tr/td`）匹配失败，需改用 `//` 路径。

## Requirements

### Requirement 1: Selenium CF Bypass 后端

**User Story:** AS mdcx 用户，我希望 JavLibrary 遇到 Cloudflare 挑战时能自动通过，以便在无需手动配置外部服务的情况下完成刮削。

#### Acceptance Criteria

1. WHEN JavLibrary 普通请求返回 CF challenge 响应时，系统 SHALL 自动启动 Selenium+Edge headless 模式重新获取页面 HTML。
2. WHEN Selenium+Edge 获取到页面 HTML 且不含 CF challenge 标记时，系统 SHALL 将该 HTML 传递给 JavLibrary 爬虫的解析逻辑进行字段提取。
3. IF 用户环境未安装 selenium 包，系统 SHALL 在首次触发 CF bypass 时自动执行 `pip install selenium`，安装完成后继续执行 bypass。
4. IF 用户环境为无 Edge 浏览器的系统（如 Linux/macOS 无 Edge），系统 SHALL 跳过 Selenium bypass 并回退到原有错误处理流程。
5. WHILE Selenium driver 正在获取页面时，系统 SHALL 设置 90 秒页面加载超时，超时后判定为 bypass 失败。
6. WHEN Selenium bypass 完成后，系统 SHALL 关闭 driver 进程释放资源。

### Requirement 2: Selenium Bypass 配置控制

**User Story:** AS 高级用户，我希望能够控制 Selenium CF bypass 的开关和行为，以便在特定场景下禁用或调整。

#### Acceptance Criteria

1. WHEN 用户在配置中显式关闭 Selenium bypass 时，系统 SHALL 跳过 Selenium fallback 直接返回原始错误。
2. WHILE Selenium bypass 默认开启时，系统 SHALL 在配置文件中提供开关字段供用户调整。
3. WHEN 用户配置了外部 cf_bypasser 地址（`cf_bypass_url`）时，系统 SHALL 优先使用外部 bypass 服务，Selenium bypass 作为最后兜底。

### Requirement 3: xpath 适配 Selenium HTML

**User Story:** AS 开发者，我希望 JavLibrary 的 xpath 解析能同时兼容普通 HTTP 和 Selenium 两种 HTML 来源，以便 bypass 前后解析逻辑统一。

#### Acceptance Criteria

1. WHEN 解析普通 HTTP 请求返回的 HTML（无 `<tbody>`）时，系统 SHALL 正确提取所有字段。
2. WHEN 解析 Selenium `page_source` 返回的 HTML（含自动补全的 `<tbody>`）时，系统 SHALL 正确提取所有字段。
3. WHILE 使用 `//` 路径替代 `/table/tr/` 路径时，系统 SHALL 保持对无 `<tbody>` HTML 的兼容性，不产生误匹配。

### Requirement 4: DMM 高清封面升级

**User Story:** AS mdcx 用户，我希望 JavLibrary 刮削的封面图能自动升级为 DMM 高清版本，以便获得与其他爬虫一致的封面质量。

#### Acceptance Criteria

1. WHEN JavLibrary 刮削成功且番号为有码番号时，系统 SHALL 调用 `upgrade_dmm_cover` 尝试升级封面和海报为 DMM 高清版本。
2. IF DMM 高清封面探测成功，系统 SHALL 用高清 URL 覆盖 JavLibrary 原始封面 URL。
3. IF DMM 高清封面探测失败，系统 SHALL 保留 JavLibrary 原始封面 URL。
4. WHEN 番号为无码番号时，系统 SHALL 跳过 DMM 封面升级。

### Requirement 5: Selenium Bypass 降级与错误处理

**User Story:** AS mdcx 用户，我希望 Selenium bypass 失败时系统能优雅降级，以便不影响其他爬虫的正常工作。

#### Acceptance Criteria

1. IF Selenium bypass 因 driver 启动失败、超时、或页面解析失败而无法获取有效 HTML，系统 SHALL 记录错误日志并返回原始 CF challenge 错误信息。
2. WHEN Selenium bypass 失败后，系统 SHALL 确保后续 JavLibrary 请求可正常重试（不永久禁用 bypass 能力）。
3. IF Selenium bypass 连续失败达到阈值，系统 SHALL 临时跳过 Selenium bypass（冷却期），避免反复尝试拖慢刮削速度。
4. WHILE Selenium bypass 正在执行时，系统 SHALL 阻止同 host 的并发请求重复启动 driver（单例锁）。

### Requirement 6: 多域名轮询

**User Story:** AS mdcx 用户，我希望 Selenium bypass 能自动尝试 JavLibrary 的多个镜像域名，以便在主域名不可用时自动切换。

#### Acceptance Criteria

1. WHEN Selenium bypass 执行时，系统 SHALL 依次尝试 JavLibrary 的已配置域名列表（动态直连地址 + 镜像）。
2. IF 某域名 CF 挑战未通过或页面加载失败，系统 SHALL 继续尝试下一个域名。
3. WHEN 某域名成功获取有效页面时，系统 SHALL 停止尝试后续域名并返回结果。
