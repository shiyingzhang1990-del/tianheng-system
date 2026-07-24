#!/bin/bash
# ==============================================
#  天衡系统 - macOS 一键安装启动脚本
#  客户无需技术知识，双击即可运行
# ==============================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PORT="${PORT:-5001}"
PIP_MIRROR="https://pypi.tuna.tsinghua.edu.cn/simple"

print_banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       天衡系统 - 智能知识助手 v2.0           ║${NC}"
    echo -e "${CYAN}║       一键安装启动脚本 (macOS)               ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════╝${NC}"
    echo ""
}

error_exit() {
    echo -e "${RED}[错误] $1${NC}"
    echo ""
    echo "按任意键退出..."
    read -n 1
    exit 1
}

success_msg() { echo -e "${GREEN}[OK]${NC} $1"; }
warn_msg()   { echo -e "${YELLOW}[!]${NC} $1"; }
info_msg()   { echo -e "${CYAN}[*]${NC} $1"; }

print_banner

# ---- 第1步：检查 Python ----
info_msg "第1步：检查 Python 环境..."

if ! command -v python3 &> /dev/null; then
    echo ""
    echo -e "${RED}未找到 Python 3，请先安装：${NC}"
    echo "  https://www.python.org/downloads/"
    echo "  下载 macOS 安装包，双击安装即可"
    error_exit "Python 3 未安装"
fi

PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
success_msg "Python $PY_VER"

# ---- 第2步：配置虚拟环境 ----
echo ""
info_msg "第2步：配置 Python 虚拟环境..."

if [ ! -d "venv" ]; then
    echo "  正在创建虚拟环境..."
    python3 -m venv venv || error_exit "创建虚拟环境失败"
    success_msg "虚拟环境创建完成"
else
    success_msg "虚拟环境已存在"
fi

source venv/bin/activate || error_exit "激活虚拟环境失败"

# ---- 第3步：安装依赖 ----
echo ""
info_msg "第3步：安装 Python 依赖包..."

if [ ! -f "requirements.txt" ]; then
    error_exit "未找到 requirements.txt"
fi

# 检查是否已安装
if python3 -c "import flask, sentence_transformers, chromadb" 2>/dev/null; then
    success_msg "依赖已安装，跳过"
else
    echo "  正在从镜像安装（首次约需2-5分钟）..."
    pip install --quiet --upgrade pip
    pip install -r requirements.txt -i "$PIP_MIRROR" || {
        warn_msg "镜像安装失败，尝试官方源..."
        pip install -r requirements.txt || error_exit "依赖安装失败"
    }
    success_msg "依赖安装完成"
fi

# ---- 第4步：下载AI模型 ----
echo ""
info_msg "第4步：检查 AI 嵌入模型..."

MODEL_DIR="models/embedding"
if [ ! -d "$MODEL_DIR" ] || [ -z "$(ls -A "$MODEL_DIR" 2>/dev/null)" ]; then
    echo "  模型尚未下载（约470MB），正在下载..."
    echo "  (仅首次需要，请耐心等待)"

    # 尝试用脚本下载
    if [ -f "download_model.py" ]; then
        python3 download_model.py || {
            warn_msg "自动下载失败"
            echo ""
            echo "  请手动下载模型文件并解压到: $MODEL_DIR"
            echo "  下载地址: https://hf-mirror.com/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        }
    else
        warn_msg "未找到 download_model.py，将在首次提问时自动下载"
    fi
else
    success_msg "模型已就绪"
fi

# ---- 第5步：检查API密钥 ----
echo ""
info_msg "第5步：检查 DeepSeek API 密钥..."

ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example "$ENV_FILE"
    fi
fi

# 读取当前配置
source "$ENV_FILE" 2>/dev/null || true
CURRENT_KEY="${DEEPSEEK_API_KEY:-}"

if [ -z "$CURRENT_KEY" ] || [[ "$CURRENT_KEY" == *"请填写"* ]]; then
    echo ""
    echo -e "${YELLOW}  ╔══════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}  ║  需要配置 DeepSeek API 密钥才能使用 AI 问答  ║${NC}"
    echo -e "${YELLOW}  ╚══════════════════════════════════════════════╝${NC}"
    echo ""
    echo "  获取步骤："
    echo "  1. 打开 https://platform.deepseek.com/"
    echo "  2. 注册账号并登录"
    echo "  3. 点击「API Keys」→「创建新的 API Key」"
    echo "  4. 复制密钥（以 sk- 开头）"
    echo ""
    read -p "  请粘贴你的 API Key: " USER_KEY

    if [ -n "$USER_KEY" ]; then
        # 更新 .env 文件
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|DEEPSEEK_API_KEY=.*|DEEPSEEK_API_KEY=$USER_KEY|" "$ENV_FILE"
        else
            sed -i "s|DEEPSEEK_API_KEY=.*|DEEPSEEK_API_KEY=$USER_KEY|" "$ENV_FILE"
        fi

        # 验证密钥
        echo "  正在验证 API Key..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -H "Authorization: Bearer $USER_KEY" \
            -H "Content-Type: application/json" \
            -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":5}' \
            --connect-timeout 10 --max-time 15 \
            "https://api.deepseek.com/v1/chat/completions" 2>/dev/null || echo "000")

        if [ "$HTTP_CODE" = "200" ]; then
            success_msg "API Key 验证成功"
        else
            warn_msg "API Key 验证失败（HTTP $HTTP_CODE），但仍可启动"
            echo "  你可以稍后修改 .env 文件更新密钥"
        fi
    else
        warn_msg "未输入密钥，将使用演示模式（无AI回答）"
    fi
else
    success_msg "API Key 已配置"
fi

# ---- 第6步：检查前端文件 ----
echo ""
info_msg "第6步：检查前端文件..."

if [ ! -d "dist" ] || [ ! -f "dist/index.html" ]; then
    error_exit "未找到前端文件 (dist/index.html)，请确保安装包完整"
fi
success_msg "前端文件就绪"

# ---- 启动 ----
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           一切就绪，正在启动...              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
echo ""
echo "  访问地址: http://localhost:${PORT}"
echo "  默认账号: admin"
echo "  默认密码: admin123"
echo ""
echo "  按 Ctrl+C 停止服务"
echo ""

# 自动打开浏览器
sleep 2
open "http://localhost:${PORT}" 2>/dev/null || true

# 启动
python3 app.py
