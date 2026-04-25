from setuptools import find_packages, setup

setup(
    name="neraium-core",
    version="0.1.0",
    description="Read-only structural instability instrumentation engine and API",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.110",
        "numpy>=1.24",
        "pandas>=2.0",
        "pydantic>=2",
        "python-multipart>=0.0.9",
        "starlette>=0.36",
        "uvicorn>=0.29",
        "websockets>=12",
    ],
    extras_require={
        "dev": ["httpx", "pytest", "ruff"],
        "plots": ["matplotlib"],
    },
    include_package_data=True,
    packages=find_packages(include=["neraium_core*", "ui*"], exclude=["tests*", "docs*"]),
)
