from setuptools import setup, find_packages

setup(
    name='POAP',
    version='0.1.7',
    author='David Bindel',
    author_email='bindel@cornell.edu',
    packages=['poap', 'poap.test'],
    scripts=[],
    url='http://pypi.python.org/pypi/POAP/',
    license='LICENSE.txt',
    description='Python Optimization Asynchronous Plumbing.',
    long_description=open('README.rst').read(),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',        
    ],
    install_requires=[
    ],
)
