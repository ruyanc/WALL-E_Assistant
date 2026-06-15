# WALL-E × 腾讯云 CloudBase 部署指南

> Phase 0：多台 **Windows / macOS** 电脑登录同一账号，同步待办、记事、提醒与番茄钟设置；不同账号之间派发与接收任务。

## 官方文档索引

| 主题 | 链接 |
| --- | --- |
| CloudBase 总览 | [docs.cloudbase.net](https://docs.cloudbase.net/) |
| HTTP API 概述 | [HTTP API 概述](https://docs.cloudbase.net/http-api/basic/overview) |
| HTTP API 快速开始 | [HTTP API 快速开始](https://docs.cloudbase.net/quick-start/http-api/introduce) |
| AccessToken | [AccessToken 说明](https://docs.cloudbase.net/http-api/basic/access-token) |
| 身份认证概述 | [身份认证概述](https://docs.cloudbase.net/authentication-v2/auth/introduce) |
| 管理登录方式 | [登录方式管理](https://docs.cloudbase.net/authentication-v2/auth/manage-login) |
| 短信验证码登录 | [短信验证码登录](https://docs.cloudbase.net/authentication-v2/method/sms-login) |
| 文档型数据库控制台 | [文档型数据库操作指南](https://cloud.tencent.com/document/product/876/46897) |
| 基础权限（四种预设） | [基础权限](https://docs.cloudbase.net/database/data-permission) |
| 安全规则（CUSTOM） | [安全规则](https://docs.cloudbase.net/database/security-rules) |
| NoSQL RESTful API | [NoSQL RESTful API](https://docs.cloudbase.net/http-api/nosql/nosql-restful-api) |
| 网关权限控制 | [网关权限控制](https://docs.cloudbase.net/authentication-v2/auth/auth-gateway) |
| 权限控制（角色） | [权限控制](https://docs.cloudbase.net/authentication-v2/auth/auth-control) |
| 用户登录 API | [auth-sign-in](https://docs.cloudbase.net/http-api/auth/auth-sign-in) |

---

## 0. 前置准备

### 0.1 地域与环境

- **文档型数据库**与 **短信验证码登录** 目前仅支持 **上海（`ap-shanghai`）** 地域，创建环境时务必选上海。
- 环境 **ID**（形如 `wall-e-d2gkz50u90bf68fa9`）即 WALL-E 客户端中的 **授权码**。
- 国内环境 API 根地址：`https://{envId}.api.tcloudbasegateway.com`；海外环境使用 `https://{envId}.api.intl.tcloudbasegateway.com`（WALL-E 默认国内域名）。

### 0.2 HTTP API / NoSQL 控制台配置（两层权限）

WALL-E 通过 **HTTP API** 访问身份认证与 **NoSQL 文档库**。CloudBase **没有**「文档型数据库里单独开启 NoSQL HTTP API」的开关，需理解 **两层权限**：

| 层级 | 控制什么 | 控制台在哪里配 | 配错了的表现 |
| --- | --- | --- | --- |
| **网关层** | 请求能否进入 API（能否调用接口） | **身份认证 → 权限控制**（网关策略） | `403`、`ACTION_FORBIDDEN` |
| **资源层** | 登录用户能读写哪些文档 | **文档型数据库 → 集合 → 权限设置**（`CUSTOM` 安全规则） | `401`、`DATABASE_PERMISSION_DENIED` |

参考：[网关权限控制](https://docs.cloudbase.net/authentication-v2/auth/auth-gateway)、[HTTP API 快速开始](https://docs.cloudbase.net/quick-start/http-api/introduce)

#### 0.2.1 网关层：为「注册用户」放行 HTTP API

手机号密码 / 短信登录成功的用户属于 **注册用户** 角色（非匿名）。

官方默认策略下，**注册用户** 对已登录后的 **数据模型 API（资源标识 `model`）** 通常为 ✅，NoSQL 路径 `/v1/database/...` 一般可直接使用。若客户端报 **403 / `ACTION_FORBIDDEN`**，再手动配置：

1. 打开 [云开发平台](https://tcb.cloud.tencent.com/dev) → **身份认证** → **权限控制**
2. 找到角色 **注册用户**，点 **配置权限**（或 **添加自定义策略**）
3. 资源类型选 **网关**
4. 在开放 API 列表中勾选与 **数据模型 / 文档型数据库** 相关的 HTTP API 策略（界面文案因版本而异）
5. 若无预设项，添加 **自定义策略**，示例（放行 NoSQL 文档库路径，允许 `POST`/`PUT` 等）：

```json
{
  "version": "1.0",
  "statement": [
    {
      "effect": "allow",
      "action": "model:tcloudbasegateway:*:/v1/database/*",
      "resource": "*"
    }
  ]
}
```

6. 保存后约 **3 分钟** 生效；建议用户退出 WALL-E 重新登录

登录、注册、发验证码等 **`/auth/v1/*`** 在登录前调用；若连登录都 403，检查 **所有用户** / 匿名相关网关策略，或临时用管理员角色策略对比排查。

#### 0.2.2 资源层：集合 + 安全规则 + 索引

网关放行后，还须完成 **§3** 中的配置（与 HTTP API 无关，但在同一部署流程中必做）：

1. 创建集合 `sync_records`、`user_profiles`、`task_assignments`
2. 每个集合 **权限设置 → 切换到安全规则 → `CUSTOM`**，粘贴对应 JSON（**勿用** PRIVATE 等预设）
3. 按 **§3.0.1** 配置索引

**不在控制台预建业务字段**；用户登录同步后客户端自动 `PUT` 文档。

#### 0.2.3 WALL-E 实际调用的接口一览

根地址：`https://{envId}.api.tcloudbasegateway.com`

| 模块 | 方法 | 路径示例 | 网关层 | 资源层 |
| --- | --- | --- | --- | --- |
| 发验证码 | `POST` | `/auth/v1/verification` | 登录前须可达 | — |
| 校验验证码 | `POST` | `/auth/v1/verification/verify` | 同上 | — |
| 登录/注册 | `POST` | `/auth/v1/signin`、`/auth/v1/signup` | 同上 | — |
| 刷新 Token | `POST` | `/auth/v1/token` | 注册用户 | — |
| 查用户 | `GET` | `/auth/v1/user/query` | 注册用户 | — |
| 查文档 | `GET` | `/v1/database/.../collections/{c}/documents?query=…&limit=N` | 注册用户 + `model` | 集合 `CUSTOM` 规则 |
| 新建文档 | `POST` | `.../collections/{c}/documents` | body: `{"data": […]}` | 同上 |
| 更新文档 | `PATCH` | `.../collections/{c}/documents` | body: `{"query": {…}, "data": {…}}` | 同上 |

请求头：`Authorization: Bearer {access_token}`、`x-device-id`、`Content-Type: application/json`。

### 0.3 免费额度

免费体验版约 **3000 资源点/月**，个人多设备同步通常足够。详见 [资源点价格文档](https://cloud.tencent.com/document/product/876/127357)。

---

## 1. 创建 CloudBase 环境

1. 打开 [CloudBase 控制台](https://console.cloud.tencent.com/tcb)
2. 创建 **免费体验版** 环境，地域选择 **上海**
3. 记录 **环境 ID**，作为分发给用户的 **授权码**

控制台顶部 **文档型数据库** 提供四个入口：**集合管理**、**数据模型**、**数据库设置**、**连接管理**。WALL-E 仅需 **集合管理**。

---

## 2. 开启身份认证

### 2.1 控制台配置

路径：**身份认证** → **登录方式**（云开发平台路径：`身份认证 / 登录方式`）

| 登录方式 | WALL-E 是否使用 | 说明 |
| --- | --- | --- |
| 用户名密码登录 | 是 | 手机号作用户名 + 密码登录 |
| 短信验证码登录/注册 | 是 | 验证码登录、新用户注册 |
| 匿名登录 | 否 | 无需开启 |
| 微信 / 邮箱等 | 否 | 按需 |

操作步骤：

1. 在登录方式列表中找到 **用户名密码登录**、**短信验证码登录**，点击 **启用**
2. 短信验证码可在同页调整发送频率（同号约 30 秒 1 次、日上限等）
3. 新用户可在客户端 **账号 → 新用户注册** 自助完成（手机号 + 密码 + 短信验证码），无需在控制台手动建用户
4. 也可在 **用户管理** 中手动创建：用户名使用手机号（CloudBase 格式 `+86 138xxxxxxxx`），并设置密码

参考：[管理登录方式](https://docs.cloudbase.net/authentication-v2/auth/manage-login)

### 2.2 手机号格式

WALL-E 客户端会将 `13800138000` 自动规范为 `+86 13800138000`。HTTP 请求中手机号须带国际区号，建议格式 `+86 13800138000`（区号与号码之间可有空格）。

### 2.3 HTTP 认证接口（WALL-E 实际调用）

根地址：`https://{envId}.api.tcloudbasegateway.com`

公共请求头：

| 头 | 说明 |
| --- | --- |
| `Authorization` | `Bearer {access_token}`（登录后） |
| `x-device-id` | 设备唯一 ID，客户端自动生成并持久化 |
| `Content-Type` | `application/json` |

| 操作 | 方法 | 路径 | 请求体要点 |
| --- | --- | --- | --- |
| 密码登录 | `POST` | `/auth/v1/signin` | `username`, `password` |
| 发送验证码 | `POST` | `/auth/v1/verification` | `phone_number`, `target`（`USER`=登录 / `ANY`=注册） |
| 校验验证码 | `POST` | `/auth/v1/verification/verify` | `verification_id`, `verification_code` |
| 验证码登录 | `POST` | `/auth/v1/signin` | `verification_token` |
| 注册 | `POST` | `/auth/v1/signup` | `phone_number`, `password`, `verification_token` |
| 刷新 Token | `POST` | `/auth/v1/token` | `grant_type=refresh_token`, `refresh_token` |
| 按手机号查用户 | `GET` | `/auth/v1/user/query?phone_number=...` | 派发时查找接收方 UID |

登录成功响应含 `access_token`、`refresh_token`、`expires_in`（默认约 **2 小时**）、`sub`（用户 UID）。客户端自动用 `refresh_token` 续期。

密码登录示例：

```http
POST https://{envId}.api.tcloudbasegateway.com/auth/v1/signin
Content-Type: application/json
x-device-id: {device_id}

{"username": "+86 13800138000", "password": "..."}
```

验证码注册/登录流程：

1. `POST /auth/v1/verification` → 获得 `verification_id`
2. `POST /auth/v1/verification/verify` → 获得 `verification_token`
3. 注册：`POST /auth/v1/signup`；登录：`POST /auth/v1/signin`（仅 `verification_token`）

---

## 3. 创建数据库集合

控制台路径：**文档型数据库** → **集合管理** → 选中集合 → 子页签 **文档列表 / 索引管理 / 权限设置**。

新建集合：左侧 **+** → 填写集合名 → 创建后进入 **索引管理**、**权限设置** 完成配置。

### 3.0 权限类型说明

CloudBase 控制台 **权限设置** 提供四种**基础权限**预设（按文档 `_openid` 判定「本人」）：

| 控制台选项 | 标识 | 权限 | 典型场景 |
| --- | --- | --- | --- |
| 读取全部数据，修改本人数据 | `READONLY` | 全体可读；仅创建者可写 | 评论、公开信息 |
| 读取和修改本人数据 | `PRIVATE` | 仅创建者可读写 | 个人设置、订单 |
| 读取全部数据，不可修改数据 | `ADMINWRITE` | 全体可读；用户不可写 | 商品信息 |
| 无权限 | `ADMINONLY` | 客户端无权限 | 后台流水 |

**WALL-E 请勿直接选用上述四种预设。** 原因：

1. 客户端通过 **HTTP + 用户名密码** 登录，身份对应 `auth.uid`，数据按 `user_id` / `assigner_id` / `assignee_id` 隔离。
2. 预设权限以 `_openid` 判定归属；部分 HTTP 场景下 `_openid` 行为与预设不一致，可能导致读不到自己的同步数据（「下次登录修改全部丢失」）。
3. `task_assignments` 需要派发方与接收方共同读写同一文档，无预设可满足。

**正确做法**：在 **权限设置** 页点击 **切换到安全规则**，选择 **自定义安全规则（`CUSTOM`）**，粘贴下文 JSON。参考：[安全规则](https://docs.cloudbase.net/database/security-rules)、[控制台权限设置说明](https://cloud.tencent.com/document/product/876/46897)。

| 集合 | 能否用预设 | 应选 |
| --- | --- | --- |
| `sync_records` | 否（按 `user_id` 隔离） | `CUSTOM` |
| `user_profiles` | 否（登录用户须全员可读） | `CUSTOM` |
| `task_assignments` | 否（双方须读写） | `CUSTOM` |

安全规则要点（官方说明）：

- 规则为 JSON：`read` / `write` 等字段为布尔值或表达式字符串
- 内置变量：`auth`（登录用户，含 `auth.uid`）、`doc`（文档字段）、`now`（时间戳）
- 查询条件须与安全规则一致；使用 `doc.字段名` 时，查询 filter 应包含对应字段

### 3.0.1 索引配置（唯一 / 非唯一）

控制台 **索引管理** → **新建索引** 时需选择是否 **唯一**。原则：**只有「一个值对应一条文档」时才选唯一**；同一用户/同一手机号的多条业务记录必须用 **非唯一**。

| 集合 | 索引字段 | 唯一？ | 说明 |
| --- | --- | --- | --- |
| `sync_records` | `user_id` + `updated_at`（复合，均升序） | **非唯一** | WALL-E 推荐，加速按用户拉取增量 |
| `sync_records` | `_openid`（系统可能显示 `_openid_1`） | **非唯一** | 系统默认索引；**WALL-E 可删除**（见下），不影响同步 |
| `sync_records` | `updated_at`（单字段） | **非唯一** | 已有 `user_id + updated_at` 复合索引时可不建 |
| `user_profiles` | `phone`（升序） | **唯一** | 一个手机号对应一条 profile |
| `user_profiles` | `phone_digits`（升序） | 非唯一（可选） | 按本地号码查询时的备用索引 |
| `task_assignments` | `assigner_id` + `updated_at` | **非唯一** | 派发方拉取自己的任务 |
| `task_assignments` | `assignee_id` + `updated_at` | **非唯一** | 接收方拉取派给自己的任务 |

勿对 `sync_records` 的 `_openid`、`updated_at` 或 `user_id + updated_at` 设 **唯一**，否则第二条相同值的文档会写入失败（`DATABASE_DUPLICATE_WRITE`）。文档 `_id` 由数据库保证唯一，无需再建唯一索引。

**关于系统默认 `_openid_1` 索引**：CloudBase 新建集合时常自动创建。WALL-E 客户端与安全规则均按 `user_id` / `auth.uid` 工作，**不按 `_openid` 查询**，删除该索引 **不会影响** WALL-E 同步与派发。保留也无害（须为 **非唯一**）。若控制台允许删除，可删；若禁止删除或删除后自动重建，保留即可。务必自行建好 **`user_id + updated_at` 非唯一复合索引**。

### 3.0.2 控制台如何填写「字段 1 / 字段 2」

复合索引在控制台里通常是 **多行「索引字段」**，第一行即 **字段 1**，第二行即 **字段 2**（有的界面标为「索引键 1」「索引键 2」）。**字段名须与 WALL-E 写入的 JSON 键名完全一致**（区分大小写，无多余空格）。

**通用操作步骤**

1. **文档型数据库** → 左侧点集合名（如 `task_assignments`）
2. 上方切到 **索引管理**
3. 点 **新建索引**（或 **添加索引**）
4. 在 **索引字段** 区域：
   - **第一行（字段 1）**：在 **字段名** 输入框手写键名 → **排序** 选 **升序**（或 `1` / 向上箭头）
   - 点 **添加字段** / **+** → 出现 **第二行（字段 2）**：再填字段名 → 同样选 **升序**
5. **唯一索引**：选 **否** / 不勾选（WALL-E 三个集合的复合索引均 **非唯一**）
6. **索引名称**：可留空自动生成，或填便于识别的名称（如 `assigner_id_updated_at`）
7. 点 **确定** / **创建**

若界面只有 **一个** 字段输入框，先填字段 1 后点 **添加字段** 才会出现字段 2；不要只建单字段索引代替复合索引。

**各集合填写对照表**

| 集合 | 字段 1（字段名 → 排序） | 字段 2（字段名 → 排序） | 唯一 |
| --- | --- | --- | --- |
| `sync_records` | `user_id` → 升序 | `updated_at` → 升序 | 否 |
| `user_profiles` | 仅单字段：`phone` → 升序 | （无需字段 2） | **是** |
| `user_profiles`（可选） | `phone_digits` → 升序 | （单字段索引） | 否 |
| `task_assignments`（索引 A） | `assigner_id` → 升序 | `updated_at` → 升序 | 否 |
| `task_assignments`（索引 B） | `assignee_id` → 升序 | `updated_at` → 升序 | 否 |

`task_assignments` 须 **分别新建两次索引**（先建 A，再建 B），不能在一次表单里混填四个字段。

**字段名不要填错**

| 正确 | 错误示例 |
| --- | --- |
| `assigner_id` | `assignerId`、`Assigner_id` |
| `assignee_id` | `assigneeId` |
| `updated_at` | `updatedAt`、`update_at` |
| `user_id` | `userId`、`uid` |

参考：[索引管理官方说明](https://docs.cloudbase.net/database/data-index)

### 3.1 `sync_records`（个人数据同步）

1. 新建集合 **`sync_records`**
2. **索引管理** → 新建 **复合索引**：`user_id`（升序）、`updated_at`（升序），选 **非唯一**（见 §3.0.1）
3. **权限设置** → **切换到安全规则** → `CUSTOM`，粘贴：

```json
{
  "read": "auth != null && doc.user_id == auth.uid",
  "write": "auth != null && (doc.user_id == auth.uid || doc.user_id == null)"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `_id` | string | `{user_id}_{collection}_{record_id}`（按账号隔离） |
| `user_id` | string | CloudBase 用户 UID（客户端写入并用于过滤） |
| `record_id` | string | 业务 UUID |
| `collection` | string | `todo` / `note` / `reminder` / `settings` / `contact` |
| `payload` | object | 完整业务数据 |
| `updated_at` | number | Unix 时间戳（秒） |
| `deleted` | bool | 软删除 |

> **字段无需在控制台手动创建。** CloudBase 文档型数据库无固定表结构，上表仅为 WALL-E 客户端写入的 JSON 字段说明。你只需：① 新建空集合 `sync_records`；② 配置索引与安全规则；③ 用户在客户端登录并同步后，文档会自动生成。不必使用「数据模型」预定义字段，也不必在控制台手动添加文档。

### 3.2 `user_profiles`（跨账号派发：手机号 → 用户 ID）

1. 新建集合 **`user_profiles`**
2. **索引管理** → `phone`（升序，**唯一**）；可选 `phone_digits`（升序，**非唯一**）
3. **权限** → `CUSTOM`：

```json
{
  "read": "auth != null",
  "write": "auth != null && (doc.user_id == auth.uid || doc.user_id == null)"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `user_id` | string | CloudBase 用户 UID |
| `phone` | string | 规范手机号 `+86 138...` |
| `phone_digits` | string | 本地号码位（查询用） |
| `updated_at` | number | 更新时间 |

> **字段无需在控制台手动创建**；首次登录后客户端自动写入。索引须将 `phone` 设为 **唯一**。

用户 **首次登录** WALL-E 时会自动 upsert 自己的 profile。派发前，接收方须至少登录一次。按手机号查找用户时，客户端优先调用 Auth `user/query`，再回退查询本集合。

### 3.3 `task_assignments`（跨账号任务）

1. 新建集合 **`task_assignments`**
2. **索引管理** → 新建两条复合索引（操作见 **§3.3.1**），均选 **非唯一**
3. **权限** → `CUSTOM`：

```json
{
  "read": "auth != null && (doc.assigner_id == auth.uid || doc.assignee_id == auth.uid)",
  "write": "auth != null && (doc.assigner_id == auth.uid || doc.assignee_id == auth.uid || doc.assigner_id == null)"
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | string | 任务 UUID |
| `title` | string | 标题 |
| `status` | string | `pending` / `accepted` / `rejected` / `completed` / `cancelled` |
| `priority` | number | 0 高 / 1 中 / 2 低 |
| `assigner_id` / `assignee_id` | string | 双方 UID |
| `assigner_phone` / `assignee_phone` | string | 展示用手机号 |
| `updated_at` | number | 增量同步游标 |

> **字段无需在控制台手动创建**；派发/接受任务时客户端自动写入。索引均选 **非唯一**。

#### 3.3.1 `task_assignments` 复合索引设置步骤

需建 **两条** 复合索引；控制台填写方式见 **§3.0.2**。下面为每条索引的具体取值：

**索引 A（我派出的）**：字段 1 = `assigner_id` 升序，字段 2 = `updated_at` 升序，**非唯一**

**索引 B（派给我的）**：字段 1 = `assignee_id` 升序，字段 2 = `updated_at` 升序，**非唯一**

完成后索引列表中应至少有上述两条（另可能有系统默认 `_openid_1`，可保留或删除，与 WALL-E 无关）。

**勿**将 `assigner_id`、`assignee_id` 或 `updated_at` 单独设为 **唯一**。

### 3.4 NoSQL HTTP API 说明与接口

控制台配置见 **§0.2**（网关 + 集合安全规则）。本节仅列 WALL-E 使用的路径与错误码。

路径前缀：

```text
https://{envId}.api.tcloudbasegateway.com/v1/database/instances/(default)/databases/(default)/collections/{collection}
```

| 操作 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 条件查询 | `GET` | `.../documents?query={JSON}&limit=N` | `query` 须为安全规则子集（如 `user_id`、`assigner_id`） |
| 新建文档 | `POST` | `.../documents` | body: `{"data": [{ "_id": "…", …字段… }]}` |
| 更新文档 | `PATCH` | `.../documents` | body: `{"query": {"_id":"…","user_id":"…"}, "data": {…}}` |

> **勿用**旧版 `documents:find`（POST）或按文档 ID 的 `PUT`：在 `tcloudbasegateway` 上会返回无效参数或静默失败。WALL-E 客户端已改用上述接口。

常见错误码（[NoSQL RESTful API](https://docs.cloudbase.net/http-api/nosql/nosql-restful-api)）：

| 错误码 | HTTP | 含义 | 先查哪一层 |
| --- | --- | --- | --- |
| `ACTION_FORBIDDEN` 等 | 403 | 网关未放行 HTTP API | **§0.2.1 网关层** |
| `DATABASE_PERMISSION_DENIED` | 401 | 集合安全规则拒绝 | **§3 资源层 `CUSTOM`** |
| `DATABASE_COLLECTION_NOT_EXIST` | 404 | 集合不存在 | 创建集合 |
| `DOCUMENT_NOT_FOUND` | 404 | 文档不存在 | 正常（部分查询） |
| `DATABASE_DUPLICATE_WRITE` | 409 | 唯一索引冲突 | **§3.0.1** 索引是否误设唯一 |
| `INVALID_PARAM` | 400 | 参数无效 | 检查 filter / 文档体 |

---

## 4. 配置 WALL-E 客户端

打开控制面板 → **☁️ 账号** 页（中文界面工作台名称为 **瓦力桌面助手**）：

1. 在 **授权码** 输入框填入环境 ID，点击 **保存授权码**
2. 输入 **手机号** 与 **密码**（或验证码 / 新用户注册），点击 **登录并同步**

授权码保存在 `%APPDATA%\WALL-E\settings.json` 的 `cloudbase_env_id` 字段。

高级配置（优先级更高）：

- 环境变量 `WALLE_CLOUDBASE_ENV_ID`
- `%APPDATA%\WALL-E\sync_config.json` 中的 `cloudbase_env_id`

---

## 5. 使用方式

### 5.1 多设备同账号同步

1. 在两台（或多台）Windows / macOS 电脑安装/运行 WALL-E
2. 填写相同 **授权码**，用 **同一手机号** 登录
3. 待办/记事/提醒/番茄钟设置自动合并（LWW 冲突策略）
4. 本地变更约 4 秒后自动上传；每 15 分钟定时同步

### 5.2 跨账号任务派发

1. 账号 A、B 均填写 **授权码** 并各登录一次（写入 `user_profiles`）
2. 账号 A → 待办 → **我派出的**：填写 B 的手机号（或昵称）、任务标题、可选 **任务说明** → **派发任务**
3. 账号 B → **派给我的**（分区：尚未接受 / 已经接受 / 已经回退 / 已撤回）：**接受/拒绝**（须填理由）；已接受可 **完成**
4. A 可在 **我派出的** 对 pending/accepted 任务 **撤回**（须填理由）
5. 状态变更时桌面瓦力气泡通知；Android 系统通知并可跳转待办子页
6. **接受后的协作任务不会写入个人待办**；已完成任务在 **已完成归档** 页统一归档

桌面端：已接受「派给我的」显示为瓦力 **左侧信封**，「我派出的」为 **右侧旗子**，点击直达子页。

本地缓存：`%APPDATA%\WALL-E\assignments.json`（macOS / Android 为各自数据目录）

### 5.3 待办页与同步控制

- 子标签：**个人待办** · **派给我的** · **我派出的** · **已完成归档**
- 待办页显示 **同步状态** 与 **重试同步**（登录且未暂停时可用）
- 账号页：**立即同步**、**暂停自动同步**（`settings.json` 的 `sync_paused`）、联系人昵称
- 本地修改约 **4 秒** 后自动上传；退出程序时保存本地数据并快速结束，**不**长时间阻塞等待网络

### 5.4 切换账号与隐私隔离

- **退出登录** 会清除本地会话，并清空待办/记事/提醒/派发缓存、联系人昵称与可同步设置的本地副本，再从云端拉取当前账号数据。
- **直接登录另一账号**（未先退出）时，若 `user_id` 变化，同样会清空上述本地数据后再同步。
- 云端个人数据依赖 `sync_records` 自定义规则（`doc.user_id == auth.uid`）；**切勿**将读规则设为 `true` 或选用「读取全部数据」类预设。
- `user_profiles` 对任意登录用户可读（用于按手机号查找派发对象）；不包含待办正文，但会暴露已注册手机号映射。

### 5.5 工作台标题

| 状态 | 中文界面 | 英文界面 |
| --- | --- | --- |
| 未登录 | 瓦力桌面助手 | WALL-E Assistant |
| 已登录 | `{手机号}的瓦力桌面助手` | `{phone}'s WALL-E Assistant` |

---

## 6. 本地文件

路径：`%APPDATA%\WALL-E\`

| 文件 | 说明 |
| --- | --- |
| `settings.json` | 含 `cloudbase_env_id` |
| `auth.json` | 登录 token（不含密码） |
| `todos.json` 等 | 离线业务数据 |
| `sync_meta.json` | 上次同步时间、所属 `user_id`、设备 `device_id` |
| `assignments.json` | 派发任务本地缓存 |
| `contact_nicknames.json` | 联系人昵称（切换账号时清空） |

---

## 7. 仍使用 Supabase（可选）

若 `sync_config.json` 中设置 `backend: "supabase"` 并填写 URL/Key，可继续使用 Supabase 后端（见 `GUIDE/sync/supabase_schema.sql`）。

---

## 8. 故障排查

| 现象 | 可能原因 |
| --- | --- |
| 「请先填写授权码」 | 账号页未保存授权码 |
| 401 / `DATABASE_PERMISSION_DENIED` | 集合未设 `CUSTOM` 规则，或误用 `PRIVATE` 等预设 | **§3 资源层** |
| 403 / `ACTION_FORBIDDEN` | **注册用户** 网关未放行 NoSQL HTTP API | **§0.2.1 网关层** |
| 404 / 集合不存在 | 未创建对应集合 |
| 手机号或密码错误 | CloudBase 用户未创建或用户名非 `+86` 手机号格式 |
| 短信发送失败 / 地域不支持 | 环境不在 **上海** 地域 |
| 未找到该手机号用户 | 接收方尚未用 WALL-E 登录过一次 |
| 登录无反应 / 退出后无法换号 | 使用最新客户端；先退出再登录；完全退出进程后重试 |
| 退出时程序未响应 | 旧版会阻塞等待同步；升级至最新版后退出应秒退 |
| 派发失败 | 查看弹窗；确认授权码一致、对方已登录 |
| 一台有数据、另一台为空 | 第二台登录后点「立即同步」 |
| `DATABASE_DUPLICATE_WRITE` | 误将 `_openid`、`updated_at` 等设为 **唯一** 索引，导致无法写入第二条相同值文档 |
| `EXCEED_REQUEST_LIMIT` | 请求配额超限，稍后重试或升级套餐 |

Token 刷新：`access_token` 约 2 小时有效，客户端自动用 `refresh_token` 续期。

---

## 9. 相关代码

| 模块 | 路径 |
| --- | --- |
| CloudBase HTTP 客户端 | `walle/sync/cloudbase_client.py` |
| 任务派发 | `walle/sync/assignment_manager.py` |
| 同步引擎 | `walle/sync/engine.py` |
| 账号 UI | `walle/control_panel.py` |
| 派发方案 | `GUIDE/ToDoList/跨账号任务派发方案.md` |
| 同步方案 | `GUIDE/ToDoList/跨平台账号同步方案.md` |
| 验证脚本 | `scripts/verify_sync_login_dispatch.py` |

---

## 10. 开发者验证

```powershell
.\.venv\Scripts\python.exe scripts/verify_sync_login_dispatch.py
.\.venv\Scripts\python.exe scripts/verify_sync_login_dispatch.py --live
```

打包安装：

```powershell
.\build.bat
.\install.bat silent
```

清理构建缓存（保留 `dist/WALL-E.exe`、`.msi`）：`clean_build_artifacts.bat`。详见 [BUILD_ARTIFACTS.md](../BUILD_ARTIFACTS.md)。

---

*最后更新：2026-06-15*
