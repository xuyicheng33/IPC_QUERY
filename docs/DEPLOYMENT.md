# IPC_QUERY 云服务器部署手册

本文档面向希望将 IPC_QUERY 部署到云服务器（阿里云 / 腾讯云 / AWS / GCP / 华为云等）的用户。

默认以 Linux（Ubuntu 22.04+/Debian 12+）为例。

## 1. 部署方案选择

- 推荐：Docker Compose（隔离性强、迁移简单、升级回滚成本低）
- 备选：systemd + Python venv（适合不使用 Docker 的内网环境）

## 2. 方案 A：Docker Compose（推荐）

### 2.1 服务器准备

```bash
# Ubuntu / Debian
sudo apt-get update
sudo apt-get install -y ca-certificates curl git

# Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# 验证
docker --version
docker compose version
```

### 2.2 拉取代码并准备目录

```bash
git clone git@github.com:xuyicheng33/IPC_QUERY.git
cd IPC_QUERY

mkdir -p data/pdfs data
cp .env.example .env
```

### 2.3 配置 `.env`

至少确认以下字段：

```dotenv
PORT=8791
DATABASE_PATH=/app/data/ipc.sqlite
PDF_HOST_DIR=./data/pdfs
PDF_MOUNT_MODE=ro
IMPORT_MODE=auto
WRITE_API_AUTH_MODE=disabled
# WRITE_API_KEY=change-me-if-api-key-mode
LEGACY_FOLDER_ROUTES_ENABLED=true
LOG_LEVEL=INFO
LOG_FORMAT=json
```

配置建议：
- 只读检索服务：`PDF_MOUNT_MODE=ro` + `IMPORT_MODE=disabled` 或 `auto`
- 允许在线导入/删除：`PDF_MOUNT_MODE=rw` + `IMPORT_MODE=enabled` 或 `auto`
- 需要写接口鉴权：设置 `WRITE_API_AUTH_MODE=api_key` 并配置 `WRITE_API_KEY`
- 容器内的 `PDF_DIR` 固定为 `/app/pdfs`，无需手动填写。

### 2.4 首次启动

```bash
docker compose up -d --build
```

验证：

```bash
curl -sSf http://127.0.0.1:8791/api/health
curl -sSf http://127.0.0.1:8791/api/capabilities
```

### 2.5 常用运维命令

```bash
# 查看状态
docker compose ps

# 查看日志
docker compose logs -f ipc-query

# 重启
docker compose restart ipc-query

# 停止
docker compose down
```

## 3. 方案 B：systemd + Python（备选）

### 3.1 创建运行用户与目录

```bash
sudo useradd -r -m -d /opt/ipc-query -s /usr/sbin/nologin ipcquery
sudo mkdir -p /opt/ipc-query /var/lib/ipc-query/pdfs /var/lib/ipc-query/data
sudo chown -R ipcquery:ipcquery /opt/ipc-query /var/lib/ipc-query
```

### 3.2 安装项目

```bash
sudo -u ipcquery -H bash -lc '
  cd /opt/ipc-query && \
  git clone git@github.com:xuyicheng33/IPC_QUERY.git . && \
  python3 -m venv .venv && \
  . .venv/bin/activate && \
  pip install -U pip && \
  pip install -e ".[dev]" && \
  npm --prefix frontend install && \
  npm --prefix frontend run build
'
```

### 3.3 创建环境变量文件

创建 `/etc/ipc-query/ipc-query.env`：

```dotenv
DATABASE_PATH=/var/lib/ipc-query/data/ipc.sqlite
HOST=127.0.0.1
PORT=8791
PDF_DIR=/var/lib/ipc-query/pdfs
UPLOAD_DIR=/var/lib/ipc-query/pdfs
IMPORT_MODE=auto
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### 3.4 创建 systemd 服务

创建 `/etc/systemd/system/ipc-query.service`：

```ini
[Unit]
Description=IPC_QUERY Service
After=network.target

[Service]
Type=simple
User=ipcquery
WorkingDirectory=/opt/ipc-query
EnvironmentFile=/etc/ipc-query/ipc-query.env
ExecStart=/opt/ipc-query/.venv/bin/python -m ipc_query serve --db /var/lib/ipc-query/data/ipc.sqlite --pdf-dir /var/lib/ipc-query/pdfs --upload-dir /var/lib/ipc-query/pdfs --host 127.0.0.1 --port 8791
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

生效并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ipc-query
sudo systemctl status ipc-query
```

## 4. Nginx 反向代理与 HTTPS（按需）

Nginx 与 HTTPS 不是所有场景都必须，但在公网部署时强烈建议启用。

建议如下：
- 公网可访问（Internet 暴露）：建议使用 Nginx + HTTPS，应用仅监听 `127.0.0.1:8791`。
- 内网专线 / VPN 场景：可先不启用 Nginx，由应用直接监听内网地址与端口。
- 安全合规要求明确规定加密传输：必须启用 HTTPS。

示例 `/etc/nginx/conf.d/ipc-query.conf`：

```nginx
server {
    listen 80;
    server_name your-domain.example.com;

    location / {
        proxy_pass http://127.0.0.1:8791;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用 HTTPS（推荐 certbot）：

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example.com
```

## 5. 备份、升级与回滚

### 5.1 数据备份

SQLite 建议使用在线备份指令：

```bash
sqlite3 /path/to/ipc.sqlite ".backup '/path/to/backup/ipc-$(date +%F).sqlite'"
```

同时备份 PDF 原始目录（`data/pdfs`）。

### 5.2 升级流程（Docker）

```bash
git fetch --tags
git checkout <new-tag-or-branch>
docker compose up -d --build
docker compose ps
curl -sSf http://127.0.0.1:8791/api/health
```

### 5.3 回滚流程（Docker）

```bash
git checkout <previous-tag>
docker compose up -d --build
```

## 6. 上线检查清单

- `GET /api/health` 返回 `status=healthy`
- `GET /api/capabilities` 符合预期（导入功能开关）
- `GET /api/capabilities` 中 `directory_policy=single_level`
- 若启用写接口鉴权：`write_auth_required=true`
- 首页、搜索页、详情页、`/db` 页面均可访问
- 日志无连续报错，CPU/内存稳定
- 已配置数据库与 PDF 周期性备份

## 7. 常见问题

### 7.1 导入按钮灰化

检查：
- `PDF_MOUNT_MODE` 是否为 `rw`
- `IMPORT_MODE` 是否设置为 `enabled` 或 `auto`
- `GET /api/capabilities` 返回的 `import_reason`

### 7.1.1 写接口 401

检查：
- `WRITE_API_AUTH_MODE` 是否为 `api_key`
- 客户端是否发送了正确的 `X-API-Key`
- `WRITE_API_KEY` 是否在服务侧正确配置

### 7.1.2 目录接口兼容期说明

- Canonical 路由：`/api/folders`、`/api/folders/rename`、`/api/folders/delete`
- Legacy alias：`/api/docs/folder/create`、`/api/docs/folder/rename`、`/api/docs/folder/delete`
- legacy 路由响应会包含 `Deprecation: true` 与 `Sunset: 2026-06-30`
- 可通过 `LEGACY_FOLDER_ROUTES_ENABLED=false` 提前关闭 legacy 路由

### 7.2 `/pdf/...` 返回 404

检查：
- 数据库记录中的 `relative_path` 对应文件是否存在
- `PDF_DIR` 是否指向实际 PDF 根目录

### 7.3 启动时报权限错误

检查：
- 运行用户是否对数据库目录和 PDF 目录有读写权限
- 容器挂载目录的宿主机权限是否匹配
