class EnvironmentSetup:
    def __init__(self):
        self.data_dir = "/content/data/"
        self.repo_dir = "torrent_downloader"
        self.libtorrent_whl_id = "1kNCut32-mZJ_joCORA2kydDb06ysTxDN"  # Google Drive ID

    def setup(self):
        import os
        import subprocess
        import sys
        import nest_asyncio
        import time

        if os.path.exists(self.repo_dir):
            print(f"Removing existing repo folder '{self.repo_dir}' for fresh clone...")
            subprocess.run(f"rm -rf {self.repo_dir}", shell=True, check=True)

        subprocess.run(
            f"git clone https://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@github.com/Alein8130/torrent_downloader.git",
            shell=True,
            check=True,
        )

        subprocess.run("gdown --id 1kNCut32-mZJ_joCORA2kydDb06ysTxDN", shell=True, check=True)
        wheel_path = "./libtorrent-2.0.11-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
        os.system(f"pip install --no-deps {wheel_path}")

        subprocess.run("cp torrent_downloader/torrent_downloader.py .", shell=True, check=True)
        subprocess.run("cp torrent_downloader/main.ass .", shell=True, check=True)
        subprocess.run("cp torrent_downloader/fonts/* /usr/share/fonts/", shell=True, check=True)
        subprocess.run("fc-cache -fv", shell=True, check=True)
        subprocess.run("cp torrent_downloader/userinputs.py .", shell=True, check=True)
        subprocess.run("cp torrent_downloader/hardsubber.py .", shell=True, check=True)

        os.makedirs(self.data_dir, exist_ok=True)

        nest_asyncio.apply()

        from userinputs import BatchProcessor
        from hardsubber import HardSubber
        import re, glob, shlex, base64, importlib, random, string
        import asyncio, wget
        import libtorrent as lt
        from google.colab import files
        from telethon import TelegramClient, errors
        from tqdm.notebook import tqdm

        from torrent_downloader import (
            download_torrent,
            add_subtitles,
            get_mkv_files,
            get_font_map,
            aria2c_torrent,
            list_audio_streams,
            get_best_audio_stream
        )

        print("✅ Environment setup completed successfully.")

















