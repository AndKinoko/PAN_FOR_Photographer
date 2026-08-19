# 局域网网盘

一个简单的局域网私有云盘，基于 Django 写的。在公司或家里的局域网里，几台设备都能访问，方便传文件。

\> \*\*注意\*\*：本项目已经全面重构，建议使用最新版本。

## 功能

- 用户注册登录
- 上传下载文件，没有类型和大小限制
- 创建/删除文件夹
- 按文件名搜索
- 分享文件，可以设密码和有效期
- 支持 RAW 格式照片预览（NEF、CR2、ARW 等）
- 手机端也能用，响应式布局

## 快速开始

需要 Python 3.8+。

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python manage.py migrate

# 启动服务
python manage.py runserver 0.0.0.0:8000
```

然后浏览器打开 `http://localhost:8000` 就能用了。局域网其他设备访问的话，换成你电脑的 IP 就行。

首次使用需要先注册一个账号。

## 项目结构

```
lan_drive/
├── drive/          # Django 项目配置
├── accounts/       # 用户登录注册
├── storage/        # 文件管理（上传、下载、删除、预览）
├── share/          # 文件分享
├── search/         # 文件搜索
├── templates/      # HTML 模板
├── media/          # 上传的文件存这里
└── static/         # 样式、JS 等静态资源
```

## 用到的库

- Django 4.x
- Bootstrap 5（前端样式）
- Pillow、rawpy、imageio（图片处理）
- SQLite（数据库）

## 说两句

这项目主要是为了方便（局域网环境/内网穿透环境）互相传文件，不需要搭什么复杂的服务。功能够用，也没什么花里胡哨的东西。有什么问题直接提 issue 就好。
