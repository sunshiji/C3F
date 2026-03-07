# 自然场景文种识别系统 (C3F)

> Natural Scene Text Language Recognition System

基于 OCR + 语种检测的自然场景文字识别网站，支持图像上传，自动识别图像中文字的语种类别。

---

## 功能特性

- 🖼️ **图像上传识别**：拖放或点击上传图片，自动 OCR + 语种分类
- 🌍 **多语种支持**：中文、英文、日文、韩文、阿拉伯文、法文等 20+ 种语言
- 📊 **可视化仪表盘**：识别统计、趋势图、语种分布图
- 🗂️ **历史记录**：查询、筛选、删除识别记录
- 👥 **用户管理**：管理员可创建/禁用用户
- 🔒 **登录鉴权**：Session + localStorage 双重验证

---

## 项目结构

```
C3F/
├── frontend/           # HTML 原型（Tailwind CSS + FontAwesome）
│   ├── login.html      # 登录页
│   ├── index.html      # 主框架（侧边栏 + iframe）
│   ├── home.html       # 仪表盘
│   ├── upload.html     # 图像识别页
│   ├── history.html    # 历史记录页
│   └── settings.html   # 系统设置页
├── backend/            # Python Flask 后端
│   ├── app.py          # 主应用
│   ├── config.py       # 配置文件
│   └── requirements.txt
├── database/
│   └── schema.sql      # MySQL 8 建表脚本
└── deploy/
    ├── environment.yml     # Conda 环境定义
    ├── nginx.conf          # Nginx 反向代理配置
    ├── start.sh            # 一键部署脚本（Conda）
    └── restart_backend.sh  # 后端快速重启脚本
```

---

## 快速部署（Ubuntu 服务器，无 sudo，使用 Conda）

> **环境说明**
> - Conda 安装路径：`/home/szh/anaconda3`
> - 项目部署路径：`/home/szh/system/C3F`
> - 不需要 `sudo` 权限，**不需要 MySQL**
> - 数据库使用 SQLite（内置于 Python，无需安装任何数据库服务）
> - 服务器无法使用代理
> - 后端通过用户级 systemd 管理，前端由 Flask 直接托管（无需 Nginx）
> - 访问端口：**5000**

### 1. 克隆代码到服务器

```bash
ssh szh@10.109.119.208
mkdir -p /home/szh/system
cd /home/szh/system
git clone <repo_url> C3F
```

### 2. 一键部署

```bash
cd /home/szh/system/C3F
chmod +x deploy/start.sh
bash deploy/start.sh
```

脚本自动完成：目录创建 → Conda 环境创建（禁用代理）→ 用户级 systemd 服务注册并启动。  
**数据库无需任何配置**：应用首次启动时自动创建 SQLite 文件 `backend/c3f.db` 并写入初始账号。

> **注**：如需系统重启后服务自动恢复（注销后保持运行），
> 需请管理员执行一次：`loginctl enable-linger szh`

### 3. 手动部署（分步）

#### 数据库

无需任何配置。SQLite 数据库文件（`backend/c3f.db`）在 Flask 后端**首次启动时自动创建**，  
默认账号也会自动写入。若需自定义 DB 文件路径：

```bash
DB_PATH=/path/to/custom.db /home/szh/anaconda3/envs/c3f/bin/python backend/app.py
```

#### 创建 Conda 环境（禁用代理）

```bash
# 禁用代理，避免无代理服务器时请求超时
/home/szh/anaconda3/bin/conda config --set proxy_servers.http  ""
/home/szh/anaconda3/bin/conda config --set proxy_servers.https ""

# 创建 conda 环境
/home/szh/anaconda3/bin/conda env create -n c3f -f deploy/environment.yml --no-default-packages

# 安装 pip 依赖（禁用代理）
/home/szh/anaconda3/envs/c3f/bin/pip install --no-proxy -r backend/requirements.txt
```

#### 启动后端

```bash
# 使用 conda 环境的 python 直接运行（不需要 conda activate）
/home/szh/anaconda3/envs/c3f/bin/python backend/app.py
```

#### 注册用户级 systemd 服务（无需 sudo）

```bash
mkdir -p ~/.config/systemd/user
cp deploy/c3f.service.example ~/.config/systemd/user/c3f.service   # 参考 deploy/start.sh 中的模板
systemctl --user daemon-reload
systemctl --user enable c3f
systemctl --user start c3f
```

#### （可选）通过 Nginx 代理到端口 80

如需通过标准 80 端口对外提供服务，请联系管理员将 `deploy/nginx.conf` 应用到系统 nginx：

```bash
# 管理员执行：
sudo cp /home/szh/system/C3F/deploy/nginx.conf /etc/nginx/sites-available/c3f
# 将 nginx.conf 中的 listen 8080 改为 listen 80
sudo ln -s /etc/nginx/sites-available/c3f /etc/nginx/sites-enabled/c3f
sudo nginx -t && sudo systemctl reload nginx
```

---

## 访问

| 地址 | 说明 |
|------|------|
| `http://10.109.119.208:5000/` | 网站入口（Flask 直接托管） |
| `http://10.109.119.208:5000/login.html` | 登录页 |
| `http://10.109.119.208:5000/api/...` | 后端 API |

**默认账号**

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin  | admin123 | 管理员 |
| user1  | user123  | 普通用户 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | HTML5 + Tailwind CSS + FontAwesome + Chart.js |
| 后端 | Python 3 + Flask + Flask-CORS |
| OCR | EasyOCR（自然场景文字识别） |
| 语种检测 | langdetect |
| 数据库 | SQLite 3（内置于 Python，无需安装，自动创建） |
| Web 服务器 | Nginx（反向代理，可选） |
| 部署环境 | Ubuntu Linux + Conda（/home/szh/anaconda3）+ 用户级 systemd |

---

## API 接口说明

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 用户登录 |
| POST | `/api/logout` | 退出登录 |
| GET  | `/api/check_auth` | 检查登录状态 |
| GET  | `/api/stats` | 获取统计数据 |
| POST | `/api/recognize` | 上传图像并识别 |
| GET  | `/api/history` | 获取历史记录 |
| DELETE | `/api/history/{id}` | 删除记录 |
| GET/PUT | `/api/profile` | 查看/更新个人信息 |
| GET/POST | `/api/users` | 用户列表/创建用户（管理员） |
| PUT/DELETE | `/api/users/{id}` | 更新/删除用户（管理员） |
