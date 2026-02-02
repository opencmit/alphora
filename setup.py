"""
打pip包
"""

from setuptools import setup, find_packages

setup(
    name="alphora",
    version="1.0.6",
    description="AI Agent Development Toolkit",
    author="Tian tian",
    author_email="tiantianit@chinamobile.com",
    license="CLA",
    packages=find_packages(include=["alphora", "alphora.*"]),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=open("requirements.txt").read().splitlines()
)
