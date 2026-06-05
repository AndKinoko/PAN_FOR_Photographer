@echo off
chcp 65001 >nul
echo ========================================
echo   局域网网盘服务器启动脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 环境！
    echo 请先安装 Python 3.8+，并确保已添加到系统 PATH。
    echo 下载地址：https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [1/5] 检查虚拟环境...
if not exist "venv\Scripts\activate.bat" (
    echo [1/5] 创建虚拟环境...
    python -m venv venv
)
if not exist "venv\Scripts\activate.bat" (
    echo [错误] 虚拟环境创建失败！
    pause
    exit /b 1
)

echo [2/5] 激活虚拟环境...
call venv\Scripts\activate.bat

echo [3/5] 安装依赖...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败！
    echo 常见原因：rawpy 需要 C++ 编译环境。
    echo 请尝试手动安装：pip install rawpy
    pause
    exit /b 1
)

echo [4/5] 数据库迁移...
python manage.py migrate
if %errorlevel% neq 0 (
    echo [错误] 数据库迁移失败！
    pause
    exit /b 1
)

REM 创建超级用户（如果不存在）
if not exist "db.sqlite3" (
    echo 创建超级用户...
    python manage.py createsuperuser --noinput --username admin --email admin@example.com 2>nul || (
        echo 如果创建失败，请手动运行：python manage.py createsuperuser
    )
)

echo.
echo [5/5] 启动开发服务器...
echo.
echo ========================================
echo   本机访问： http://localhost:8000
echo   局域网访问：http://[你的IP地址]:8000
echo   按 Ctrl+C 停止服务器
echo ========================================
echo.
python manage.py runserver 0.0.0.0:8000
if %errorlevel% neq 0 (
    echo [错误] 服务器启动失败，请检查端口 8000 是否被占用。
    pause
)