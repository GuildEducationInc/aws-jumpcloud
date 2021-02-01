from setuptools import find_packages, setup

from aws_jumpcloud.version import __VERSION__


def get_requirements(requirements_file):
    requirement = []
    with open(requirements_file) as requirements:
        for line in requirements:
            line, _, _ = line.partition("#")
            line = line.strip()
            requirement.append(line)
    return requirement


with open("README.md", "r", encoding="utf-8") as readme:
    LONG_DESCRIPTION = readme.read()

setup(
    name="aws_jumpcloud",
    version=__VERSION__,
    packages=find_packages(exclude=["tests"]),
    zip_safe=False,
    python_requires=">=3.6, <4",
    install_requires=get_requirements("requirements.txt"),
    tests_require=get_requirements("test-requirements.txt"),
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    classifiers=[  # Optional
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3 :: Only",
    ],
    entry_points={"console_scripts": ["aws-jumpcloud = aws_jumpcloud.cli:main"]},
)
