# J01-c 有证明的旧账号绑定

状态：功能代码和隔离测试已实现，默认关闭。未交付绑定页面、Java BFF、无密码旧账号迁移、自助解绑、账号合并或换绑。真实身份源的启用验收尚未完成。

## 身份与权限规则

旧账号必须有密码且启用。每一步同时提供有效的本地 API Bearer 与外部受托 Bearer，并重新验证当前密码。服务端从本地 token 的 sub 获取目标账号，从外部已验证的 issuer+subject 获取外部身份；请求不能指定 user_id、username 或 email。开发头、同名/同邮箱、MCP token 均不能认领账号。

绑定使用 `identity.bind`，不接受 `resume.read` 代替。外部 token 的已验证 azp 必须在独立绑定白名单内，且映射为 platform。TiKi 的普通读取委派没有绑定权限；绑定接口没有注册为 Agent/MCP/A2A 工具。

`EXTERNAL_BINDING_ENABLED=false` 与 `EXTERNAL_BINDING_ALLOWED_CLIENTS=[]` 为默认值。启用需同时开启受托验证、配置非空且不重复的精确客户端白名单；白名单成员必须在 `DELEGATED_ACTOR_CLIENTS` 中映射到 platform。禁止通配符。客户端实际名称由部署配置，文档不假设已有平台客户端。

真实 IdP 尚需证明：专用 scope 可以签发、交换后不扩大授权、仅指定平台客户端可获得、tiki 无法获得，以及用户会话/在线停用符合 J01-b 的 Keycloak profile。HTTP 替身测试不能代替该验收；证据未取得时保持关闭。

## 两步接口

共同请求头：`Authorization: Bearer <本地 API token>`，`X-External-Authorization: Bearer <外部 token>`。凭据仅通过 TLS 传输，不放入 URL。禁止代理/应用记录这两个头和请求体。请求为 JSON；无 cookie 身份回退，不添加跨域通配配置。

| 方法与路径 | 请求体 | 成功结果 |
|---|---|---|
| POST `/api/auth/external-bindings/challenges` | password | 201：challenge_id、challenge_secret、expires_at、user_id、username、issuer、subject；此时没有映射或开户副作用 |
| POST `/api/auth/external-bindings/confirm` | challenge_id、challenge_secret、password、confirm=true（必须为 JSON 布尔值） | 200：status=bound、binding_id、user_id、issuer、subject、audit_id |

所有模型拒绝额外字段。验证错误返回固定 422 文案，不回显原始敏感输入。响应设置 `Cache-Control: no-store`。未知内部错误返回 500，只记录异常类型，不记录错误消息或请求凭据；实际排障结合部署层请求关联和数据库监控。

挑战 secret 使用 32 随机字节，仅在创建时返回；数据库仅保存 SHA-256 摘要。挑战有效期 5 分钟，绑定本地 user_id、local token 摘要、issuer、subject、client_id 和外部 session_id。确认必须为同一本地 token 和同一外部会话；同会话外部 token 可以刷新，但必须重新验证权限和在线状态。secret 比较使用常量时间比较。

调用方应向用户展示双方身份后发送显式确认。`confirm=true` 不被解释为服务器能证明真人点击；未来 BFF/页面不得将密码或确认权交给 Agent。

有效期内相同身份及凭据重复确认返回原成功回执，不重复写审计；挑战过期后返回 410。再次创建新挑战并确认已经存在的相同绑定，会生成该新确认对应的 already_bound 审计。响应不会签发本地 JWT/MCP token。

## 冲突、自动开户与解绑

数据库同时约束 `(issuer, subject)` 和 `(issuer, user_id)` 唯一。同一 issuer 内，一个本地用户只能绑定一个 subject；不同 issuer 的数据模型允许分别绑定，但当前配置仍只验证一个固定 issuer。

相同绑定可幂等确认；身份已属于其他账号、旧账号已被同 issuer 的其他 subject 绑定，一律 409，不返回对方账号信息、不覆盖映射、不移动业务资源。无密码旧账号不通过此接口设置密码或认领。

使用旧账号时应先绑定，再调用受托 `/api/internal/v1/identity/me`。该入口维持 J01-b 自动开户语义；挑战不预占身份，若并发自动开户先成功，则绑定确认冲突，即使新账号没有业务数据也不自动换绑。绑定先成功时，自动开户竞争者回滚新用户并读取旧账号映射。

没有解绑/换绑接口或删除映射脚本。删除映射会影响无密码用户的开发认证判断，不能作为撤销方案。紧急阻断应使用 IdP 用户/会话停用或本地用户停用，并保留映射；IdP 停用不会自动撤销本地 JWT，本地用户停用影响两种入口。该能力不代表后台任务授权撤销或全会话注销已实现。

## 事务、审计与限流

先独立短事务锁 User 行并提交尝试槽位，再在锁外执行外部 HTTP 验证和受限线程池中的 bcrypt。绑定密码超过 72 UTF-8 字节直接拒绝，不截断。业务事务重新锁 User 行检查启用状态和密码快照，按 User → Challenge 顺序锁行，再通过唯一约束/savepoint 裁决映射竞争。

每个本地用户滚动 5 分钟最多创建 5 次、确认 10 次；失败密码也占槽位。数据库持久化支持多个服务实例；超过限流返回 429 与 Retry-After。未认证流量的边缘防洪仍由部署负责，不宣称全站登录限流已实现。

映射、挑战成功状态、成功审计同事务提交。冲突终态先提交，再返回 409。未知 IntegrityError 不作为幂等成功处理。锁等待上限 3 秒、本地事务总预算 5 秒；提交前重查 token 和挑战期限，数据库时间使用 clock_timestamp。HTTPX 身份源验证沿用 J01-b 的分阶段超时，未持有业务事务。

新增三表 external_binding_challenges、external_binding_audits、external_binding_attempts；审计和尝试不存密码/原始 token/明文挑战 secret。审计只追加但不宣称对数据库管理员防篡改。暂不自动清理过期挑战和尝试记录，少量用户部署需监控规模，保留期另行制定。

在线状态只保证最近一次 introspection 结果；IdP 停用与本地提交之间没有跨库原子保证。

错误约定：401 认证失败；403 缺少权限/停用；404 功能关闭、挑战不存在或凭据不匹配；409 映射冲突；410 本人正确挑战已过期；422 脱敏格式错误；429 尝试过多；503 身份服务或可重试的数据库/锁故障；500 未知内部故障。

## 迁移与回滚

新增 Alembic revision `a41c98d72b60`，父 revision `f29b6a70d183`。迁移先检测存量 `(issuer,user_id)` 重复：发现即失败，不删除或挑选映射，不修改业务 owner。非空映射/挑战/审计/尝试阻止自动降级，避免丢失安全证据或降低现有约束。

部署顺序：完成存量检查与迁移 → 部署默认关闭的新代码 → 完成真实 IdP 启用验收 → 显式开启。真实数据库迁移需要部署时执行，本次只在 B01 隔离库验证。回滚先关闭入口并停止相关请求；有数据的降级属于单独受控恢复，不能把测试空库往返当作生产可直接降级。

## 验证方法与证据边界

沿用 B01 专用测试库，仓库根目录启动 `docker compose -f backend/compose.test.yaml up -d --wait`，设置 `.env.test.example` 所述 TEST_DATABASE_URL，执行 `uv --directory backend run python testing_environment.py migrate`，再执行 `uv --directory backend run pytest`。禁止回退业务 DATABASE_URL。

- `tests/test_external_binding.py`：双身份/密码证明、权限、挑战、重试、冲突、状态变化、限流与脱敏。
- `tests/test_external_binding_concurrency.py`：真实 PostgreSQL 独立连接与两个 engine 的唯一竞争、JIT 双向竞争、限流、审计回滚和锁超时。
- `tests/test_external_binding_migration.py`：临时 schema 内运行实际 revision，检测重复存量、空库往返与四类非空降级阻断；结束回滚整个 schema，不触碰 public 业务测试表。
- 原 J01-a/b 认证与用户隔离回归，以及完整后端测试继续执行。

本地具体测试数量和最终结果记录在本刀实施记录中；远程 CI 只以未来对应提交的运行结果为准。本地验收不等于已经提交、合并或启用真实绑定服务。
