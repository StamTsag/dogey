from setuptools import setup

with open('README.md', 'r') as f:
    long_description = f.read()

setup(
    name='dogey',
    version='0.1',
    description='A dogehouse python API',
    author='Shadofer',
    author_email='shadowrlrs@gmail.com',
    packages=['dogey'],
    install_requires=['websockets'],
    long_description=long_description,
    license='MIT'
)
