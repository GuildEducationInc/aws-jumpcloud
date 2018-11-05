from setuptools import find_packages, setup


setup(
    name='aws_jumpcloud',
    packages=find_packages(exclude=["tests"]),
    zip_safe=False,
    python_requires=">=3.6",
    install_requires=["requests", "BeautifulSoup4", "lxml", "boto3", "keyring"],
    tests_require=["pycodestyle", "pylint"],
    entry_points={'console_scripts': ['aws-jumpcloud = aws_jumpcloud.cli:main']}
)
