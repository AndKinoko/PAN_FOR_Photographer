@echo off
echo 启动局域网网盘服务器...
echo.

REM 检查虚拟环境
if not exist "venv\Scripts\activate.bat" (
    echo 创建虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
echo 安装依赖...
pip install -r requirements.txt

REM 数据库迁移
echo 数据库迁移...
python manage.py migrate

REM 创建超级用户（如果不存在）
if not exist "db.sqlite3" (
    echo 创建超级用户...
    python manage.py createsuperuser --noinput --username admin --email admin@example.com 2>nul || (
        echo 如果创建失败，请手动运行：python manage.py createsuperuser
    )
)

REM 运行服务器
echo.
echo 启动开发服务器...
echo 本机访问：http://localhost:8000
echo 局域网访问：http://[你的IP地址]:8000
echo 按 Ctrl+C 停止服务器
echo.
python manage.py runserver 0.0.0.0:8000

pause