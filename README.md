# 局域网网盘

一个用 Django 写的轻量级网盘，适合公司/家里局域网环境用，方便几台设备之间传文件。

## 能干啥

- 注册登录，支持密码重置
- 上传下载文件，不限类型（单文件最大 10GB）
- 文件夹管理 + 面包屑导航
- 按文件名搜索
- 文件分享，可设密码和有效期
- 在线预览图片/视频/PDF/RAW（NEF、CR2、ARW 都支持）
- 浅色/深色主题，一键切换
- 手机端也能用
- 管理员可管理用户（冻结账号、设配额、删用户等）

## 快速开始

Python 3.8+ 环境下：

```bash
# 装依赖
pip install -r requirements.txt

# 建库
python manage.py migrate

# 建管理员账号（登录后左边会有"用户管理"）
python manage.py createsuperuser

# 启动
python manage.py runserver 0.0.0.0:8000
```

Windows 用户直接双击 `start_server.bat` 就行。

浏览器打开 `http://localhost:8000`，局域网其他设备换成你电脑 IP 访问。

首次用需要注册账号。

想改配置的话，把 `.env.example` 复制成 `.env` 就行。

## 管理员相关

- 管理员登录后左侧导航栏有"用户管理"入口
- 冻结账号：能登录看文件，但不能下载/上传/分享
- 配额默认 10GB，设 0 或留空就是不限
- 不能对自己搞冻结/删除，超级管理员也不能动

## 项目结构

```
├── drive/          # Django 项目配置
├── accounts/       # 用户相关
├── storage/        # 文件管理
├── share/          # 文件分享
├── search/         # 搜索
├── templates/      # HTML 模板
├── media/          # 上传的文件
├── static/         # 静态资源
├── .env.example    # 环境变量示例
└── start_server.bat  # Windows 一键启动
```

## 依赖

- Django 4.x
- Bootstrap 5
- django-crispy-forms + crispy-bootstrap5
- Pillow、rawpy、imageio、numpy（图片处理）
- SQLite

---

局域网传文件够用，有问题直接提 issue。
