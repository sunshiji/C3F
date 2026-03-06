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
    ├── nginx.conf      # Nginx 反向代理配置
    ├── start.sh        # 一键部署脚本
    └── restart_backend.sh
```

---

## 快速部署（Ubuntu 服务器）

### 1. 克隆代码到服务器

```bash
ssh szh@10.109.119.208
cd /home/szh
git clone <repo_url> system
```

### 2. 一键部署

```bash
cd /home/szh/system
chmod +x deploy/start.sh
bash deploy/start.sh
```

脚本自动完成：系统依赖安装 → Python 虚拟环境 → 数据库初始化 → Nginx 配置 → 启动后台服务。

### 3. 手动部署（分步）

#### 数据库

```bash
mysql -u root -p < database/schema.sql
```

#### 修改数据库配置

编辑 `backend/config.py`，修改 `DB_CONFIG` 中的 `password` 为 MySQL root 密码。

#### 安装 Python 依赖

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> 注：EasyOCR 体积较大，首次运行会自动下载语言模型（需要联网）。  
> 如果不需要 OCR 功能，可只安装 `Flask Flask-Cors PyMySQL Pillow langdetect`，系统将使用模拟数据演示。

#### 启动后端

```bash
cd backend
source venv/bin/activate
python app.py          # 监听 0.0.0.0:5000
```

#### 配置 Nginx

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/c3f
sudo ln -s /etc/nginx/sites-available/c3f /etc/nginx/sites-enabled/c3f
sudo nginx -t && sudo systemctl reload nginx
```

---

## 访问

| 地址 | 说明 |
|------|------|
| `http://10.109.119.208/` | 网站入口（Windows 浏览器可直接访问） |
| `http://10.109.119.208/login.html` | 登录页 |
| `http://10.109.119.208/api/...` | 后端 API（Nginx 代理） |

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
| 数据库 | MySQL 8 |
| Web 服务器 | Nginx（反向代理） |
| 部署环境 | Ubuntu Linux |

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
