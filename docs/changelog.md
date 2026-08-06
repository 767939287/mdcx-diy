# Changelog

## v2.0.4 (2026-08-04) 当前版本

### 功能

- **从 AVdb 同步演员映射**：演员库维护工具新增「从 AVdb 同步」按钮，消费社区维护的 `actor-mapping.xml`（li-peifeng/Jav-Actors-Mapping），一键补齐中文名/繁体名/别名/出生日期/简介。数据源四选一：jsDelivr 加速（默认）/ GitHub 直连 / 自定义下载地址 / 本地 xml 文件
- **演员数据库新增「出生日期」「简介」两列**：`bio_graphy` 解析出结构化出生日期（YYYY-MM-DD）与静态简介，剔除动态「N岁」年龄；老 7 列 xlsx 向后兼容
- **智能合并写入**：匹配顺序 jp 精确 → 中文精确 → keyword 命中 → 未匹配新建；本地优先只补空缺、绝不覆盖已有数据；keyword 合并去重；tmdbid 冲突视为同一人并入别名而非新建
- **数据库静态校验脚本**：`scripts/check_actor_db.py` 检查出厂 xlsx 的 jp 重复、keyword 脏数据/重复词、空字段、tmdbid 重复、出生日期格式，挂入 `uv run check`
- **Emby 演员信息补全接入本地演员库（最高优先）**：自动补全 actor 信息时优先查询本地 `actor_database.xlsx`，命中即用本地「出生日期」填 PremiereDate/ProductionYear、本地「简介」填 Overview（换行转 `<br/>`），本地有简介则彻底跳过 wiki/minnano/数据库网络来源；仅本地简介缺失时才退回外部补齐，生日仍取本地。离线可用、降低外部依赖，返回统计新增 Local 计数
- **Emby 演员管理器新增 graphis 头像和背景图**：匹配头像时新增 graphis.ne.jp 来源（位于 gfriends 之后、minnano 之前），同时下载 prof.jpg（头像）和 model.jpg（背景图），同步时一并上传到 Emby
- **Emby 演员管理器接入本地演员库（最高优先）**：`search_actor_info` 优先查询本地 `actor_database.xlsx`，命中即用本地出生日期和简介回填，有简介则彻底跳过网络来源，与信息补全按钮行为一致
- **Emby 演员管理器跳过逻辑精确化**：`_try_fetch_info` 不再仅靠 `has_overview` 布尔值跳过，改为重新拉取 Emby 当前 Overview 并检查是否为"无维基百科信息"占位符，占位符视为缺失重新获取
- **剔除男演员（TMDB gender 校验）**：`actor_database.xlsx` 数据来自 AVdb 映射，包含男优（加藤鷹、しみけん 等）。新增「剔除男演员」按钮（演员库维护组）：按 tmdbid 调 TMDB `/person/{id}` 取 gender，gender=2（男）的行删除，删除前备份到独立「男优备份」sheet；gender 0/1、请求失败、无 tmdbid 一律保留不误删。支持限量与手动停止。同时 `sync_from_avdb` 新增 `filter_male=True` 源头过滤——待新建条目校验性别，男优直接跳过不写入，本地已有 tmdbid 不重复请求
- **出厂库增量合并进用户库**：出厂库（`resources/userdata/actor_database.xlsx`）随软件版本更新（清洗修正、新增演员），但老用户已存在的用户库（`userdata/actor_database.xlsx`）此前只在首次创建时复制、之后不再同步，清洗成果无法到达老用户。新增 `resources.merge_actor_db_from_backup`：启动时把出厂库中「用户库没有的新条目」完整追加，并给「用户库已有但字段空缺」的条目补全（tmdbid/生日等）——只增不删、绝不覆盖用户已填的值、绝不删除用户库任何行；**别名列做并集合并去重，按「纯中文→中日混合→日文→罗马音」排序（中国人习惯）**；用出厂库 md5 写入 `userdata/.actor_db_merge_marker` 标记，出厂库未变化时跳过，避免每次启动重复扫描。配套测试 9 个 `tests/test_actor_db_merge.py`
- **出厂库 tmdbid 全量验证补完**：确认出厂库 5657 个有 id 演员的验证状态——5511 个在身份排查 audit 中验证过，146 个补 id 时经软件正向搜索验证过，剩余 37 个未验证的逐一用 TMDB `person/{id}` 反查补齐：19 个 TMDB 已删除（404 失效 id，如 `桃乃木香奈`/`楓カレン`/`三佳詩`）、2 个错误映射（`星海レイカ`→Yuka Kojima、`ジゼル`→Tyra）→ 清除这 21 个 tmdbid；16 个确认片假名↔英文同人（`キャシー・ヘブン`→Cathy Heaven 等西方女优）→ 保留。有 tid 5678 → 5657，出厂库 id 全部验证通过（合并进用户库的 id 均为正确映射）
- **清除出厂库中误收录的非 AV 人物 id**：用 TMDB `adult=False` 标记筛查出出厂库混入大量非 AV 人物——先清除 39 个确定项（好莱坞影星 `玛丽莲·梦露`/`汤唯`/`张雨绮`/`莎朗·斯通`、知名声优 `水樹奈々`/`林原めぐみ`/`竹内順子`、日本女演员 `橋本環奈`/`有村架純`/`長澤まさみ`），再对剩余 987 个 `adult=False` 用 `combined_credits` 作品名复核（强成人特征词 vs 主流作品占比，断点续传+进度展示）：366 个确认非 AV（声优/偶像/歌手/主流演员如 `坂本真綾`/`安室奈美恵`/`安宥真`/`白石麻衣`/`浜崎あゆみ`）清除 id，368 个有成人作品保留，245 个不确定保留（宁缺毋滥）。有 tid 5657 → 5252（其中 4485 个 adult=True 真 AV，767 个 adult=False 但复核 av/unknown 保留）
- **删除确认非 AV 的演员行**：405 个复核确认非 AV 的人物（含 39 个确定项 + 366 个作品复核判定）从出厂库整行删除（非仅清 id），确保 `玛丽莲·梦露`/`安室奈美恵`/`橋本環奈` 等绝不在 AV 演员库。新增 `scripts/clean_actor_db_non_av.py` 固化该检测规则——遍历有 tmdbid 的演员，adult=True 保留、adult=False 拉作品复核、确认非 AV 整行删除（删除前备份 .bak，支持断点续传与进度展示），供以后重复清理。出厂库 20757 → 20352 行
- **清除无 id 演员中混入的非 AV 人物**：对之前软件筛查遗留的 220 个「匹配到 TMDB 但 adult=False」的无 id 演员，逐一拉 `combined_credits` 完整作品复核——36 个确认非 AV（K-POP 偶像 `本田仁美`/`イェジ`/`スヨン`/`Lisa`、声优 `内田彩`、特摄演员 `川崎愛`/`高橋明日香`、歌手 `小野春菜` 等）删除整行，其中修正 1 个误判（`西永彩奈` 作品全为 Air control AV 系列，实为真 AV 女优，保留）；20 个有成人作品保留，161 个作品少/无法判断保留（宁缺毋滥）。出厂库 20352 → 20317 行
- **同一演员重复行合并（A+B 类）**：发现出厂库存在大量「同一 TMDB person 对应多行」的情况——A 类空格差异（`高見えな`/`高見 えな`）13 对、B 类无 id 日文 + 有 id 中文/罗马音（`愛原つばさ`/`爱原翼`）37 对，合并 50 对删除 48 行。用 libredmm 作品数逐一验证主名方向，发现 7 对方向错误（`波形モネ`/`青木琴音` 等，主名应为作品多的 `青木琴音`）回滚重做；23 对 tie 经分类确认 keep 方向正确（日文原名/无空格为主名）。合并后别名并集、空缺字段补全，出厂库 20317 → 20269 行
- **补全 libredmm 链接**：对 A+B 涉及的演员逐一搜索 libredmm 补全 href，链接从 74 → 122 个
- **C 类双艺名/多重别名合并**：对出厂库中「两个日文艺名」的疑似同人（无码演员，libredmm 无记录）用 javdb app 演员 ID 体系判断主名——javdb `name` 字段是主名、`other_name` 是别名、作品数辅助判断（修复 actor 匹配逻辑后 `沖田いつき` 归一到主名 `赤瀬尚子`、`東雲れん`/`御坂りあ` 归一到 `御坂莉亞`）。合并 52 对单对 + 2 组多重别名（`園田かのこ`=華澤かこ+藤崎いのり、`麻宮わかな`=若宮エレナ+西村綾香，avwikidb 确认）+ 1 组重复 id（`櫻木梨乃`=真名瀬りか）。另用 avwikidb（用户手动查证）+ javdb + libredmm 三方交叉验证合并 2 组重复 id（`西倉まより`(主名,23部) + `鶴島さゆき`、`咲田ラン`(主名,12部) + `丸川あみ`）。出厂库 20269 → 20211 行
- **无 id 演员重查补 id（融合软件 TMDB 方法）**：对 271 个「被清除 id + 仅名字」的无 id 演员，融合软件刮削 `query_single_actor_cached` 的成熟匹配（名字匹配 + `place_has_japan`/`adult`/`popularity`/`known_for_count` 优中选优，用 keyword 别名辅助搜索）——找到 257 个候选，其中 220 个 adult=True，再逐一反查验证库名/别名（含繁简）确实在 TMDB name/aka 中，确认补回 214 个正确 id（`桃乃木香奈`→2616715、`三佳詩`→5882313、`楓カレン`→2638477、`海野環`→1548446 等），剔除 43 个名字不匹配/错误映射（`白井ほの`→大沢美加、`未来`→志田未来、`夢華さら` 等）。有 tid 5270 → 5484

### 修复

- **新增「校验 tmdbid 有效性」按钮**（演员库维护）：TMDB 是公开平台，person id 可能被删除/重建/合并（如「三佳詩」旧 id 6231965 被 TMDB 删除后重建为 5882313），库中 id 静态存储不会自愈，失效 id 被刮削直接采用会导致拿错误资料或 404。新增 `verify_tmdb_ids`：扫描库中所有有 tmdbid 的行，并发调 TMDB `person/{id}` 校验，404（person 已删除）清除该行 tmdbid + tmdb url（回到无 id 状态，宁缺毋滥，刮削按名字重新搜索）；清除后**按名字重搜 TMDB 自动补回新 id**（复用 `query_single_actor_cached`，仅补 adult=True 且名字匹配的，如三佳詩 6231965→5882313）；网络错误/限流/5xx 保守保留不误清；支持 limit 限量与手动停止。工具页新增「校验 tmdbid 有效性」按钮（含说明文字）触发。配套测试 4 个（失效清除/全有效保留/网络错误保留/补回新 id）
- **TMDB 演员匹配优化**（`tmdb_actor`）：`_expand_name_variants` 加入繁→简转换（zhconv zh-cn），覆盖 variant map 未收录的大量繁简字（`三佳詩`/`三佳诗`、`涼子`/`凉子`）——TMDB name/aka 常为简体、库名常为繁体，此前匹配失败导致漏配；`_query_single_actor` 候选排序 `adult=True` 权重提升至 `place_has_japan` 之前——AV 女优的 adult 标记是最强信号，优先于"日本出生地"（日本普通演员也出生日本），减少同名普通演员冒充 AV 女优的误选
- **TMDB 演员匹配稳健性优化**（`tmdb_actor`）：候选从 `results[:5]` 放宽到 `results[:10]`（通用名时正确结果可能不在前 5）；新增 `hit_count` 命中变体数作为排序维度（置于 adult/place_has_japan 之后、popularity 之前），同名演员只命中 1 个通用变体的弱匹配不再与多变体命中的强匹配同等对待；`known_for_count` 改为从 search 接口的 `known_for` 字段取值——person detail 接口不含 `known_for`，此前恒为 0 是无效排序维度

- **工具页布局重叠**：增高「演员库维护」组后曾与下方 `groupBox_7` 重叠 110px，连锁下移下方 6 个分组并同步滚动容器高度
- **漏加 UI 控件**：生成文件 `MDCx.py` 曾漏加「从 AVdb 同步」的提示 label，导致运行时不显示，已补齐
- **设置页 groupBox 布局重叠**：全面检查所有 tab 发现 2 处历史遗留重叠——命名页 `groupBox_40`（字段命名规则）与 `groupBox_8`（视频命名规则）重叠 181px、下载页 `groupBox_34`（创建剧照副本）与 `groupBox_66`（显示剧照）重叠 21px。连锁下移受影响 groupBox 及下方所有兄弟，统一间距为 19px，同步滚动区高度
- **重复且无效的补全范围单选按钮**：设置-演员页 `frame_8`/`frame_9` 中误放了 4 个与正确版本（无后缀）视觉重复的"所有女优/仅缺少信息"单选按钮，无代码接线、点击无效，已删除
- **MDCx.py 与 MDCx.ui 文案漂移**：将手工维护的界面文案（Emby 演员管理器描述含 graphis、项目主页 `mdcx-diy` 链接、帮助尾注）回写 `MDCx.ui` 作为唯一权威源，重编译不再回退文案
- **`validate_crawler_registry` 误报**：已废弃枚举值 `Website.AIRAV`（仅用于兼容旧配置、无爬虫）不再算作缺失爬虫
- **网络诊断超时硬上限**：诊断单个站点超时从 5 秒硬上限改为使用用户配置的超时时间（#25）
- **网络诊断路由列**：诊断结果新增"路由"列，显示每个站点实际走代理还是直连，便于排查代理配置问题（#26）
- **全面代码审查安全修复**：
  - `shell=True` 命令注入风险（`utils/file.py` 用 `explorer /select` 打开路径）改为参数数组调用
  - 移除 11 处 `?api_key=` URL 查询参数暴露（已有 Authorization 头）
  - 修复 5 处无声 `except`（加 traceback/日志输出），`warm_cache.py` 新增下载 URL 白名单校验（防供应链投毒）
- **minnano 演员日文名查找路径 bug**：`minnano_crawler._lookup_japanese_name` 硬编码相对路径 `resources/userdata/actor_database.xlsx` 逐行扫描——打包后 CWD 变化路径失效，且读的是出厂库而非运行时用户库（用户同步/刮削的新数据查不到）。重构为复用 `resources.get_actor_data`（内存缓存+反向索引，读运行时用户库），支持中文/日文/别名/归一化变体匹配，消除每次全表扫描。配套测试 5 个 `tests/test_minnano_lookup.py`
- **minnano 缓存文件路径 bug**：`CACHE_FILE` 硬编码 `resources/userdata/minnano_cache.xlsx`，`_get_cache_path()` 解析为 `data_folder/resources/userdata/...`——打包后 `data_folder` 下无 `resources` 子目录，缓存读不到也写不进。改为标准用户数据目录 `userdata/minnano_cache.xlsx`（与 `resources.u()` 一致），`save_cache_row` 写入前自动创建父目录。配套测试 2 个（缓存路径、自动建目录+读写）

### 工程质量

- **清理死代码**：移除 `PreparePreviewThread` 中未使用的 `info_sources` 属性
- **AVdb 解析独立模块**：`mdcx/utils/xml_avdb.py`（纯标准库）含解析、出生日期提取、年龄剔除、转义清洗，配套 22 个单元测试
- **记忆文件更新**：`.monkeycode/MEMORY.md` 合并工具页 UI 改动注意点（连锁下移、手工核对生成控件、comboBox 内部件误报）
- **mypy 严格化（三阶段，彻底移除 `disable_error_code`）**：`pyproject.toml` 中 19 项 `disable_error_code` 全部移除，全项目 mypy 零抑制通过（133 文件）。`scripts/check.py` 的 `check` 命令加入 `mypy mdcx/`，推送前自检覆盖类型检查。各阶段：
  - 移除 `assignment`/`arg-type`/`return-value` 并修复 43 处类型错误（变量类型冲突、可选值未收窄等）
  - 移除 `no-redef`/`misc`/`var-annotated`/`list-item`/`func-returns-value`/`attr-defined`/`method-assign`（循环变量复用、except 外 walrus 赋值、重复注解等）
  - 移除 `override`/`call-arg`/`call-overload`/`union-attr`/`annotation-unchecked`/`import-untyped`：`BaseCrawler` 泛型化使 9 个爬虫类的具体 Context 匹配超类签名；`file_done_dic` 安全默认值用 `cast`；Qt 控件 None 断言收窄；`parse_fanza_resp` None 安全化
- **顺带修复的类型检查暴露 bug**：
  - `CrawlerDebugInfo.search_urls/detail_urls` 默认 `None` 改为空列表，消除潜在 `.append()` 崩溃
  - wiki 简介获取 `res_wiki.get("intro")`（实为 URL 字符串）改为 `actor_info.overview`
  - `emby_actor_manager` 的 `wiki_intro` 未初始化导致 `UnboundLocalError`
  - `cnmdb._run` 解引用 `None` 返回值补 `CrawlerException`
  - 回滚修复 `get_checkbox`/`get_radio_buttons` 默认参数被误删的回归（28 处单参调用会 `TypeError`）
- **UI 结构自动化测试**：新增 `tests/test_ui_structure.py`（5 个测试）固化 UI 结构约束——groupBox 同父容器不重叠/无负间距/不超滚动区、用户控件 objectName 唯一、`MDCx.py` 与 `MDCx.ui` 重编译同步（防手工漂移）。自动纳入 `uv run check` 与 CI pytest
- **`validate_crawler_registry` 测试**：新增 `test_validate_crawler_registry_no_missing`，固化"新增 Website 枚举必须注册爬虫"且废弃值 AIRAV 不得有爬虫

### 文档

- **使用说明 tab 更新**：项目主页链接修复为 `mdcx-diy`，上游项目信息改为 `sqzw-x/mdcx → Hazard804/mdcx → ZiPenOk/mdcx`
- **README / INSTALL / FEATURES / USER_GUIDE / CONFIGURATION**：修复 3 处仓库链接，补充 graphis 和本地演员库等新功能描述

### 演员库数据清洗

- **存量垃圾数据清洗**：新增 `scripts/clean_actor_db_field_noise.py` 一次性清洗出厂 `actor_database.xlsx`，清理约 300 处字段噪声——名字混入系列/站点标签（`パコパコママ`/`FC2`/`グラドル`/`トリプルエックス`）、年份（`（2015）`）、国籍/事务所标注（`マオ（ベトナム）`/`Lisa【FALENO】`）、描述污染（`巨乳女子プロレスラー凛叶`/`生意気ツインテール18ちゃん`）；别名混入作品标题（`ラグジュTV`/`ママ友喰い`/`VOL.xx`）、名字+年龄（`あいみ 20歳`）、类型标签（`人妻`/`着エロ`）、悬空斜杠/残括号（`ただえりさ /`）；占位符名字（`素人奥様`）与简介碎片置空。保留罗马音/日文映射、读音、韩文别名等合法内容
- **新数据自动清洗防线**：新增 `mdcx/utils/actor_clean.py` 统一语义清洗模块，`sync_from_avdb`（AVdb 同步）与 `update_actor_db_row`（刮削写入）入口自动应用——今后 AVdb 同步或刮削新增的演员数据自动剥离同名噪声；纯占位符名返回 `skipped_placeholder` 不写入脏数据。清洗脚本重构为复用该模块，存量清洗与新数据清洗共享同一规则源
- **配套测试**：新增 `tests/test_actor_clean.py`（18 个用例）覆盖名字/别名的标签剥离、标注剥离、作品标题剔除、悬空斜杠修复、占位符识别、合法别名保留；`update_actor_db_row` 占位符保护与清洗写入各 1 个用例

### TMDB 演员身份排查与清理

- **背景**：AVdb 同步数据中发现部分 tmdbid 指向错误人物（如动画录音师、声优、好莱坞演员），经 TMDB API 全量排查 9251 个有 id 演员（9232 成功），识别出疑似非 AV 演员 3447 个
- **排查方法**：第一波查 `person/{id}` 取 `adult` 标记与 `known_for_department`；第二波对 `adult=False` 的 4511 个查 `combined_credits` 作品，按作品名判断是否成人内容。校准确认知名 AV 女优（三上悠亜/波多野結衣等）均为 `adult=True`
- **分类结果**：明确 AV（adult=True）4721 个、非 Acting 部门 934 个、Acting+有成人作品 1052 个、Acting+仅非成人作品 2414 个、Acting+无作品 99 个
- **清理动作**：删除疑似非 AV 演员 3447 行（非 Acting 部门 934 + Acting 无成人作品 2414 + 无作品 99），出厂库 24243 → 20796 行，保留男优备份 sheet。宁缺毋滥——错误 id 比无 id 更糟（刮削兜底会取到错误人物资料），删除后刮削遇同名演员按名字重新搜索
- **顺带修复**：清除 7120 行"无 tmdbid 但 url 有值"的孤儿 url（AVdb 源数据错误映射残留，url 内 id 与库中已有行重复但非同一演员，反推补 id 会固化错误）
- **无 id 演员软件筛查**：复用项目 `query_single_actor_cached`（含 `include_adult=true`、名字变体扩展、性别过滤）按名字批量筛查 14952 个无 id 演员——14469 个无匹配（真 AV 女优 TMDB 未收录），483 个匹配到 person；其中 263 个 adult=True 可补 id、220 个 adult=False 疑似非 AV
- **补 id 与去重**：263 个可补 id 中，116 个与库中已有 id 重复（9 个经别名证明是同一人应合并、107 个无法证明不补）；147 个全新 id 经 TMDB `also_known_as` 逐一验证后补入（146 个成功，1 个 `本庄ひな` 别名指向库中已存在的 `菊川みつ葉` 故撤销）。最终有 tid 5804 → 5950
- **adult=False 的 220 个**：TMDB 标 non-adult 的匹配人物，抽查发现混杂两类——未标 adult 的 AV 女优（`愛田るか`/`浅倉麗`）与真非 AV 人物（`本田仁美`=IZ*ONE 偶像/`内田彩`=声优）。因 adult 标记与作品关键词判断均不可靠，**保留不处理**——它们保持无 id 状态，刮削按名字搜索自然容错，符合宁缺毋滥原则
- **有 id 演员 id 反查（tmdbid 校验）**：AVdb 同步的数据准确性存疑，对全部 5950 个有 id 演员用 id 反查 TMDB `person/{id}`（`name`+`also_known_as` 归一化比对，复用软件 `_expand_name_variants`/`_norm_name_set` 匹配逻辑）——5642 个（94.8%）库名与 id 人物直接匹配确认正确；16 个片假名↔英文对照的西方女优（`キャシー・ヘブン`→`Cathy Heaven` 等）实为同人；258 个存疑（库名与 id 人物无法证实同一人），二次判定用软件 `query_single_actor_cached` 正向搜索复核，25 个被软件认可、233 个未证实
- **清除 272 个存疑 id**：确认 AVdb 源存在真实错误映射（如 `平山加奈`→美国演员 Christa Allen、`森千里`→歌手森高千里、`恵美`→声优绪方惠美、`白井ほの`→大沢美加、`未来`→女演员志田未来），库名与 id 人物无任何关联。清除 272 个无法证实同一人的 tmdbid 与 tmdb url（含 14 个软件搜索结果与库内 id 不一致的），宁缺毋滥——回到无 id 状态，刮削按名字重新搜索自然容错。有 tid 5950 → 5678
- **`sync_from_avdb` 写入防线**：新增 `mdcx/core/tmdb_actor.fetch_person_identity`（带 `_PERSON_IDENTITY_CACHE`）返回 `{gender, name, original_name, also_known_as}`；`actor_db_tool` 新增 `_tmdb_id_matches_entry`/`_entry_variants`/`_is_katakana_roman_pair` 归一化比对（复用软件既有 `_expand_name_variants`/`_norm_name_set` 匹配逻辑，片假名↔英文音译对照视为同人放行，请求失败保守放行）。`sync_from_avdb(verify_tmdbid=True)` 默认开启：待写入的新 tmdbid 先用 `person/{id}` 反查身份，与条目名不匹配则丢弃该 id 保留其他字段（`skipped_tmdbid` 计数，完成日志含「丢弃错误id」统计）；已存在于库中的 id 属历史数据不重复反查。GUI 新增「校验 tmdbid 与名字匹配」复选框（默认勾选）控制开关，见 `mdcx/views/MDCx.ui`。配套测试 6 个（匹配保留/错配丢弃/关闭校验/片假名放行/已存在不反查），`tests/test_actor_db_filter_male.py`
- **生日字段误填清洗**：审计发现 `extract_birth_date` 会把 bio 中「XX年出道」「出道作品发行日期」误提取为生日——12346 行有生日的库中 2199+ 行 bio 明确是出道年份、526 行只填 4 位年份（几乎全是出道年）、171 条 2023+ 完整生日基本全是出道日期，emby 演员卡显示错误生日。修复 `mdcx/utils/xml_avdb.py`：`extract_birth_date` 改为**只在文本出现出生语义（出生/誕生/生年月日/生日）时提取**（新增 `_BIRTH_FULL_DATE_PATTERNS`/`_BIRTH_YEAR_MONTH_PATTERNS`/`_BIRTH_YEAR_PATTERNS`），宁缺毋滥拒绝出道/作品日期；配套测试 6 个（含拒绝出道年、作品日、出生语义保留）。存量数据以 AVdb 源重新提取修正——修正 2167 行（清除出道年份误填 + 补源中的真实出生日期），有生日 12346 → 10583（无 2025/2026 荒谬年份，知名演员正确生日如桃園怜奈 1996-07-27 保留）
- **空 jp 主名行修复**：36 行日文原名缺失（软件 `read_actor_db_xlsx` 遇空 jp 直接跳过，永远加载不到）——11 行可救（有别名/简介/tmdbid，从 bio/别名提取主名补上，如 `高木由香`/`戸田さやか`/`渋谷レミ`），25 行垃圾/占位（`複数`/`管理者様、女優名を復元してください`/`凛女優情報`/`S級素人` 等）删除。空 jp 清零
- **jp 主名重复行合并**：14 组同名行（如 `小沢優` 两行别名互补、`SARA` 一行含 `吉川澪,黒沢麗華` 被另一行覆盖、`アイカ` 一行缺生日）——保留信息更丰富的一行并合并别名/缺失字段，删除冗余行。重复 jp 清零，dict 加载不再丢别名
- **别名重复词去重**：37 行别名列含重复项（`河北麻衣,河北麻衣`、`AIKA,AIKA`、`MARON,Maron`），单行纯去重（大小写不敏感）。`check_actor_db` 错误从 88 → 0（仅剩 22 个 zh_cn/zh_tw 为空的非阻断 warning，属「补全中文名」工具范畴）

## v2.0.3 (2026-08-03)

### 功能

- **演员库维护工具改为直接操作 xlsx**：移除「输入演员名单 / 选择 nfo 目录」输入方式，新增三个独立按钮——补全中文名（按已有 TMDB ID 补中/英繁体翻译）、补全 LibreDMM 链接（补信息链接）、同步别名（用 TMDB 最新 also_known_as 刷新 keyword 列），统一扫描 `actor_database.xlsx`，每个按钮带独立防重入
- **同步别名与刮削共用同一规则**：`run_actor_db_xlsx` 的 `sync_aliases` 改为复用 `_merge_keyword_values`，与刮削写入 actor 库的别名合并逻辑保持一致，永不同步偏差
- **工具页工具排序调整**：按用户偏好重排为 Emby 演员管理 → 演员库维护 → 单文件刮削 → 裁剪图片 → 封面补图 → 软链接助手 → 移动视频字幕 → 检查演员缺失番号
- **打开演员数据库按钮**：演员库维护工具新增「打开演员数据库」按钮，用系统默认程序打开 `actor_database.xlsx` 供查看与手工编辑；文件不存在或打开失败时提示先安装 Excel/WPS 等办公软件
- **并发提速**：演员库维护（补全中文名/链接/同步别名）改为滑动窗口并发模式，TMDB 请求并发 5、LibreDMM 请求并发 2，串行 150s+ 降至约 30s

### 修复

- **单 exe 按钮无提示退出**：修复「打开演员数据库」按钮点击后程序直接退出（根因：`_open_actor_db_file` 误作实例方法调用导致 AttributeError，被 onefile 无控制台吞掉为静默退出）
- **executor.submit 传参错误**：`AsyncBackgroundExecutor.submit()` 只接受单协程参数，`executor.submit(asyncio.run, run())` 写法导致 TypeError。修复 `main_window.py` 的 `_run_actor_db_tool` 及 `tool_handlers.py` 的 cover_backfill 两处同源 bug
- **跨线程 Qt 不安全操作**：`_run_actor_db_tool` 协程内直接 `btn.setEnabled()` 跨线程操作 QWidget。改为 `actor_db_finished` pyqtSignal 主线程恢复，消除潜在 segfault 风险
- **日志通道不通**：`_log_line` 仅写内存 LogBuffer，不显示在 GUI 日志页/文件，用户看到「开始扫描」后无后续输出误以为卡死。改为同时调用 `signal_qt.show_log_text` 实时显示

### 工程质量

- **崩溃转储埋点**：`main.py` 注册 faulthandler + sys.excepthook + stdout/stderr 重定向到 `MAIN_PATH/crash/` 目录， onefile 无控制台环境下的 Python 异常不再被静默吞掉
- **死代码清理**：移除 `init.py` 重复 `setText` 接线、`tool_handlers.py`/`main_window.py` 旧 `pushButton_actor_db_pick_dir/start_clicked` 引用已删除控件的死代码
- **记忆文件写入**：`.monkeycode/MEMORY.md` 记录 9 条经验：onefile 静默退出诊断方法、日志通道一致性、executor.submit 正确用法、跨线程 Qt 安全模式、刮削并发架构参考

## v2.0.2 (2026-08-02)

### 重构

- **工具页槽函数抽取**：将 `main_window.py` 中的 21 个工具/设置页槽函数抽取至独立模块 `tool_handlers.py`，`main_window.py` 从 3539 行减至约 3350 行
- **目录选择模式统一**：新增 `_pick_folder` 公共 helper，9 个目录选择方法统一为一行 delegate 调用
- **删除 2 个废弃 import**：`emby_actor_image`/`emby_actor_info` 改为延迟导入

### 性能

- **行索引缓存**：`update_actor_db_row` 新增 `_ACTOR_DB_ROW_INDEX` 全局索引（jp_name → row_index），消除 O(n²) workbook 全表扫描，三个调用点（actor_db_tool/tmdb_actor/scraper）直接受益
- **读取模式批量落盘**：`scraper.py` 读取模式下演员 TMDB ID 补充改为共享 workbook，集中一次落盘，避免每个演员独立 load/save
- **格式化跳过**：`_format_db_worksheet` 检测表头是否已格式化，首次后跳过边框/字体/列宽设置，每次 save 减少 5 次全表遍历，CI 测试耗时从 20.8s 降至 10.7s

### 工程质量

- **移除 7 个文件的 network 标记**：`test_tmdb_actor.py` 等 7 个文件的 93 个测试全部为纯离线 mock 测试，移除 `pytestmark = pytest.mark.network` 使其进入 CI
- **修复 9 个预存陈旧测试**：`test_network_lifecycle.py` 的 `_FakeLimiter`/`_FakeResponse` mock 修复（添加 async context manager 支持），`test_web_amazon_data.py` 的 mock 路径修正（`mdcx.utils.rate_limit.random`），`test_amazon_database.py` freeze_panes assert 修正
- **新增 14 个测试用例**：行索引缓存 6 个、`_load_actor_db_wb`/`_flush_actor_db_wb` 4 个、目录选择/gfriends 同步 8 个
- CI 离线测试通过数从 **530 提升至 635**（+105），全量 627 passed，4 skipped
- **打包配置补充**：`build.py` 新增 `mdcx.tools.emby_actor_image`/`emby_actor_info`/`sync_gfriends`/`scripts.cover_backfill` 的 hidden-import，排除 6 个开发期包（playwright/setuptools/mypy 等），预估单 exe 体积减少约 200MB

## v2.0.1 (2026-08-01)

### 新增功能

- **演员库维护工具**：工具页新增"演员库维护"功能，可对已有 TMDB ID 的演员批量补全中文/繁体翻译和 LibreDMM 链接，支持输入演员名单或选择 nfo 目录自动收集演员
- **刮削流程精简**：更新模式刮削时不再自动为已有演员补全翻译/LibreDMM 链接（该能力移至独立的"演员库维护"工具），加快刮削速度、减少不必要的网络请求
- **Emby 演员管理器**：工具页新增"Emby 演员管理器"按钮，打开独立对话框，可连接 Emby 服务器获取演员列表、多源匹配头像（Gfriends/minnano-av/本地文件夹）和简介（minnano-av/Wiki/本地数据库），支持批量同步到 Emby
- **Emby 演员管理器 - 选库**：点击"获取演员列表"时弹出媒体库选择对话框，可按需勾选要管理的库
- **Emby 演员管理器 - 表格查看**：演员列表表格展示头像/简介/背景图/影片数状态，支持按缺失情况筛选和搜索
- **封面补图工具**：工具页新增"封面补图"功能，输入番号即可自动刮削并补齐缺失的 `poster.jpg` 和 `thumb.jpg`，复用当前配置的站点优先级、命名、裁切、水印规则，支持批量输入与覆盖已有图片
- **封面补图独立脚本**：`scripts/cover_backfill.py` 支持命令行批量和自定义参数，可在打包外独立运行
- **JIMMY 前缀路由**：`JIMMY-003` 等番号自动路由到 FALENO 官网获取资料
- **失败原因记录**：所有刮削来源均失败时，日志会列出各站点的具体失败原因（超时/搜索未匹配等），便于定位问题

### 改进

- **自动海报选优**：不再将横向海报作为最终 Poster，候选图全为横图时自动改用缩略图右裁切，修复 ABF-371 一类封面未裁剪问题

### 修复

- **Windows 路径超限**：`{{ series }}` 系列名过长导致完整路径超 MAX_PATH(260) 时，自动缩短目录名，修复刮削后文件夹无法打开的问题（#19）
- **中文字幕标签误添加**：共享数据路径中未检查 `nfo_tag_include` 配置，关闭后仍会添加"中文字幕"标签，现已修复（#20）
- **explorer /select 路径未引号**：含空格或特殊字符的路径无法用 `explorer /select` 打开，已修复为加引号调用
- **Emby 4.9 剧照显示**：`extrafanart_extras_copy` 将 .jpg 改为 .mp4 时使用 move 而非 copy，导致 `behind the scenes` 目录下只保留 .mp4，Emby 4.9 无法识别。改为 copy 同时保留 .jpg 和 .mp4（#17）

### 工程质量

- 新增 2 个模块，596 个测试用例（583 通过，13 个为既有环境性网络用例失败，与本次改动无关）
- 无新增第三方依赖，兼容 Windows 打包
- 新增 9 个测试用例：JIMMY 前缀路由测试、失败原因记录测试、海报横向过滤单元测试（7 个覆盖 portrait 选优逻辑）
- 新增演员库维护相关测试用例：nfo 目录收集/去重、空名单、翻译/链接开关控制、翻译与链接补全

## v2.0.0 (2026-07-18)

MDCx v2.0.0 全新出发。

### 新增爬虫

- **R18.dev 爬虫**：新增 `r18dev` 刮削源，走 R18.dev 的 JSON 接口直连，不需要翻墙，番号自动补零适配，支持 dvd_id 和 content_id 两种查询方式
- **JavDB API 爬虫**：新增 `javdb_api` 刮削源，走 JavDB 镜像站 HTML 直连，不用 CF 代理，带演员名简繁转换和异体字修正（筱→篠、穗→穂等），可选镜像站地址
- **MissAV免防护墙爬虫 missav_api**：原MissAV爬虫常被防护墙挡住；现在多了一条免防护墙通道，不用费力绕墙也能直接刮到它的影片信息

### 新增功能

- **界面缩放比例配置**：在"设置 → 界面外观 → 高分屏缩放"设置区域新增缩放比例下拉框，支持"跟随系统"/80%/90%/100%/125%/150%/175%/200% 共 8 档选项（含非整数倍缩放）。选择非默认值时通过 `QT_SCALE_FACTOR` 环境变量（Qt6 原生机制）精确控制界面缩放，解决高分屏字体过大或过小的问题，并可配合暗色模式使用。保存后重启软件生效
- **内置 CF Bypass（零配置）**：新增"启用内置 Bypass"选项，勾选后 MDCx 自动在后台启动本地旁路服务（基于隐身浏览器），无需手动搭建外部服务。
- **新增设置项**：`cf_bypass_auto`（bool，默认 false），与外部 `cf_bypass_url` 互斥，地址为空时方能启用本地服务

### 刮削系统

- **四种刮削模式**：正常模式（全新刮削：扫描→刮数据→下图片→生成NFO→重命名→移动）/ 整理模式（仅归类文件，不下载图片不生成NFO）/ 更新模式（调整已有文件的目录结构）/ 读取模式（维护补刮，4个独立选项自由组合）
- **字段级优先级配置**：每个字段（标题、简介、演员、海报、评分等）可独立配置来源网站顺序和翻译开关，不同刮削类型还可设置不同的字段优先级
- **刮削模式**：支持 info（信息优先）、speed（速度优先）、single（单站快速）三种模式
- **刮削类型独立配置**：有码/无码/FC2/国产/欧美/素人每种类型可分别设置网站源列表
- **马赛克标准化**：自动将各类标签归一化为有码、无码、无码破解、流出、无码流出、国产
- **标签优先级系统**：基于 info_database.xlsx 的标签优先级排序，优先级标签→系列标签→其他标签

### 网络与反爬

- **CF Bypass 双模式**：支持 Mirror 模式（外部 bypass 服务代理请求）与 HTML 模式（调用 bypass 服务 `/html` 端点）
- **域名级独立限流**：每个网站独立令牌桶限流，默认 8 req/s，失败自动退避重试（403/429/500/502/503/504）
- **连接池管理**：三级连接池（HostPool → ConnectionPool → Session），域名级并发控制，Session 热更新，空闲自动回收
- **网络连通性检查**：内置一键测试各网站可达性工具
- **软链接支持**：可选择不移动原文件，创建软链接到目标目录

### 界面与工具

- **暗色/亮色主题切换**：内置完整双主题支持
- **海报裁剪工具**：图形化界面，鼠标拖拽选择裁剪区域，支持 2:3 标准比例
- **缺失文件检测**：检查媒体库中哪些文件缺失
- **成功/失败文件列表**：自动记录处理结果，支持断点续刮
- **多CD分集支持**：多碟片文件自动合并为一条记录
- **额外剧照处理**：自动下载多张剧照并管理副本
- **图片修复**：自动修复下载的图片（尺寸、格式等）
- **24 个命名模板字段**：番号、标题、演员、系列、制作商、分辨率、编码等，Jinja2 条件渲染
- **演员 NFO 生成**：生成 Kodi 兼容的演员信息文件（.actors 目录）
- **内置资源管理**：演员数据库、ASIN 数据库、NFO 信息数据库、字体等资源统一管理

### 配置系统

- **配置自动迁移**：旧版 INI 格式配置文件在加载时自动转换为 JSON 格式
- **配置热切换**：修改配置后自动生效，无需重启
- **敏感字段脱敏**：API Key 等敏感字段在导出时自动替换为 `***`

### 修复

- **网络标签页按钮重叠**：修复了设置页面里网络标签页的控件叠到一起、显示不全的问题，调整了各区域的高度和位置
- **Windows 下启动崩溃**：修复了 Windows 版打开时因 `topLevelItem(1)` 为空导致闪退的问题
- **R18.dev 补零位数**：番号标准化从 3 位补零改为 5 位，跟 R18.dev 数据库实际格式一致
- **fc2cmadb 演员数据爬取修复**：Inertia.js Deferred Props 导致的演员数据缺失问题。修复逻辑改为 Inertia JSON 解析后若 actresses 为空则回退到 HTML table 解析补充，同时增强 Inertia partial reload 请求头（注入 X-Inertia-Version 和 X-XSRF-TOKEN），解决已登录但爬不到演员的问题
- **fc2ppvdb Cookie 检查优化**：域名迁移至 fc2cmadb 后，Cookie 检查不再依赖 `fc2ppvdb_session` 关键字
- **刮削失败标题被日志污染**：修复 `main_window.py:1180` 中刮削失败后标题回退到 `LogBuffer.error().get()` 的问题——该函数会跨任务聚合其他任务的 TMDB 演员处理日志（如 `[演员数据库] 已新增 ... 并写入 tmdbid=...`）作为标题。改为使用文件名兜底
- **刮削过程更稳**：修好了多个任务同时刮时偶尔"串数据"的老毛病，演员信息写入也更省系统资源
- **修好 30 个第三方库的安全隐患**：把软件用到的外部工具库都升级到安全版本，整体更安全

### 改进

- **绕过网站防护墙更稳更快**：后台服务重写，启动不发呆、不卡死；安装包里直接带好隐身浏览器，装完即用，不用额外下载和配置
- **界面缩放优化**：放宽 Windows 窗口最小尺寸限制（从硬锁定 1089x700 改为 QSize(850, 550)），解决 1920x1080 125% 缩放下界面过大且无法缩小的问题

### 工程质量

- **推送前自动跑测试**：新增 pytest 推送前自检，`uv run check` 会自动执行 ruff 格式检查 + ruff 代码规范 + pytest 单元测试，三项全过才能推
- **新增一批测试用例**：R18.dev 14 个测试 + JavDB API 18 个测试，覆盖番号解析、字段映射、搜索匹配等工作

### 其他

- 软件内"使用说明"的内容已更新，过时的信息换成了最新的
- 新增一批自动测试，防止上面的问题以后又冒出来

## v1.4.0 (2026-07-07)

### 新增功能

- **Bing 翻译引擎**：新增 Bing 翻译选项，免费免配置，与 Google 一样自动爬取翻译接口，支持中/英/日互译
- **无码官网爬虫**：official 源扩展支持 Caribbeancom、HEYZO、1Pondo、Pacopacomama、10Musume 五个无码官网，番号自动路由到对应站点
- **official 官网前缀路由**：FNS/FALENO 与 DLDSS/DAHLIA 番号前缀自动委派给对应的子爬虫，扩大官网覆盖范围
- **fc2ppvdb 适配 fc2cmadb**：基础 URL 迁移至 `fc2cmadb.com`，新增 Inertia.js JSON + HTML 双模式解析，不再依赖旧版 fc2ppvdb XHR 接口

### 修复

- **avsex 更新修复**: 兼容 /cn/ 简体中文页面，修复 title/actor/tag/outline/extrafanart XPath 提取
- **iqqtv 标题清理**：去除标题末尾的 `caribbeancom_番号` / `1pondo_番号` 等站点前缀，避免污染无码影片标题
- **fix**: 图片简化命名(poster.jpg)在 skip_reorganize 和不移动文件路径下被忽略

## v1.3.3 (2026-06-23)

### 修复

- **xcity 刮不出中文**：修复了 xcity 刮出来全是英文的问题（加了请求头让网站返回繁体中文，再自动转成简体）
- **多任务同时刮会串数据**：修复了同时刮多个影片时，xcity 的数据会串到别的影片上的问题
- **预置4个默认代理**：amazon.co.jp、m.media-amazon.com、xcity.jp、dmm.co.jp 保障正常刮削 dmm、xcity及下载日亚高清封面

### 日志精简

- **日志去重**：同一行重复的日志不再刷屏了
- **去掉没意义的"(old)"日志**：之前每个文件都会刷"Poster done! (old)"这类消息（意思是"文件已经有了，跳过下载"），现在不显示了，日志减少了将近一半
- **报错提示不再重复弹**：图片下载失败时，"去设置里勾选xxx"的提示只出现一次，不再日志和错误提示各出现一次
- **翻译跳过不再逐行输出**：如果多个翻译引擎都不可用或跳过，现在汇总成一行显示，不再每个引擎占一行

### 日志合并

- **Poster 裁剪日志合并为一行**：以前裁剪海报时先输出"开始处理"，再输出"用了什么策略"，现在合并为一行，信息量不变
- **Poster 直复制缩略图日志合并**：策略说明和完成报告合并为一行

### 开发者工具

- **添加类型检查工具**：新增 pyright 配置，后续开发时能自动发现潜在的类型错误，减少发布后出问题的概率

## v1.3.2 (2026-06-22)

### 功能增强

- **刮削速度优化**：图片下载改成并行模式，缩略图下载完后，海报、剧照等会同时下载，不用排队等了
- **演员 TMDB ID 查询加速**：从 TMDB 查演员信息时，多个演员同时查（以前是排着队一个一个查），补演员改名翻译和网址也合并到一块写入硬盘，减少重复读写

### 界面调整

- **代理设置更清晰了**：原来的"不使用代理"改成了"使用代理"。现在只对你填进去的网站走代理，其他网站默认直连，不会出现代理影响国内网站的尴尬。默认预填了 `amazon.co.jp` 和 `m.media-amazon.com`

### 修复

- **Excel 字体大小不一致**：修复了往演员数据库和 Amazon ASIN 数据库添加新数据时，字体默认变成 12 号，和原来 11 号不统一的问题

## v1.3.1 (2026-06-20)

### 新增功能

- **新爬虫：JavDB APP版接口**：新增 `javdb_app` 刮削源，走的是 JavDB App 的接口，有码/无码/素人/FC2/欧美都能用，配置里对应的分类已默认加上

### 修复

- **欧美影片刮着刮着就超时**：修复了一个代码缩进错误。以前日系番号（如 `SSNI-111`）正常，但欧美番号（如 `Viv-thomas.24.12.20`）因为名字里带点号，程序错误地进入了"等待同番号"的死循环，干等 300 秒后超时报错。现在欧美番号也能正常刮了

### 界面调整

- **可用网站列表刷新**："可用网站"弹窗和"指定网站"下拉框现在和实际注册的爬虫保持一致，移除了已停用的 `avsex`、`love6`
- **无码分类编辑框不再出现有码站**：`javlibrary`、`libredmm`、`dmm_api` 不会再出现在无码的编辑网站对话框里

### 日志优化

- **分隔线不再用满屏 emoji**：以前每个任务开始和结束用 50 个连续 emoji（`👆`×50、`👇`×50）做分隔线，在某些电脑上显示为乱码方框，且日志文件体积巨大。改为 40 个等号 `====`，清爽多了

## v1.3.0 (2026-06-18) 重磅更新

### 新增功能

- 演员日文名更准了：以前填演员表用的是搜索用的中文名，现在改用 TMDB 返回的日文原名（像"三上悠亜"这种）
- 自动补演员网址：刮削完会自动检查哪些演员有 TMDB ID 但没网址，用日文名去 LibreDMM 找到网址填上
- 重磅更新,读取模式下，向已刮削的影片的NFO中补全写入演员tmdbid
- 前提条件：
  - 1.设置网络页面填入TMDB API KEY（没有的要去TMDB申请）
  - 2.设置NFO页面勾选"为演员写入TMDB ID"
  - 3.设置刮削模式为选读取模式，并勾选"允许更新 nfo文件"
  - 4.TMDB上要有这个演员的信息资料
- 注意：如果不想在补全演员tmdbid后，改变nfo中的演员名，请不要勾选设置翻译页面的"使用演员映射表翻译演员"
- 好消息：AVdb的LEO、龙王大佬们在持续补充 TMDB 女优资料中，lsj可以定期用读取模式去获取新增加女优的tmdbid了，不用重新刮削

### 读取模式改进

- **选项更灵活了**：4 个选项现在互不绑定。可以只勾"有 NFO 时更新"不勾"更新 NFO"，就只整理文件不改 NFO；也可以只勾"更新 NFO"不勾"有 NFO 时更新"，就只改 NFO 内容不挪文件

### 修复

- **NFO 里的 `<![CDATA[...]]>`** 改用正规解析，不会再因为内容里恰好有 `]]>` 而出错
- **正则表达式安全**：文件名中的特殊字符会先转义再匹配，不会崩
- **并发请求异常**：演员名查询时如果某个请求出错，不会让整个任务崩溃
- **被悄悄吞掉的错误日志**：演员数据查询中隐蔽的异常现在会写入日志

## v1.2.1 (2026-06-17)

### 修复

- 修复传统窗口模式下（未勾选"隐藏边框"），点击原生标题栏关闭按钮无响应问题
- 修复反序设置导致已有超链接单元格样式标记丢失

### 功能增强

- 完善 LibreDMM 演员链接自动补全功能
- xlsx 冻结窗格从 `A2` 改为 `B2`，同时固定表头行和第1列（番号列），横向滚动时始终可见
- 传统窗口模式下，点击关闭按钮同样遵循 `HIDE_CLOSE` 配置，支持"关闭时隐藏到系统托盘"

### UI 改进

- 更新设置翻译页面提示词，反映 xlsx 数据库格式和 TMDB 自动填充功能

## v1.2.0 (2026-06-16)

### 架构改进

- 将 `_read_actor_db_xlsx` 及列常量从 `tmdb_actor.py` 迁移至 `resources.py`，彻底消除模块初始化阶段的循环导入依赖

### 修复

- **#consts.py** `IS_DOCKER` 改为检测 `/.dockerenv` 文件，避免 Linux 桌面环境误判为 Docker
- **#number.py** `get_number_first_letter("")` 加空字符串保护，防止 `IndexError` 崩溃
- **#tmdb_actor.py** `_tmdb_request()` curl_cffi 分支补上 `follow_redirects` 参数，统一两种 HTTP 后端的重定向行为

### 功能增强

- **#file_crawler.py** `_normalize_release_value()` 增加 `YYYYMMDD` 无分隔符日期格式兼容
- **#tmdb_actor.py** 演员数据库首次发现为 `None` 时自动重试加载（延迟加载兜底），减少不必要的 TMDB API 请求
- **#tmdb_actor.py** 对 `update_actor_db_row()` 增加 `asyncio.Lock()` 防止并发写 xlsx 导致文件损坏
- **#resources.py** `reload_actor_db()` 文件不存在时不再重置 `actor_db` 为 `None`；异常时恢复旧值保留缓存；异常信息同步写入主日志和 traceback 日志

### 代码精简

- **#resources.py** `_get_mark_icon()` 7 处重复的 if-not-isfile-copy 合并为数据驱动循环
- **#number.py** FC2 / HEYZO 番号提取两个几乎相同的 elif 分支合并为一个，区分前缀和最小位数
- **#crawlers/** 12 个爬虫文件各自定义的 `split_csv` 函数统一为 `crawlers/base/types.py` 的共享函数，各文件 import 使用
- **#pyproject.toml** 添加 `[build-system]` 段，符合 PEP 517/518 打包规范

### 线程安全

- **#log_buffer.py** `all_buffers` 字典所有读写操作增加 `threading.Lock` 保护，消除多协程并发时字典损坏风险

## v1.1.0 (2026-06-13)

### 新增功能

- **Minnano-av 演员信息刮削源**
  - 新增 `minnano_crawler.py` 模块，支持从 みんなのAV 网站抓取演员信息
  - 支持中文→日文演员名映射（通过 `actor_database.xlsx` 查找日文原名后再搜索）
  - 实现模糊搜索匹配策略：精确匹配优先，其次多字符公共子串匹配，最后五十音回退搜索
  - 详情页加了标题核对，避免匹配到错误的演员

- **Emby 演员信息增强**
  - 在 Wikipedia 之前优先查询 Minnano-av 数据源，补充 Emby 演员元数据
  - Minnano-av 缓存文件 `minnano_cache.xlsx` 集成，避免重复请求
  - 缓存表头冻结、数据行全边框、URL 超链接，便于用户手动审查

- **Gfriends 头像本地仓库**
  - UI 新增"Gfriends 设置"区域：可以选择本地仓库路径、点按钮更新（拉取最新头像）、显示最后更新时间
  - 有本地仓库时优先从本地读取，不联网；本地没配置时才从 GitHub 网络下载
  - 更新按钮在没选路径或正在更新时禁用，防止误操作
  - 保存配置时，如果本地和网络都没填会弹窗提醒

- **Gfriends 头像升级：AI 修复版优先**
  - 找Gfriends 头像时优先用 `AI-Fix-名字.jpg`（AI 修复增强版），再找普通版

- **搜索链接中文兼容**
  - Graphis、Minnano-av、Wikidata 搜索时，演员名字自动做编码转换，解决日语名字搜索失败的问题

### 配置变更

- 新增 `gfriends_local_path` 配置项：填本地 Gfriends 文件夹路径即可启用本地模式

## v1.0.0 (2026-06-11)

MDCx-DIY 首个正式发布版，基于Hazard804改良的mdcx项目制作，对前辈表示衷心感谢！！！

### 刮削引擎

- 40+ 网站爬虫（有码/无码/FC2/国产/欧美）
- 新增 libredmm 刮削源（可刮削dmm下架影片）
- GenericBaseCrawler 统一框架 + 上下文隔离
- 智能番号识别与自动分类（用户预定义）
- 异步并发架构（asyncio + 渐进式任务调度）
- curl-cffi 浏览器指纹伪装

### TMDB 演员

- 新增 NFO 女优 TMDB ID 功能
- NFO 女优 TMDB ID 写入（需在 NFO 设置勾选 + 填入 API Key）
- 日文原名搜索，日本出生地 + 女性/未指定性别 + 精确名匹配过滤
- 多候选按 popularity 排序取最优，失败不阻塞刮削
- 令牌桶限流器（3.5 req/s，突发 10），并发 3 查询
- TMDB adult 候选自动跳过，搜索候选数优化为 5
- actor_database.xlsx用于nfo增加tmdbid和演员映射功能，反向搜索 + 增量写入，已预置部分女优数据，后续随软件使用动态更新（新演员若TMDB有数据就在表中追加数据，表中演员若TMDB数据更新，表中相关数据会追加）
- 超链接一致性校验与自动修复

### Amazon 高清封面

- ASIN 条码识别 + 三层搜索策略
- 封面 poster 固定 1500 尺寸（平衡质量和大小）
- 新增Amazon ASIN 缓存功能，通过Excel 缓存（amazon_asin_database.xlsx）
- 缓存去重逻辑，保护高置信度数据
- ASIN 缓存Excel随软件使用动态追加（同个影片二次刮削时不用再去Amazon查找，直接用表中数据下载高清封面）

### 数据源迁移

- actor_mapping XML + TMDB 缓存合并为 actor_database.xlsx
- mapping_info.xml 迁移为 info_database.xlsx
- 内置 xlsx 数据库，支持表头冻结，筛选、超链接等，用户可自行编辑或通过超链接审查数据

### 代理与网络

- HTTP/SOCKS5 代理配置
- 新增"不使用代理"网站选择器：40+ 刮削源下拉快速选择，智能域名匹配
- 默认 api.tmdb.org 不走代理

### 元数据与媒体

- NFO 生成器，30+ 字段，兼容 Kodi/Emby/Jellyfin
- 多语言翻译（Google/Bing/百度/DeepL/DeepLX/LLM 六引擎）
- Jinja2 命名模板引擎
- OpenCV 人脸检测智能裁剪
- 海报/背景图/预告片自动获取
- 字幕管理与缺失检测
- Emby/Jellyfin 演员信息补全 + 头像同步

### 界面与工具

- PyQt6 桌面图形界面
- 命令行工具（crawl、gen_enums）
- 构建工具链（build、bump、changelog、check）

### 工程质量

- 70+ 个测试文件覆盖核心模块
- CI：ruff format + ruff check
- Release：macOS DMG + Windows EXE
- 新增29 篇技术文档（架构、模块、API、迁移指南等）
