from setuptools import setup, find_packages

setup(
    name="antigravity-headroom",
    version="0.1.0",
    description="Context compression tool for LLM token usage reduction",
    author="Headroom Core Developer",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "mcp>=0.1.0",
    ],
    entry_points={
        "console_scripts": [
            "headroom=antigravity_headroom.cli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)
