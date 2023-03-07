from setuptools import setup

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name = 'dogey',
    version = '0.1',
    description = 'A pythonic dogehouse API.',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    author_email = 'shadowrlrs@gmail.com',
    python_requires = '>=3.8.0',
    url = 'https://github.com/Shadofer/dogey',
    packages = ['dogey'],
    install_requires = ['websockets'],
    extras_require = {
        'sound': ['pymediasoup']
    },
    license = 'MIT'
)
