#!/usr/bin/env python3
"""
天衡系统 - 嵌入模型下载工具
预下载 paraphrase-multilingual-MiniLM-L12-v2 模型（约470MB）
优先使用 HuggingFace 国内镜像，支持断点续传
"""

import os
import sys
import time



# 允许用户通过环境变量设置镜像
HF_ENDPOINT = os.environ.get('HF_ENDPOINT', 'https://hf-mirror.com')

MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
LOCAL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'embedding')


def print_step(step, msg):
    print(f"\n  [{step}] {msg}")


def main():
    print("=" * 55)
    print("  天衡系统 - AI模型下载工具")
    print("=" * 55)
    print(f"  模型: {MODEL_NAME}")
    print(f"  大小: 约 470MB")
    print(f"  镜像: {HF_ENDPOINT}")

    # 如果已存在，跳过
    if os.path.isdir(LOCAL_DIR) and os.listdir(LOCAL_DIR):
        print(f"\n  模型已存在于: {LOCAL_DIR}")
        print("  如需重新下载，请先删除此目录。")
        return True

    os.makedirs(LOCAL_DIR, exist_ok=True)

    try:
        from sentence_transformers import SentenceTransformer

        print("\n  正在下载模型（可能需要几分钟）...")
        print("  (下载进度会显示在下方)")

        if HF_ENDPOINT:
            os.environ['HF_ENDPOINT'] = HF_ENDPOINT

        start = time.time()
        model = SentenceTransformer(MODEL_NAME)
        elapsed = time.time() - start

        # 保存到本地目录
        model.save(LOCAL_DIR)
        print(f"\n  下载完成！用时 {elapsed:.0f} 秒")
        print(f"  模型已保存到: {LOCAL_DIR}")
        return True

    except ImportError:
        print("\n  [错误] 未安装 sentence-transformers")
        print("  请先运行: pip install sentence-transformers")
        return False

    except Exception as e:
        print(f"\n  [错误] 下载失败: {e}")
        print()
        print("  请尝试以下方法之一：")
        print(f"  1. 设置其他镜像: HF_ENDPOINT=https://hf-mirror.com python download_model.py")
        print(f"  2. 手动下载模型放到: {LOCAL_DIR}")
        print(f"     下载地址: https://hf-mirror.com/sentence-transformers/{MODEL_NAME}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
