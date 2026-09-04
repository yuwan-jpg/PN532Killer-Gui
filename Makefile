# PN532 Python 跨平台构建 Makefile

# 变量定义
PYTHON := python3
BUILD_SCRIPT := build_cross_platform.py
DIST_DIR := dist
BUILD_DIR := build

# 默认目标
.PHONY: all
all: build

# 检查依赖
.PHONY: check
check:
	@echo "检查构建依赖..."
	$(PYTHON) $(BUILD_SCRIPT) check

# 运行测试
.PHONY: test
test:
	@echo "运行测试..."
	$(PYTHON) $(BUILD_SCRIPT) test

# 清理构建目录
.PHONY: clean
clean:
	@echo "清理构建目录..."
	$(PYTHON) $(BUILD_SCRIPT) clean
	@if [ -d "$(BUILD_DIR)" ]; then rm -rf $(BUILD_DIR); fi
	@if [ -d "$(DIST_DIR)" ]; then rm -rf $(DIST_DIR); fi
	@if [ -d "__pycache__" ]; then rm -rf __pycache__; fi
	@find . -name "*.pyc" -delete
	@find . -name "*.pyo" -delete

# 构建应用程序
.PHONY: build
build: check test
	@echo "构建应用程序..."
	$(PYTHON) $(BUILD_SCRIPT) build

# 快速构建（跳过检查和测试）
.PHONY: build-fast
build-fast:
	@echo "快速构建..."
	$(PYTHON) $(BUILD_SCRIPT) build

# 安装依赖
.PHONY: install-deps
install-deps:
	@echo "安装 Python 依赖..."
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install pyinstaller

# Linux 特定目标
.PHONY: install-linux-deps
install-linux-deps:
	@echo "安装 Linux 依赖..."
	@echo "请参考 LINUX_SETUP.md 手动安装系统依赖"

# 开发环境设置
.PHONY: dev-setup
dev-setup: install-deps
	@echo "设置开发环境..."
	@if [ ! -f "key.txt" ]; then touch key.txt; fi
	@if [ ! -f "history_keys.txt" ]; then touch history_keys.txt; fi

# 语法检查
.PHONY: lint
lint:
	@echo "执行语法检查..."
	@for file in *.py; do \
		if [ -f "$$file" ]; then \
			echo "检查 $$file..."; \
			$(PYTHON) -m py_compile "$$file" || exit 1; \
		fi \
	done
	@echo "语法检查完成"

# 运行应用程序
.PHONY: run
run:
	@echo "运行应用程序..."
	$(PYTHON) pn532_gui.py

# 打包源代码
.PHONY: package-source
package-source:
	@echo "打包源代码..."
	@tar -czf pn532-python-source.tar.gz \
		--exclude='$(BUILD_DIR)' \
		--exclude='$(DIST_DIR)' \
		--exclude='__pycache__' \
		--exclude='*.pyc' \
		--exclude='*.pyo' \
		--exclude='.git' \
		.

# 显示帮助信息
.PHONY: help
help:
	@echo "PN532 Python 构建系统"
	@echo ""
	@echo "可用目标:"
	@echo "  all           - 执行完整构建（默认）"
	@echo "  check         - 检查构建依赖"
	@echo "  test          - 运行测试"
	@echo "  clean         - 清理构建目录"
	@echo "  build         - 构建应用程序"
	@echo "  build-fast    - 快速构建（跳过检查）"
	@echo "  install-deps  - 安装 Python 依赖"
	@echo "  dev-setup     - 设置开发环境"
	@echo "  lint          - 语法检查"
	@echo "  run           - 运行应用程序"
	@echo "  package-source- 打包源代码"
	@echo "  help          - 显示此帮助信息"
	@echo ""
	@echo "Linux 特定:"
	@echo "  install-linux-deps - 显示 Linux 依赖安装指南"

# 设置默认目标
.DEFAULT_GOAL := help