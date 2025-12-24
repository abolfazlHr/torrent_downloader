import importlib
import random
import string
import time
import os
import re
import shlex
import subprocess
import asyncio
from tqdm.notebook import tqdm
from telethon import TelegramClient, errors
from google.colab import files
from torrent_downloader import list_audio_streams, add_subtitles, aria2c_torrent, get_mkv_files

class HardSubber:
    def __init__(self, batch_info, manual_audio_selection=False, telegram_api_id=20824771, telegram_api_hash='659d6d48782b33998e714d27195def94', telegram_bot_token=None):
        self.batch_info = batch_info
        self.manual_audio_selection = manual_audio_selection
        self.telegram_api_id = telegram_api_id
        self.telegram_api_hash = telegram_api_hash
        self.telegram_bot_token = telegram_bot_token

        random_session_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self.client = TelegramClient(random_session_name, telegram_api_id, telegram_api_hash)
        self.random_session_name = random_session_name

        importlib.reload(importlib.import_module("torrent_downloader"))

    async def safe_telegram_start(self):
        if self.client.is_connected():
            return  # Already started

        while True:
            try:
                await self.client.start(bot_token=self.telegram_bot_token)
                print("✅ Telegram client started successfully!")
                break
            except errors.FloodWaitError as e:
                wait_minutes = e.seconds // 60
                wait_seconds = e.seconds % 60
                print(f"⚠️ FloodWaitError: wait {wait_minutes} min {wait_seconds} sec...")
                await asyncio.sleep(e.seconds)

    async def process(self):
        if self.batch_info['is_batch']:
            await self._process_batch()
        else:
            await self._process_movie()

    async def _process_batch(self):
        ses = self.batch_info['session']
        handle = self.batch_info['handle']
        torrent_info = self.batch_info['torrent_info']
        files_ = torrent_info.files()

        for ep in self.batch_info['selected_episodes']:
            selected_index = ep['index']
            input_file = os.path.join('/content/data/', ep['path'])
            file_size = files_.file_size(selected_index)

            priorities = [0] * files_.num_files()
            priorities[selected_index] = 1
            handle.prioritize_files(priorities)

            print(f"\nDownloading episode {ep['episode_num']}...")
            pbar = tqdm(total=100)
            while True:
                s = handle.status()
                file_progress = handle.file_progress()
                downloaded = file_progress[selected_index]
                progress_percent = (downloaded / file_size) * 100 if file_size > 0 else 0

                pbar.set_postfix({
                    'Progress': f'{progress_percent:.2f}%',
                    'Down': f'{s.download_rate / 1000:.1f} kb/s',
                    'Up': f'{s.upload_rate / 1000:.1f} kB/s',
                    'Peers': s.num_peers
                })
                pbar.n = int(progress_percent)
                pbar.refresh()

                if progress_percent >= 100:
                    break
                time.sleep(5)
            pbar.close()
            print(f"Downloaded: {ep['path']}")

            audio_streams_param = None
            if self.manual_audio_selection:
                # Ask if user wants manual selection for this episode
                while True:
                    choice = input(f"Do you want to manually select audio streams for episode {ep['episode_num']}? (y/n): ").strip().lower()
                    if choice in ('y', 'n'):
                        break
                    print("Please enter 'y' or 'n'.")

                if choice == 'y':
                    audio_streams = list_audio_streams(input_file)
                    
                    user_input = input(
                        "Enter desired stream indices separated by commas (e.g., 0,1) or leave empty for default: "
                    ).strip()

                    if user_input:
                        try:
                            selected_numbers = [int(n.strip()) for n in user_input.split(",") if n.strip()]
                        except ValueError:
                            print("[WARN] Invalid input, using default audio streams.")
                            selected_numbers = []

                        audio_streams_param = []
                        for n in selected_numbers:
                            matching = next((s for s in audio_streams if s[0] == n), None)
                            if matching:
                                audio_streams_param.append(f"0:a:{n}")
                            else:
                                 print(f"[WARN] No audio stream corresponding to index: {n}")
                    else:
                        print("[INFO] No audio streams selected, using default.")
                else:
                    print("[WARN] No audio streams found, using default.")

            await self.process_episode(
                input_file,
                ep['episode_num'],
                ep['subtitle'],
                audio_streams=audio_streams_param
            )

    async def _process_movie(self):
        movie_path = aria2c_torrent(self.batch_info['torrent_link'], "/content/data/")
        input_file = os.path.join("/content/data/", get_mkv_files("/content/data/")[0])
        episode_num = self.batch_info['episode_numbers'][0]
        subtitle_file = self.batch_info['subtitles'][episode_num]

        audio_streams_param = None
        if self.manual_audio_selection:
            
            audio_streams = list_audio_streams(input_file)
            user_input = input(
                "\nEnter desired stream indices separated by commas (e.g., 0,1) or leave empty for default: "
            ).strip()
            if user_input:
                selected_numbers = [
                    int(n.strip()) for n in user_input.split(",") if n.strip().isdigit()
                ]
                audio_streams_param = []
                for n in selected_numbers:
                    matching = next((s for s in audio_streams if s[0] == n), None)
                    if matching:
                        audio_streams_param.append(f"0:a:{n}")
                    else:
                        print(f"[WARN] No audio stream corresponding to index: {n}")

        await self.process_episode(
            input_file,
            episode_num,
            subtitle_file,
            audio_streams=audio_streams_param
        )

    def get_duration(self, input_file):
        import ffmpeg
        try:
            probe = ffmpeg.probe(input_file)
            return float(probe['format']['duration'])
        except Exception:
            try:
                result = subprocess.run(
                    ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                     '-of', 'default=noprint_wrappers=1:nokey=1', input_file],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                return float(result.stdout.strip())
            except Exception:
                return None

    def run_ffmpeg_with_progress(self, cmd_list, duration_sec):
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        pbar = tqdm(total=100, dynamic_ncols=True, desc="Encoding")

        process = subprocess.Popen(cmd_list, stderr=subprocess.PIPE, universal_newlines=True)

        while True:
            line = process.stderr.readline()
            if not line:
                break

            time_match = time_pattern.search(line)

            if time_match:
                h, m, s = time_match.groups()
                elapsed_seconds = int(h) * 3600 + int(m) * 60 + float(s)
                percent_complete = (elapsed_seconds / duration_sec) * 100 if duration_sec else 0
                percent_complete = min(percent_complete, 100)

                remaining_seconds = max(duration_sec - elapsed_seconds, 0)
                rem_h = int(remaining_seconds // 3600)
                rem_m = int((remaining_seconds % 3600) // 60)
                rem_s = int(remaining_seconds % 60)
                remaining_str = f"{rem_h}:{rem_m:02}:{rem_s:02}"
                pbar.n = int(percent_complete)
                pbar.set_postfix({
                    'Progress': f'{percent_complete:.2f}%',
                    'ETA': remaining_str
                })
                pbar.refresh()

        process.wait()
        pbar.n = 100
        pbar.refresh()
        pbar.close()

        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg exited with code {process.returncode}")

    async def process_episode(self, input_file, episode_num, subtitle_file, audio_streams=None):
        await self.safe_telegram_start()
        for quality in self.batch_info['qualities']:
            quality_label = f"{quality.split('x')[1]}p"

            safe_video_name = re.sub(r"[\'\"\\/:*?<>|]", "_", self.batch_info['video_name'])
            if self.batch_info['is_movie']:
                output_filename = f"[@AniWide] {safe_video_name} ({quality_label}).mkv"
                caption_name = f"[@AniWide] {self.batch_info['video_name']} ({quality_label}).mkv"
            else:
                output_filename = f"[@AniWide] {safe_video_name} - {episode_num} ({quality_label}).mkv"
                caption_name = f"[@AniWide] {self.batch_info['video_name']} - {episode_num} ({quality_label}).mkv"
            output_file = f"/content/data/{output_filename}"

            cmd_str = add_subtitles(f'"{input_file}"', subtitle_file, 'hard', 'x264', self.batch_info['CRF'], quality, True, audio_streams)
            full_cmd = f"{cmd_str} '{output_file}'"

            print(f"Encoding {quality_label}...")

            duration = self.get_duration(input_file)
            if duration is None:
                duration = 0

            cmd_list = shlex.split(full_cmd)
            self.run_ffmpeg_with_progress(cmd_list, duration)

            print(f"Uploading {quality_label}...")
            await self.client.send_file(
                self.batch_info['telegram_id'],
                output_file,
                caption=caption_name,
                force_document=True
            )
            print(f"{quality_label} Uploaded!\n")
            try:
                os.remove(output_file)
            except Exception as e:
                print(f"Warning: failed to delete {output_file}: {e}")

    async def finalize_telegram(self):
        await self.client.disconnect()
        print("Telegram client disconnected.")

        session_file = f"{self.random_session_name}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
            print(f"Deleted session file")

