from setuptools import setup

setup(
    name="consulstack",
    version="0.1",
    install_requires=[
        'cfn-environment-base==0.6.0'
    ],
    dependency_links=[
        'https://github.com/DualSpark/cloudformation-environmentbase/archive/0.5.1.zip#egg=cfn-environment-base-0.5.1'
    ],
    package_dir={"": "src"},
    include_package_data=True,
    zip_safe=True
)
