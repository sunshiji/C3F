# 自然场景文种识别系统 (C3F)

> Natural Scene Text Language Recognition System

基于 OCR + 语种检测的自然场景文字识别网站，支持图像上传，自动识别图像中文字的语种类别。

---

## 功能特性

- 🖼️ **图像上传识别**：拖放或点击上传图片，自动 OCR + 语种分类
- 🌍 **多语种支持**：支持 18 种语言/文种（12 种 EasyOCR + 6 种 Unicode 范围检测），涵盖 CJK、阿拉伯文、梵文系、西里尔文等字符体系，以及符号类别（详见下方语种列表）
- 📊 **可视化仪表盘**：识别统计、趋势图、语种分布图
- 🗂️ **历史记录**：查询、筛选、删除识别记录
- 👥 **用户管理**：管理员可创建/禁用用户
- 🔒 **登录鉴权**：Session + localStorage 双重验证

---

## 支持的语种

| 语种 | 识别方式 | ISO 代码 |
|------|---------|---------|
| 简体中文 | EasyOCR | `ch_sim` |
| 繁体中文 | EasyOCR | `ch_tra` |
| 英文（拉丁文） | EasyOCR | `en` |
| 日文 | EasyOCR | `ja` |
| 韩文 | EasyOCR | `ko` |
| 阿拉伯文 | EasyOCR | `ar` |
| 印地语（天城体） | EasyOCR | `hi` |
| 俄文（西里尔） | EasyOCR | `ru` |
| 泰文 | EasyOCR | `th` |
| 孟加拉文 | EasyOCR | `bn` |
| 卡纳达文 | EasyOCR | `kn` |
| 泰卢固文 | EasyOCR | `te` |
| 希腊文 | Unicode 范围检测 | `el` |
| 希伯来文 | Unicode 范围检测 | `he` |
| 柬埔寨文（高棉文） | Unicode 范围检测 | `km` |
| 藏文 | Unicode 范围检测 | `bo` |
| 蒙古文 | Unicode 范围检测 | `mn` |
| 奥里亚文 | Unicode 范围检测 | `or` |
| 符号/数字类 | Unicode 范围检测 | `symbols` |

> 希腊文、希伯来文、柬埔寨文、藏文、蒙古文和奥里亚文通过 Unicode 字符范围直接识别，
> 无需下载额外的模型权重文件。

---

## 项目结构

```
C3F/
├── frontend/               # HTML 原型（Tailwind CSS + FontAwesome）
│   ├── login.html          # 登录页
│   ├── index.html          # 主框架（侧边栏 + iframe）
│   ├── home.html           # 仪表盘
│   ├── upload.html         # 图像识别页
│   ├── history.html        # 历史记录页
│   └── settings.html       # 系统设置页
├── backend/                # Python Flask 后端
│   ├── app.py              # 主应用
│   ├── config.py           # 配置文件
│   ├── download_models.py  # OCR 模型权重一键下载工具
│   ├── requirements.txt    # pip 依赖
│   └── models/             # ★ OCR 模型权重目录（.pth 文件，不纳入版本控制）
│       └── README.md       # 模型目录说明
├── database/
│   └── schema.sql          # SQLite DDL 参考（应用启动时自动建表）
└── deploy/
    ├── environment.yml     # Conda 环境定义
    ├── nginx.conf          # Nginx 反向代理配置（可选）
    ├── start.sh            # 一键部署脚本（Conda）
    ├── update_env.sh       # 已有环境依赖更新脚本
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

脚本自动完成：目录创建（含 `backend/models/`）→ Conda 环境创建（禁用代理）→ 用户级 systemd 服务注册并启动。  
**数据库无需任何配置**：应用首次启动时自动创建 SQLite 文件 `backend/c3f.db` 并写入初始账号。

> **注**：如需系统重启后服务自动恢复（注销后保持运行），
> 需请管理员执行一次：`loginctl enable-linger szh`

### 3. 已有环境如何更新依赖（代码更新后）

如果 Conda 环境 `c3f` **已经存在**，只需更新 pip 依赖，无需重建整个环境：

```bash
cd /home/szh/system/C3F

# 先拉取最新代码
git pull

# 只更新 pip 依赖（自动卸载已删除的包、安装新包）
bash deploy/update_env.sh

# 重启服务
systemctl --user restart c3f
```

> **说明**：`update_env.sh` 会：
> 1. 卸载已从依赖列表中移除的旧包（如 PyMySQL）
> 2. 用 `pip install -r requirements.txt` 安装/升级当前所需包
>
> `pip install -r requirements.txt` 只会**增量安装**，不会自动卸载已删除的依赖，
> 所以需要 `update_env.sh` 来显式清理旧包。

也可以只运行完整部署脚本，它也包含同样的清理逻辑：

```bash
bash deploy/start.sh
```

### 4. 手动部署（分步）

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

### 5. OCR 模型下载与配置

EasyOCR 的模型权重文件存放在 `backend/models/` 目录。  
后端启动时会**自动检测**该目录：

- 若目录中有 `.pth` 文件 → 直接从本地加载，**不联网**
- 若目录为空 → EasyOCR 使用默认缓存目录（`~/.EasyOCR/model/`），首次识别时自动下载

**强烈建议**在启动服务前使用内置脚本**一次性**完成下载，避免服务运行时因网络波动导致识别失败。

#### 5.1 运行一键下载脚本

在项目根目录执行（需能访问互联网）：

```bash
cd /home/szh/system/C3F

# 激活 conda 环境后直接运行
conda activate c3f
python backend/download_models.py
```

脚本将把所有模型文件保存到 `backend/models/`（约 1–3 GB）。下载完成后，后端启动时会
自动检测到该目录并从本地加载模型，**无需配置 `OCR_MODEL_DIR` 环境变量**。

支持参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--model-dir DIR` | 模型保存目录 | `backend/models` |
| `--langs LANGS` | 逗号分隔的语种代码 | 全部 12 个 |
| `--gpu` | 下载时启用 GPU | 否（CPU 即可） |

```bash
# 示例：只下载中英日韩
python backend/download_models.py --langs ch_sim,en,ja,ko

# 示例：保存到自定义目录
python backend/download_models.py --model-dir /data/ocr_models
```

> 如果下载中断，重新运行脚本即可——已下载的文件会被自动跳过。
>
> 以下语种已从 EasyOCR 支持列表移除（当前版本不兼容）：
> 古吉拉特文（`gu`）、旁遮普文（`pa`）— 无对应模型；泰米尔文（`ta`）— 模型权重维度与当前 EasyOCR 1.7.x 不兼容。

#### 5.2 配置自定义模型目录（可选）

默认情况下，后端自动检测 `backend/models/`，**无需手动配置**。

如果需要将模型放在其他位置，通过环境变量指定：

**方法 A：写入 systemd 服务文件**（推荐，重启后自动生效）

编辑 `~/.config/systemd/user/c3f.service`，在 `[Service]` 节中添加：

```ini
[Service]
Environment="OCR_MODEL_DIR=/path/to/your/models"
```

然后重新加载并重启：

```bash
systemctl --user daemon-reload
systemctl --user restart c3f
```

**方法 B：手动启动时指定**

```bash
OCR_MODEL_DIR=/path/to/your/models \
  /home/szh/anaconda3/envs/c3f/bin/python backend/app.py
```

> **提示**：配置 `OCR_MODEL_DIR` 后，服务会完全禁用自动下载。若指定目录中
> 模型文件缺失，EasyOCR 将直接报错而非尝试下载，从而避免服务挂起。

#### 5.3 GPU 推理（默认开启）

系统默认开启 GPU 推理（`OCR_USE_GPU=1`），速度比 CPU 快 5–10 倍。

**验证 GPU 是否可用**

```bash
/home/szh/anaconda3/envs/c3f/bin/python -c \
  "import torch; print('GPU 可用' if torch.cuda.is_available() else 'GPU 不可用，将使用 CPU')"
```

**无 GPU 时切换到 CPU 模式**

```ini
# ~/.config/systemd/user/c3f.service [Service] 节中添加：
Environment="OCR_USE_GPU=0"
```

#### 5.4 可选：精简加载语种以加快启动

默认加载全部 12 个 EasyOCR 语种（`ch_sim,ch_tra,en,ja,ko,ar,hi,ru,th,bn,kn,te`）。
如需加快启动速度，可通过 `OCR_LANGS` 只加载所需语种，**并确保 `backend/models/`
中已有对应的模型文件**（先用 `--langs` 参数运行下载脚本）：

```ini
# ~/.config/systemd/user/c3f.service [Service] 节中添加：
Environment="OCR_LANGS=ch_sim,en,ja,ko"
```

以下语种通过 Unicode 范围检测，**无需 EasyOCR 模型权重**，不受 `OCR_LANGS` 限制：
希腊文（`el`）、希伯来文（`he`）、柬埔寨文（`km`）、藏文（`bo`）、蒙古文（`mn`）、奥里亚文（`or`）

> EasyOCR 支持语种完整列表：<https://www.jaided.ai/easyocr/>

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
| OCR | EasyOCR 1.7（自然场景文字识别，12 种语言，本地模型权重） |
| 语种检测 | Unicode 范围检测 + langdetect（拉丁文系后处理） |
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

