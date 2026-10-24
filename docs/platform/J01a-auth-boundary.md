# J01-a 认证入口边界修复

日期：2026-10-24。状态：本地实现与验收完成；远程 CI 结果以对应提交的 GitHub Actions 为准。
基线：JobPilot main `db14811a0c5c1f9cd49c3ab764041438518cd442`。
工作区：`D:/code/jobpilot-j01a-auth`；分支：`codex/j01a-auth-boundary`。

## 行为变更

| 入口 | 修复后行为 |
|---|---|
| 注册已有用户名 | 无论是否有密码都返回 409，不修改密码、email、display_name 或启用状态 |
| 开发身份 | 默认关闭；仅 local/test 显式启用且提供非空 X-User-Name 时准入 |
| 无凭据请求 | 返回 401，不自动选择 demo |
| 错误 Authorization + 开发头 | 返回 401，不回退到开发身份 |
| 密码账号使用开发头 | 返回 401，要求密码登录 |
| 停用账号 | 开发头和 JWT 都拒绝，不通过注册重新激活 |
| 本地 API JWT | 必须包含 sub/exp；sub 为 users.id 可表示的规范正整数，exp 为有效数值；字段异常转为 401 |
| 服务配置 | local/test 之外的环境拒绝开发认证、debug、示例/短密钥及非 HS256 的本地算法 |

本地/test 仍允许明确 opt-in 的无密码开发账号访问，便于已有隔离测试；这不是账号归属证明，不能用于远程服务。APP_ENV 不会根据监听地址自动推断，对外部署必须显式配置服务环境。

`Settings` 对环境名称去空白并转小写，不认识的名称也按服务环境处理。签名密钥检查至少 32 字节并排除示例值，不能据此保证熵足够；部署须使用强随机密钥。Pydantic 错误显示隐藏输入，避免在配置异常中回显配置值。

`app.main` 最先加载配置再导入业务路由；独立进程测试确认不安全配置在导入 SQLAlchemy 前拒绝。认证头 scheme 大小写不敏感；空/非 Bearer/非法 token 均不能触发开发身份。

## 文件与边界

主要改动：`app/api/auth.py`、`app/api/deps.py`、`app/core/config.py`、`app/core/security.py`、`app/main.py`、`app/services/user_scope_service.py`。

测试：更新 `tests/test_auth_api.py`，新增 `tests/test_auth_config.py`；`tests/conftest.py` 增加隔离库账号准备与快照 fixture。现有测试环境继续显式开启受控测试身份，生产默认关闭。

根/后端 README 及前后端 `.env.example` 同步默认账号登录。前端原有实际配置不自动覆盖；使用 JWT 登录时设置 `VITE_AUTH_DEV_MODE=false`，仅本地演示时与后端一起开启。

没有新增依赖、改变锁文件、创建业务迁移或接入外部 OIDC。J01-b 仍负责 issuer+subject 映射与受托令牌，J01-c 负责有证明的旧账号绑定；J01 整包未完成。

## 本地验收

| 检查 | 结果 |
|---|---|
| 配置组合与提前拒绝启动 | 18 项通过 |
| 独立 B01 测试环境护栏 | 7 项通过 |
| 配置、认证 API、MCP 认证、用户作用域定向集 | 77 项通过 |
| 完整后端 pytest | **428 passed, 16 subtests passed**，54.33 秒 |
| 测试库迁移 | 全新 tmpfs PostgreSQL，成功至 e8f3a1c9d204 |
| diff/依赖 | git diff --check 通过；pyproject.toml / uv.lock 未变 |
| 资源清理 | 本刀测试容器及专用网络已移除 |

部分检查包含重叠用例，不相加宣传为独立测试总数。环境：Windows、Python 3.12.7、按项目锁文件 `uv sync --frozen`；未执行远程 CI 或前端构建（前端仅修改环境样例）。

测试重点包括：携带私有简历的无密码账号不能被同名注册认领，原账号快照不变；另一个合法 JWT 用户读取该简历返回 404。验证密码账号、停用账号、错误身份头、异常已签名 claims、缺少/过期 token 及合法 JWT 优先级。

首次启动顺序测试发现原 main 先导入路由，再读取配置，已前置配置加载并复验通过。Docker 初始未启动，启动就绪后才创建专用临时实例；没有连接业务数据库。

本次只修复入口边界，未改造旧 Assistant/领域任务生命周期；生产多用户平台仍须后续身份、任务及操作幂等验收。
