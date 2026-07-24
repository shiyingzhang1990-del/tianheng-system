#!/bin/bash
# ======================================================
# 天衡系统 - 阿里云自动部署脚本
# 在阿里云服务器上运行此脚本，自动完成部署
# 使用方法: bash aliyun_deploy.sh
# ======================================================

set -e

echo "========================================"
echo "  天衡系统 - 阿里云部署脚本"
echo "========================================"
echo ""

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

error_exit() { echo -e "${RED}[错误] $1${NC}"; exit 1; }
success() { echo -e "${GREEN}[成功] $1${NC}"; }
info() { echo -e "${YELLOW}[信息] $1${NC}"; }

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then 
  error_exit "请使用 sudo 运行此脚本: sudo bash aliyun_deploy.sh"
fi

# 获取项目目录
PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_DIR"

# [1] 安装系统依赖
info "[1/6] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx git curl > /dev/null 2>&1
success "系统依赖安装完成"

# [2] 创建项目目录
info "[2/6] 配置项目目录..."
mkdir -p /opt/tianheng
# 复制当前目录所有文件到 /opt/tianheng
cp -r "$PROJECT_DIR"/* /opt/tianheng/ 2>/dev/null || true
cd /opt/tianheng
success "项目文件已复制到 /opt/tianheng"

# [3] 创建虚拟环境 & 安装 Python 依赖
info "[3/6] 安装 Python 依赖（首次可能需要 5-10 分钟）..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install gunicorn -q
success "Python 依赖安装完成"

# [4] 创建 systemd 服务
info "[4/6] 配置系统服务..."
cat > /etc/systemd/system/tianheng.service << 'SERVICEEOF'
[Unit]
Description=天衡系统 - 智能知识助手
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tianheng
Environment="PATH=/opt/tianheng/venv/bin"
Environment="DEEPSEEK_API_KEY="
Environment="DEFAULT_USERNAME=admin"
Environment="DEFAULT_PASSWORD=admin123"
Environment="SECRET_KEY=tianheng-secret-2024"
ExecStart=/opt/tianheng/venv/bin/gunicorn --bind 127.0.0.1:5001 --workers 2 --timeout 120 app:create_app()
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable tianheng
success "系统服务已创建"

# [5] 配置 Nginx 反向代理
info "[5/6] 配置 Nginx..."

# 获取服务器公网 IP
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com 2>/dev/null || curl -s https://api.ipify.org 2>/dev/null || echo "localhost")

cat > /etc/nginx/sites-available/tianheng << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket 支持（流式输出需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # 流式响应
        proxy_buffering off;
        proxy_cache off;
    }
}
NGINXEOF

# 启用站点
ln -sf /etc/nginx/sites-available/tianheng /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
success "Nginx 配置完成"

# [6] 启动服务
info "[6/6] 启动天衡系统..."
systemctl start tianheng
sleep 2
systemctl status tianheng --no-pager | head -10

echo ""
echo "========================================"
echo -e "${GREEN}  部署完成！${NC}"
echo "========================================"
echo ""
echo -e "  ${GREEN}访问地址: http://$PUBLIC_IP${NC}"
echo ""
echo "  默认账号: admin"
echo "  默认密码: admin123"
echo ""
echo "  如需修改密码，编辑 /etc/systemd/system/tianheng.service"
echo "  修改 DEFAULT_PASSWORD 后运行:"
echo "    systemctl daemon-reload && systemctl restart tianheng"
echo ""
echo "  如需配置 DeepSeek API Key（用于 AI 问答），编辑:"
echo "    /etc/systemd/system/tianheng.service"
echo "  设置 DEEPSEEK_API_KEY 后运行:"
echo "    systemctl daemon-reload && systemctl restart tianheng"
echo ""
echo "  查看日志: journalctl -u tianheng -f"
echo "========================================"
