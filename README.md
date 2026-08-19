# 局域网网盘系统

一个基于 Django 的私有云存储解决方案，支持局域网内设备访问，具备完整的文件管理、分享、搜索功能，并针对手机端进行了响应式设计优化。
> **注意**：本项目已经全面重构，建议使用最新版本。

> **当前版本**: V1.5_26/03/20  
> **发布日期**: 2026年3月20日

---

## 目录

- [功能特性](#功能特性)
- [技术栈](#技术栈)
- [项目结构](#项目结构)
- [快速开始](#快速开始)
- [部署指南](#部署指南)
- [安全与性能](#安全与性能)
- [移动端优化](#移动端优化)
- [V1.5 更新日志](#v15-更新日志)
- [版本历史](#版本历史)
- [许可证](#许可证)

---

## 功能特性

### 核心功能
- ✅ 用户注册/登录/登出（Django 内置认证系统）
- ✅ 文件上传下载（无类型和大小限制）
- ✅ 文件夹管理（创建、删除、导航）
- ✅ 文件搜索（按文件名全局搜索）
- ✅ 文件分享（支持密码保护和有效期设置）
- ✅ 响应式设计（桌面端 + 手机端兼容）

### V1.5 新增功能
- ✅ **RAW 格式照片预览**: 支持尼康 (NEF)、佳能 (CR2/CR3)、索尼 (ARW) 等主流相机 RAW 文件
- ✅ **增强文件预览**: 优化预览框显示，支持更多图像格式
- ✅ **前端体验优化**: 修复文件名换行、预览框尺寸等问题
- ✅ **分享功能完善**: 添加分享功能入口，提升用户体验
- ✅ **文件删除优化**: 修复 RAW 文件删除后预览图残留问题，实施双重保障机制

---

## 技术栈

### 后端
| 技术 | 说明 |
|------|------|
| Django 4.x | Web 框架 |
| SQLite | 数据库 |
| Pillow, rawpy, imageio, numpy | 图像处理（RAW 解码） |
| Django 内置认证系统 | 用户认证 |

### 前端
| 技术 | 说明 |
|------|------|
| Bootstrap 5 | UI 框架 |
| HTML5, CSS3, JavaScript | 前端语言 |
| 移动优先设计 | 响应式布局策略 |

### 文件处理
| 类别 | 格式 |
|------|------|
| 常规图像 | JPEG, PNG, GIF, BMP, WebP, TIFF |
| 相机 RAW | NEF, CR2, CR3, CRW, ARW, SR2, SRF, DNG, RAF, ORF, RW2, NRW |
| 预览生成 | 自动生成 800×800 JPEG 缩略图 |

---

## 项目结构

```
lan_drive/
├── drive/                  # Django 项目主配置
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/               # 用户认证应用
│   ├── views.py
│   └── templates/accounts/
├── storage/                # 文件存储管理应用
│   ├── models.py           # File 模型（含预览生成）
│   ├── views.py            # 文件上传/下载/删除/预览
│   ├── signals.py          # 文件删除信号清理
│   ├── forms.py            # 文件上传表单
│   └── templates/storage/
├── share/                  # 文件分享应用
│   ├── views.py            # 分享创建/查看/管理
│   ├── models.py           # Share 模型（含密码哈希）
│   └── templates/share/
├── search/                 # 文件搜索应用
│   └── views.py
├── templates/              # 模板文件
│   ├── base.html           # 基础布局模板
│   ├── includes/           # 可复用组件
│   ├── accounts/
│   ├── storage/
│   └── share/
├── media/                  # 上传文件存储目录
│   └── previews/           # 预览图存储目录
└── static/                 # 静态文件目录
```

---

## 快速开始

### 环境要求
- Python 3.8+
- Django 4.x（详见 requirements.txt）
- 内存: 至少 2GB（用于 RAW 文件处理）
- 操作系统: Windows / Linux / macOS

### 安装步骤

```bash
# 1. 克隆项目
git clone <项目地址>
cd lan_drive

# 2. 创建虚拟环境
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 数据库迁移
python manage.py migrate

# 5. 创建超级用户（管理员）
python manage.py createsuperuser

# 6. 运行开发服务器（局域网访问）
python manage.py runserver 0.0.0.0:8000
```

### 访问方式
- 本机访问: `http://localhost:8000`
- 局域网访问: `http://[你的IP地址]:8000`
- 管理后台: `http://localhost:8000/admin/`（需超级用户登录）

### 一键启动（Windows）
双击项目根目录下的 `start_server.bat` 即可自动完成创建虚拟环境、安装依赖、数据库迁移并启动服务器。

---

## 部署指南

### 局域网部署

```powershell
# 获取本机 IP
ipconfig

# 确保防火墙允许 8000 端口
# Windows: 防火墙 → 入站规则 → 新建 8000/TCP

# 启动
python manage.py runserver 0.0.0.0:8000

# 或直接双击 start_server.bat（自动完成全部步骤）
```

### 常见问题

| 问题 | 解决 |
|------|------|
| 无法从其他设备访问 | 检查防火墙，确保使用 `0.0.0.0:8000` 而非 `127.0.0.1` |
| 文件上传失败 | 检查 `media/` 目录权限和磁盘空间 |
| RAW 文件解码失败 | 确保安装了 rawpy 和依赖的 C++ 运行时库 |

---

## 安全与性能

### 安全措施

| 类别 | 措施 |
|------|------|
| 认证授权 | Django 内置认证系统，用户只能访问自己的文件 |
| 输入防护 | CSRF 令牌、模板自动转义、Django ORM 防 SQL 注入 |
| 密码存储 | 分享密码使用 `make_password` 哈希存储 |
| 文件安全 | 文件名安全处理、路径遍历防护、用户文件隔离 |
| 媒体保护 | 媒体文件通过受保护的 `serve_media` 视图访问，需登录认证 |
| 会话安全 | 安全的 session cookie 设置 |

### 性能优化

- **数据库**: 常用字段添加索引，使用 `select_related` / `prefetch_related`
- **缓存**: 支持 Redis/Memcached 缓存配置
- **静态文件**: 支持 CDN 部署和文件压缩
- **文件处理**: 大文件流式上传下载，预览图自动缩放（800×800）
- **分页**: 大数据集自动分页

### 备份策略

```powershell
# backup.ps1 (Windows PowerShell)
$date = Get-Date -Format "yyyyMMdd"
$backupDir = "D:\backups\lan_drive\$date"
New-Item -ItemType Directory -Path $backupDir -Force

python manage.py dumpdata > "$backupDir\db_backup.json"
Copy-Item -Path "media" -Destination "$backupDir\media\" -Recurse
Write-Host "备份完成: $backupDir"

# 删除 7 天前的备份
Get-ChildItem "D:\backups\lan_drive" -Directory | Where-Object {
    $_.CreationTime -lt (Get-Date).AddDays(-7)
} | Remove-Item -Recurse -Force
```

---

## 移动端优化

### 设计原则
采用 **移动优先** 的响应式设计策略，确保在手机端有良好的用户体验。

### 已实现的优化
- **响应式布局**: Bootstrap 5 网格系统，适配 xs 到 xl 所有断点
- **触摸优化**: 按钮尺寸 ≥44×44 px，足够的触摸目标间距
- **性能优化**: 懒加载图片、压缩静态资源
- **表单优化**: 防止 iOS 自动缩放（`font-size: 16px`）

---

## V1.5 更新日志

> 发布日期: 2026-03-20

### 新功能

#### 1. RAW 格式照片预览
- **支持格式**: 尼康 (NEF)、佳能 (CR2/CR3)、索尼 (ARW)、松下 (RW2)、奥林巴斯 (ORF)、通用 (DNG)
- **技术实现**: 使用 `rawpy` 库后台解码 RAW 文件，生成 JPEG 预览图
- **预览流程**: 上传 → `rawpy.imread()` 解码 → `postprocess()` 转 RGB → 缩放至 800×800 → 存储为 JPEG
- **降级策略**: 生成失败时自动尝试提取 RAW 文件内嵌的 JPEG 缩略图
- **文件管理**: 预览图与 RAW 文件同步删除（信号 + delete 双重保障）

#### 2. 增强的文件预览
- 预览框从 `col-lg-4` 扩大到 `col-lg-5`
- 修复长文件名换行问题（`text-break`）
- RAW 文件显示专用相机图标
- 优先使用生成的预览图，无预览时显示文件图标

### 问题修复

| 问题 | 原因 | 修复 |
|------|------|------|
| 新上传文件无法预览 | 预览生成逻辑时序问题 | 优化生成逻辑，确保文件保存后正确触发 |
| 文件名换行错误 | 缺少换行 CSS 类 | 使用 Bootstrap `text-break` |
| 预览框尺寸过小 | 网格列宽不足 | `col-lg-4` → `col-lg-5` |
| 分享入口缺失 | 前端未添加按钮 | 在操作栏、导航栏、预览区添加分享按钮 |
| RAW 预览图残留 | 删除时未清理 preview 文件 | 信号 + delete 双重保障机制 |

### 依赖变更

```txt
# 新增
rawpy>=0.26      # RAW 文件解码
imageio>=2.37    # 图像处理支持
numpy>=2.4       # 数值计算支持
```

### 数据库变更

- `storage_file` 表新增 `preview` 字段（ImageField）
- 迁移文件: `storage/migrations/0002_file_preview.py`

### 现有文件批量生成预览

```bash
python manage.py shell
>>> from storage.models import File
>>> for f in File.objects.filter(preview__isnull=True):
...     f.generate_preview()
...     f.save()
```

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| V1.5 | 2026-03-20 | RAW 格式预览、增强预览、分享入口、删除优化 |
| V1.4 | 2026-03-15 | 基础文件管理、用户认证、分享功能、响应式设计 |

---

## 许可证

[MIT License](https://opensource.org/licenses/MIT) © 2026