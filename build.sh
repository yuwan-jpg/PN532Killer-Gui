#!/bin/bash

# PN532 Python Linux/macOS 构建脚本

set -e  # 遇到错误时退出

echo "========================================"
echo "PN532 Python Linux/macOS 构建脚本"
echo "========================================"

# 检查 Python 是否可用
if ! command -v python3 &> /dev/null; then
    echo "错误: python3 未安装或不在 PATH 中"
    exit 1
fi

# 解析命令行参数
COMMAND=${1:-build}

show_help() {
    echo "用法: ./build.sh [命令]"
    echo ""
    echo "可用命令:"
    echo "  help     - 显示此帮助信息"
    echo "  check    - 检查构建依赖"
    echo "  test     - 运行测试"
    echo "  clean    - 清理构建目录"
    echo "  build    - 构建应用程序 (默认)"
    echo "  install  - 安装依赖"
    echo "  setup    - 设置 Linux 环境"
    echo ""
}

check_deps() {
    echo "检查构建依赖..."
    python3 build_cross_platform.py check
}

run_tests() {
    echo "运行测试..."
    python3 build_cross_platform.py test
}

clean_build() {
    echo "清理构建目录..."
    python3 build_cross_platform.py clean
    
    # 额外清理
    [ -d "build" ] && rm -rf build
    [ -d "dist" ] && rm -rf dist
    [ -d "__pycache__" ] && rm -rf __pycache__
    find . -name "*.pyc" -delete 2>/dev/null || true
    find . -name "*.pyo" -delete 2>/dev/null || true
    
    echo "清理完成"
}

install_deps() {
    echo "安装 Python 依赖..."
    python3 -m pip install --upgrade pip
    python3 -m pip install -r requirements.txt
    python3 -m pip install pyinstaller
    echo "Python 依赖安装完成"
}

setup_linux() {
    echo "设置 Linux 环境..."
    echo "请参考 LINUX_SETUP.md 安装系统依赖"
    
    # 检查是否为 Ubuntu/Debian
    if command -v apt-get &> /dev/null; then
        echo ""
        echo "检测到 Ubuntu/Debian 系统"
        echo "建议运行以下命令安装依赖:"
        echo "sudo apt-get update"
        echo "sudo apt-get install libnfc-bin libnfc-dev build-essential git"
        echo ""
    fi
    
    # 检查是否为 CentOS/RHEL/Fedora
    if command -v yum &> /dev/null || command -v dnf &> /dev/null; then
        echo ""
        echo "检测到 CentOS/RHEL/Fedora 系统"
        echo "建议运行以下命令安装依赖:"
        if command -v dnf &> /dev/null; then
            echo "sudo dnf install libnfc libnfc-devel gcc gcc-c++ make git"
        else
            echo "sudo yum install libnfc libnfc-devel gcc gcc-c++ make git"
        fi
        echo ""
    fi
    
    # 检查是否为 Arch Linux
    if command -v pacman &> /dev/null; then
        echo ""
        echo "检测到 Arch Linux 系统"
        echo "建议运行以下命令安装依赖:"
        echo "sudo pacman -S libnfc base-devel git"
        echo ""
    fi
}

build_app() {
    echo "开始构建应用程序..."
    python3 build_cross_platform.py build
    echo "构建完成！"
    echo "可执行文件位于 dist 目录中"
}

# 主逻辑
case "$COMMAND" in
    help)
        show_help
        ;;
    check)
        check_deps
        ;;
    test)
        run_tests
        ;;
    clean)
        clean_build
        ;;
    install)
        install_deps
        ;;
    setup)
        setup_linux
        ;;
    build)
        build_app
        ;;
    *)
        echo "未知命令: $COMMAND"
        show_help
        exit 1
        ;;
esac

echo "操作完成"