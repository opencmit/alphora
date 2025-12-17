"""
打pip包
"""

from setuptools import setup, find_packages

setup(
    name="alphora",  # 包名
    version="1.0.1",  # 版本号
    description="AI Agent Development Toolkit",

    author="Tian tian",
    author_email="tiantianit@chinamobile.com",
    license="MIT",
    packages=find_packages(include=["alphora", "alphora.*"]),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=open("requirements.txt").read().splitlines()
)
