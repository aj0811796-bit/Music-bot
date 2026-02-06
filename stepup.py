from setuptools import setup

setup(
    name='telegram-music-bot',
    version='1.0.0',
    install_requires=[
        'pyrogram>=2.0.0',
        'pytgcalls>=3.0.0.dev31',
        'yt-dlp>=2024.4.9',
        'python-dotenv>=1.0.0',
        'requests>=2.31.0',
    ],
)
