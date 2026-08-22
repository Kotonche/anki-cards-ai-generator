from setuptools import setup, find_packages


def read_requirements():
    with open('requirements.txt', encoding='utf-8') as f:
        return f.read().splitlines()


setup(
    name='anki-cards-ai-generator',
    version='0.2.0',
    install_requires=read_requirements(),
    python_requires='>=3.10',
    url='https://github.com/ValeriiZhyla/anki-cards-ai-generator',
    packages=find_packages(),
    package_data={
        'generator.webui': ['templates/*.html', 'static/*.css', 'static/*.js'],
    },
    entry_points={
        'console_scripts': [
            'anki-cards-web=generator.webui.server:main',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
    ],
)
