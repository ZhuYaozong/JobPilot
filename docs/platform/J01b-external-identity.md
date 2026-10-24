# J01-b 外部身份映射与受托令牌验证

日期：2026-10-24。状态：本地实现与验收完成；远程 CI 结果以对应提交的 GitHub Actions 为准。
基线：JobPilot main `371bd20500bccb585ab532b8d5e7d03dfbd402a0`。
工作区：`D:/code/jobpilot-j01b-identity`；分支：`codex/j01b-external-identity`。

## 已实现

- `external_identities` 使用 `(issuer, subject)` 唯一约束、指向 `users.id` 的外键及 user_id 索引。
- `resolve_external_user` 以短事务和 savepoint 原子创建用户与映射。唯一冲突仅处理指定的身份唯一约束，回滚竞争者的开户，再读取胜出记录；不吞掉其他数据库错误。
- 首次访问创建随机 `ext_<uuid>` 账号，不采用 token 的用户名、姓名或邮箱关联旧账号，email/password 均不复制。
- 独立 `GET /api/internal/v1/identity/me` 接口使用 `DelegatedIdentityDep`，返回经验证的 issuer、subject、actor、scope 和本地用户。首次访问允许写入身份元数据，不写简历等业务资源。
- RS256 验签固定 issuer/JWKS/audience；验证 sub、exp、iat、nbf（存在时）、azp、typ、用户会话 sid、preferred_username 和 resume.read。
- 每次请求在线 introspection，要求 active 严格为 true，sub/sid/username 与已验签内容一致；再次确认未过期。无在线放行缓存，失败不降级。
- JWKS 最长缓存 300 秒，首次未知 kid 可刷新，额外陌生 kid 刷新限频五秒；不跟随重定向或 token 头 jku/x5u。失败不复用过期缓存。响应上限 128 KiB，RSA 长度 2048–8192 位。
- 本地停用账号拒绝；开发头无法进入有外部身份映射的账号。本地 JWT、MCP 及原业务资源 owner 校验继续独立工作。

## 配置与部署顺序

默认 `DELEGATED_AUTH_ENABLED=false`，身份确认入口返回 404，不进行网络核验或开户。

先按已有部署流程备份并应用 Alembic head，再配置固定身份源和资源端 introspection 凭据，最后启用外部认证。例如（地址和密钥均为配置示意）：

```dotenv
DELEGATED_AUTH_ENABLED=true
DELEGATED_ISSUER=https://identity.example.invalid/realms/platform
DELEGATED_JWKS_URL=https://identity.example.invalid/realms/platform/protocol/openid-connect/certs
DELEGATED_INTROSPECTION_URL=https://identity.example.invalid/realms/platform/protocol/openid-connect/token/introspect
DELEGATED_CLIENT_ID=jobpilot
DELEGATED_CLIENT_SECRET=<由受保护配置注入>
DELEGATED_AUDIENCE=jobpilot
DELEGATED_ACTOR_CLIENTS={"tiki":"tiki"}
DELEGATED_TIMEOUT_SECONDS=3
DELEGATED_JWKS_CACHE_SECONDS=300
DELEGATED_MAX_LIFETIME_SECONDS=600
```

配置要求三个地址位于同一 HTTPS origin 和 issuer 路径范围，无用户信息/query/fragment；不允许请求决定地址。TLS 使用系统信任链且 `trust_env=false`，此实现不读取继承代理。超时配置用于 HTTPX 网络阶段。SecretStr 隐藏 introspection 密钥的常规 repr，但部署者仍须妥善保存配置。

受托令牌的固定 provider profile 沿用 B03 的 Keycloak 路径：用户 token 保留 sub，azp 映射受控 actor，typ=Bearer，具有用户会话 sid 及 preferred_username；在线响应保留对应 sub/sid/username。缺失或不匹配会拒绝。服务账号的无会话形态及 `service-account-` 用户名均拒绝；这不是对任意 OIDC 提供方或任意管理员重写 mapper 的通用用户类型推断，生产需保持该 profile 并核对真实 IdP 配置。普通业务用户若使用保留的 service-account- 前缀也会被拒绝。

IdP 必须允许 jobpilot 资源客户端 introspect 其 audience 的 token。将所有未知 token 发去 introspection 不是替代验签的方案，本实现先做本地验签和声明检查。身份源返回 inactive 为 401，缺少所需 scope 为 403，超时/错误/无效 JSON/JWKS 为 503；不回显 token、私钥或密钥。

本次没有新增生产依赖，`pyproject.toml` 和 `uv.lock` 未变；没有修改用户实际 `.env`。

## 迁移与回滚

新 revision：`f29b6a70d183`，父 revision：`e8f3a1c9d204`。仅新建表和索引，不回填、重命名或认领历史用户。

空身份表允许 downgrade；已有任何映射时明确拒绝自动 downgrade，避免静默丢失账号关联。启用后需要备份映射并制定受控回滚方案，不能删除映射后让用户重试自动开户来“恢复”原归属。用户和业务表不由该 downgrade 删除。

临时库实测：非空降级被拒且映射未变；在仅有测试数据的实例内将映射备份到内存、清空测试映射后降级和升级，users/resumes 数量不变，再恢复映射并核对一致。此动作未在业务数据库执行。

## 验收结果与复现

环境：Windows、Python 3.12.7，`uv sync --frozen`，B01 专用 tmpfs PostgreSQL/pgvector。

| 检查 | 结果 |
|---|---|
| 原配置校验回归 | 18 项通过 |
| 身份/原认证/MCP/作用域定向集 | 162 项通过（随后补充的两项也纳入下述完整回归） |
| 完整后端 pytest | **515 passed, 16 subtests passed**，66.93 秒 |
| 新迁移及往返 | 升级成功，非空拒绝降级，空表降级/升级及原数据保留通过 |
| 并发开户 | 两个独立事务经 barrier 同时读到空映射，唯一冲突后只留一个用户和一条映射 |
| 资源隔离 | 同名/同邮箱不关联旧账号，不同 issuer 相同 sub 不合并；两个映射用户的简历 owner 校验通过 |

定向测试命令（先按 B01 启动专用测试库并迁移）：

```powershell
$env:TEST_DATABASE_URL = 'postgresql+asyncpg://jobpilot_test:disposable-test-only@127.0.0.1:35432/jobpilot_test'
uv --directory backend run pytest tests/test_delegated_auth.py tests/test_external_identity.py tests/test_auth_config.py tests/test_auth_api.py tests/test_mcp_auth.py tests/test_user_scope_and_list_rules.py
uv --directory backend run pytest
```

测试真实执行 RSA 签名/验签、HTTPX 请求组装以及 PostgreSQL 事务和唯一约束；身份源 HTTP 使用 respx 替身，不连接真实 Keycloak。本刀没有宣称新增生产代码已通过真实 IdP 部署联调。首次两个配置测试失败来自测试继承环境的 dict 合并和非唯一占位文本断言，修正后完整回归通过。

## 后续边界

- J01-c 才提供有归属证明的旧账号绑定；本刀没有绑定接口。
- J04/J07 使用受托依赖接入领域任务/技能，并校验平台 principal 与本地资源、任务、委派及 grant 的绑定；不能把请求中的 principal_id 当成映射依据。
- 本刀只返回本地用户和可信 issuer/subject，不自行生成或猜测平台 principal_id。
- 现有业务 API 仍使用本地认证依赖，不因启用本功能就接受外部令牌。身份确认接口不签发本地 JWT 或 MCP token。
- scope 只决定受托入口权限，不代替资源 owner、精确操作授权、预算或持久任务约束。
- 在线验证是当前请求时刻的状态检查，后续后台任务执行和续期须重新核验；令牌及 introspection 凭据不进入图状态或数据库映射表。
- 正常 JWKS 换钥不等于紧急密钥撤销。在线验证不可用时暂停访问，不能切换全权服务账号。

参考：[Keycloak 用户/服务账号与令牌状态说明](https://www.keycloak.org/docs/latest/server_admin/index.html)、[RFC 7662](https://datatracker.ietf.org/doc/html/rfc7662)。生产行为以固定 provider profile 的实际接入验收为准。
