@echo off
REM ==============================================
REM  天衡系统 - Windows 一键安装启动脚本
REM  客户无需技术知识，双击即可运行
REM ==============================================

chcp 65001 >nul
title 天衡系统 - 安装启动中...
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"
set "PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PORT=5001"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║       天衡系统 - 智能知识助手 v2.0           ║
echo ║       一键安装启动脚本 (Windows)             ║
echo ╚══════════════════════════════════════════════╝
echo.

REM ---- 第1步：检查 Python ----
echo [*] 第1步：检查 Python 环境...

where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 未找到 Python，请先安装
    echo   下载地址: https://www.python.org/downloads/
    echo   安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] Python %PY_VER%

REM ---- 第2步：配置虚拟环境 ----
echo.
echo [*] 第2步：配置虚拟环境...

if not exist "venv\Scripts\python.exe" (
    echo   正在创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建完成
) else (
    echo [OK] 虚拟环境已存在
)

call "venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [错误] 激活虚拟环境失败
    pause
    exit /b 1
)

REM ---- 第3步：安装依赖 ----
echo.
echo [*] 第3步：安装 Python 依赖包...

if not exist "requirements.txt" (
    echo [错误] 未找到 requirements.txt
    pause
    exit /b 1
)

python -c "import flask, sentence_transformers, chromadb" 2>nul
if errorlevel 1 (
    echo   正在从清华镜像安装（首次约需2-5分钟）...
    python -m pip install --quiet --upgrade pip
    python -m pip install -r requirements.txt -i %PIP_MIRROR%
    if errorlevel 1 (
        echo [!] 镜像安装失败，尝试官方源...
        python -m pip install -r requirements.txt
        if errorlevel 1 (
            echo [错误] 依赖安装失败
            pause
            exit /b 1
        )
    )
    echo [OK] 依赖安装完成
) else (
    echo [OK] 依赖已安装
)

REM ---- 第4步：下载AI模型 ----
echo.
echo [*] 第4步：检查 AI 嵌入模型...

set "MODEL_DIR=models\embedding"
if not exist "%MODEL_DIR%\*" (
    echo   模型尚未下载（约470MB），正在下载...
    echo   (仅首次需要，请耐心等待)

    if exist "download_model.py" (
        python download_model.py
        if errorlevel 1 (
            echo [!] 自动下载失败
            echo   请手动下载模型文件并解压到: %MODEL_DIR%
            echo   下载地址: https://hf-mirror.com/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
        )
    ) else (
        echo [!] 未找到 download_model.py，将在首次提问时自动下载
    )
) else (
    echo [OK] 模型已就绪
)

REM ---- 第5步：检查API密钥 ----
echo.
echo [*] 第5步：检查 DeepSeek API 密钥...

set "ENV_FILE=.env"
if not exist "%ENV_FILE%" (
    if exist ".env.example" copy ".env.example" "%ENV_FILE%" >nul
)

REM 读取当前API Key
set "API_KEY="
if exist "%ENV_FILE%" (
    for /f "tokens=2 delims==" %%a in ('findstr "DEEPSEEK_API_KEY" "%ENV_FILE%" 2^>nul') do set "API_KEY=%%a"
)

if "%API_KEY%"=="" (
    set NEED_KEY=1
) else (
    echo !API_KEY! | findstr "请填写" >nul && set NEED_KEY=1 || set NEED_KEY=0
)

if "!NEED_KEY!"=="1" (
    echo.
    echo ╔══════════════════════════════════════════════╗
    echo ║  需要配置 DeepSeek API 密钥才能使用 AI 问答  ║
    echo ╚══════════════════════════════════════════════╝
    echo.
    echo   获取步骤：
    echo   1. 打开 https://platform.deepseek.com/
    echo   2. 注册账号并登录
    echo   3. 点击 API Keys → 创建新的 API Key
    echo   4. 复制密钥（以 sk- 开头）
    echo.
    set /p USER_KEY="  请粘贴你的 API Key: "

    if not "!USER_KEY!"=="" (
        REM 更新 .env 文件
        powershell -Command "(Get-Content '%ENV_FILE%') -replace 'DEEPSEEK_API_KEY=.*', 'DEEPSEEK_API_KEY=!USER_KEY!' | Set-Content '%ENV_FILE%'" 2>nul
        echo [OK] API Key 已保存
    ) else (
        echo [!] 未输入密钥，将使用演示模式（无AI回答）
    )
) else (
    echo [OK] API Key 已配置
)

REM ---- 第6步：检查前端文件 ----
echo.
echo [*] 第6步：检查前端文件...

if not exist "dist\index.html" (
    echo [错误] 未找到前端文件 (dist\index.html)
    pause
    exit /b 1
)
echo [OK] 前端文件就绪

REM ---- 启动 ----
echo.
echo ╔══════════════════════════════════════════════╗
echo ║           一切就绪，正在启动...              ║
echo ╚══════════════════════════════════════════════╝
echo.
echo   访问地址: http://localhost:%PORT%
echo   默认账号: admin
echo   默认密码: admin123
echo.
echo   按 Ctrl+C 停止服务
echo.

REM 自动打开浏览器
start http://localhost:%PORT%

python app.py

if errorlevel 1 (
    echo.
    echo [错误] 启动失败，请检查上方错误信息
)

echo.
pause
