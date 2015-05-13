from distutils.core import setup

setup(
    name='POAP',
    version='0.1.2',
    author='David Bindel',
    author_email='bindel@cornell.edu',
    packages=['poap', 'poap.test'],
    scripts=[],
    url='http://pypi.python.org/pypi/POAP/',
    license='LICENSE.txt',
    description='Python Optimization Asynchronous Plumbing.',
    long_description=open('README.txt').read(),
    install_requires=[
    ],
)
