from setuptools import setup

# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='cbpi4-Flowmeter',
      version='0.0.7',
      description='Sensor de fluxo e volume CBPI4 (YF-201)',
      author='Edgar Louzano',
      author_email='edgar.verdile@gmail.com',
      url='https://github.com/louzano/cbpi4-Flowmeter',
      include_package_data=True,
      keywords='globalsettings',
      package_data={
        # If any package contains *.txt or *.rst files, include them:
      '': ['*.txt', '*.rst', '*.yaml'],
      'cbpi4-Flowmeter': ['*','*.txt', '*.rst', '*.yaml']},
      packages=['cbpi4-Flowmeter'],
      install_requires=['cbpi4>=4.1.10.rc2'],
      long_description=long_description,
      long_description_content_type='text/markdown'
     )
