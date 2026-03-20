# 局域网网盘部署指南

## 系统要求

- Python 3.8+
- Django 4.0+
- 支持的操作系统：Windows, Linux, macOS

## 快速部署步骤

### 1. 克隆或下载项目
```bash
git clone <项目地址>
cd lan_drive
```

### 2. 创建虚拟环境并安装依赖
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. 配置环境变量
复制 `.env.example` 为 `.env` 并修改配置：
```bash
cp .env.example .env
```

编辑 `.env` 文件，至少修改以下配置：
```
SECRET_KEY=your-very-secret-key-here
DEBUG=False  # 生产环境设置为False
ALLOWED_HOSTS=your-local-ip-address,localhost,127.0.0.1
```

### 4. 数据库迁移
```bash
python manage.py migrate
```

### 5. 创建超级用户
```bash
python manage.py createsuperuser
```

### 6. 收集静态文件
```bash
python manage.py collectstatic
```

### 7. 运行开发服务器（局域网访问）
```bash
# 获取本机IP地址
# Windows: ipconfig
# Linux/Mac: ifconfig

# 运行服务器，允许局域网访问
python manage.py runserver 0.0.0.0:8000
```

### 8. 访问网盘
- 本机访问：http://localhost:8000
- 局域网其他设备访问：http://[你的IP地址]:8000

## 生产环境部署

### 使用Gunicorn + Nginx（Linux）

1. 安装Gunicorn：
```bash
pip install gunicorn
```

2. 创建Gunicorn服务文件 `/etc/systemd/system/gunicorn.service`：
```ini
[Unit]
Description=gunicorn daemon for lan_drive
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/lan_drive
ExecStart=/path/to/lan_drive/venv/bin/gunicorn --access-logfile - --workers 3 --bind unix:/path/to/lan_drive/lan_drive.sock drive.wsgi:application

[Install]
WantedBy=multi-user.target
```

3. 配置Nginx：
```nginx
server {
    listen 80;
    server_name your-server-ip;

    location = /favicon.ico { access_log off; log_not_found off; }
    location /static/ {
        root /path/to/lan_drive;
    }

    location /media/ {
        root /path/to/lan_drive;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/path/to/lan_drive/lan_drive.sock;
    }
}
```

## 防火墙配置

### Windows
1. 打开Windows Defender防火墙
2. 添加入站规则，允许8000端口TCP连接

### Linux (ufw)
```bash
sudo ufw allow 8000/tcp
sudo ufw enable
```

## 常见问题

### 1. 无法从其他设备访问
- 检查防火墙设置
- 确保运行命令为 `runserver 0.0.0.0:8000` 而不是 `runserver 127.0.0.1:8000`
- 确认设备在同一局域网内

### 2. 文件上传失败
- 检查 `media/` 目录权限
- 确保磁盘有足够空间
- 检查文件大小是否超过限制（默认100MB）

### 3. 静态文件无法加载
- 运行 `python manage.py collectstatic`
- 检查Nginx/Apache静态文件配置
- 确保 `STATIC_ROOT` 路径正确

### 4. 数据库问题
- 运行 `python manage.py migrate`
- 检查数据库文件权限
- 确保使用正确的数据库配置

## 性能优化建议

1. **数据库优化**：
   - 考虑使用PostgreSQL替代SQLite
   - 定期清理过期分享链接

2. **文件存储优化**：
   - 使用外部存储（如NAS）存储大文件
   - 定期清理临时文件

3. **缓存优化**：
   - 启用Django缓存
   - 使用Redis或Memcached

4. **安全建议**：
   - 定期更新Django和依赖包
   - 使用HTTPS（可通过Nginx配置）
   - 定期备份数据库

## 手机端访问

- 系统已采用响应式设计，支持手机浏览器访问
- 建议将网站添加到手机主屏幕，获得类似App的体验
- 确保手机与服务器在同一局域网内

## 更新项目

```bash
git pull origin main
pip install -r requirements.txt --upgrade
python manage.py migrate
python manage.py collectstatic
sudo systemctl restart gunicorn  # 如果使用Gunicorn
```

## 技术支持

如遇问题，请检查：
1. Django错误日志：查看 `manage.py runserver` 输出
2. 服务器日志：查看系统日志
3. 浏览器开发者工具：检查网络请求和Console输出