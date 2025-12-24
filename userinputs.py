import os
import re
import time
import subprocess
import libtorrent as lt
from google.colab import files

class BatchProcessor:
    ASS_TEMPLATE = """[Script Info]
Title: Subtitle Edit styles file
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Vazirmatn RD ExtraBold,60,&H00FFFFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,1.2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    FONT_DEST = "/usr/share/fonts/"
    TEST_FONT_DEST = "/content/fonts/"

    def __init__(self, torrent_link, video_name, episode_numbers, telegram_id,
                 is_batch=False, is_movie=False, encode_480p=True, encode_720p=True,
                 encode_1080p=True, manual_audio_selection=False, CRF=25):
        
        self.torrent_link = torrent_link
        self.video_name = video_name
        self.episode_numbers = [ep.strip() for ep in episode_numbers.split(',') if ep.strip()]
        self.telegram_id = telegram_id
        self.is_batch = is_batch
        self.is_movie = is_movie
        self.manual_audio_selection = manual_audio_selection
        self.CRF = CRF

        self.qualities = []
        if encode_480p: self.qualities.append("848x480")
        if encode_720p: self.qualities.append("1280x720")
        if encode_1080p: self.qualities.append("1920x1080")

        os.makedirs(self.FONT_DEST, exist_ok=True)
        os.makedirs(self.TEST_FONT_DEST, exist_ok=True)

        self.batch_info = {
            'is_batch': self.is_batch,
            'torrent_link': self.torrent_link,
            'video_name': self.video_name,
            'episode_numbers': self.episode_numbers,
            'qualities': self.qualities,
            'CRF': self.CRF,
            'telegram_id': self.telegram_id,
            'subtitles': {},
            'is_movie': self.is_movie
        }
        self.session = None
        self.handle = None
        self.torrent_info = None

    # === Helper methods ===

    def is_ass(self, filepath):
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return "[Script Info]" in f.read(1024)

    def srt_time_to_ass_time(self, srt_time):
        hh, mm, rest = srt_time.split(':')
        ss, ms = rest.split(',')
        hh = int(hh)
        mm = int(mm)
        ss = int(ss)
        ms = int(ms)
        cs = round(ms / 10)
        if cs == 100:
            cs = 0
            ss += 1
            if ss == 60:
                ss = 0
                mm += 1
                if mm == 60:
                    mm = 0
                    hh += 1
        return f"{hh}:{mm:02d}:{ss:02d}.{cs:02d}"

    def srt_to_ass(self, filepath):
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        dialogue = []
        start = end = None
        text_lines = []
        for line in lines + ['\n']:
            line = line.strip()
            if line.isdigit():
                if start and end and text_lines:
                    dialogue.append((start, end, text_lines))
                start = end = None
                text_lines = []
            elif '-->' in line:
                start_raw, end_raw = [t.strip() for t in line.split('-->')]
                start = self.srt_time_to_ass_time(start_raw)
                end = self.srt_time_to_ass_time(end_raw)
            elif line == '':
                if start and end and text_lines:
                    dialogue.append((start, end, text_lines))
                start = end = None
                text_lines = []
            else:
                clean_line = ''.join(ch for ch in line if ord(ch) > 31)
                text_lines.append(clean_line)
        events = ""
        for start, end, txt in dialogue:
            text = "\\N".join(txt)
            events += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
        return self.ASS_TEMPLATE + events

    def uu_decode(self, data: str) -> bytes:
        ret = bytearray()
        src = [0] * 4
        pos = 0
        length = len(data)

        while pos < length:
            bytes_count = 0
            i = 0
            while i < 4 and pos < length:
                c = data[pos]
                pos += 1
                if c not in ('\n', '\r'):
                    src[i] = ord(c) - 33
                    i += 1
                    bytes_count += 1

            if bytes_count > 1:
                ret.append((src[0] << 2) | (src[1] >> 4))
            if bytes_count > 2:
                ret.append(((src[1] & 0xF) << 4) | (src[2] >> 2))
            if bytes_count > 3:
                ret.append(((src[2] & 0x3) << 6) | src[3])

        return bytes(ret)

    def decode_ass_font(self, data_lines):
        import base64
        data = "".join(line.strip() for line in data_lines if line.strip())
        try:
            decoded_bytes = self.uu_decode(data)
        except:
            try:
                decoded_bytes = base64.b64decode(data)
            except:
                print("❌ Failed to decode font data")
                return b""
        return decoded_bytes

    def extract_fonts_from_ass(self, ass_path):
        os.makedirs(self.FONT_DEST, exist_ok=True)
        os.makedirs(self.TEST_FONT_DEST, exist_ok=True)

        with open(ass_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        in_fonts = False
        font_name = None
        font_data = []
        extracted_fonts = []

        def save_font(name, data_lines):
            decoded = self.decode_ass_font(data_lines)
            if not decoded:
                return False
            out_path = os.path.join(self.FONT_DEST, name)
            with open(out_path, "wb") as f:
                f.write(decoded)
            test_path = os.path.join(self.TEST_FONT_DEST, name)
            with open(test_path, "wb") as f:
                f.write(decoded)
            extracted_fonts.append(name)
            return True

        for line in lines:
            line = line.strip()

            if line.startswith("[") and line.endswith("]"):
                if font_name and font_data:
                    save_font(font_name, font_data)
                in_fonts = (line.lower() == "[fonts]")
                font_name = None
                font_data = []
                continue

            if not in_fonts:
                continue

            if line.lower().startswith("fontname:"):
                if font_name and font_data:
                    save_font(font_name, font_data)
                font_name = line.split(":", 1)[1].strip()
                font_data = []
            else:
                font_data.append(line)

        if font_name and font_data:
            save_font(font_name, font_data)

        if extracted_fonts:
            print(f"Extracted and installed: {', '.join(extracted_fonts)}")
            print("Updating font cache...")
            subprocess.run(["fc-cache", "-fv"], check=False)

        return len(extracted_fonts)

    def process_uploaded_sub(self, ep_num, subtitle_file):
        ext = os.path.splitext(subtitle_file)[1]
        out_name = f'subtitle_{ep_num}{ext}'
        os.rename(subtitle_file, out_name)

        if self.is_ass(out_name):
            print(f"Extracting fonts from {out_name}...")
            count = self.extract_fonts_from_ass(out_name)
            if count == 0:
                print("No embedded fonts found in this ASS file.")
        else:
            ass_content = self.srt_to_ass(out_name)
            with open(out_name, 'w', encoding='utf-8') as f:
                f.write(ass_content)
            print(f"✔ Converted SRT→ASS: {os.path.basename(out_name)}")

        return out_name

    def sanitize_filename(self, name: str) -> str:
        return re.sub(r'[<>"/\\|?*]', '_', name)  # replace invalid filename chars

    # === Main batch preparation ===
    def prepare_batch(self):
        if not self.is_batch:
            # Non-batch: upload one subtitle
            if not self.episode_numbers or len(self.episode_numbers) != 1:
                raise ValueError("For non-batch, exactly one episode number.")

            ep_num = self.episode_numbers[0]
            print(f"Upload subtitle for episode {ep_num}:")
            uploaded = files.upload()
            if not uploaded:
                raise ValueError(f"No subtitle uploaded for episode {ep_num}!")
            self.batch_info['subtitles'][ep_num] = self.process_uploaded_sub(ep_num, list(uploaded.keys())[0])
            self.batch_info['selected_episodes'] = [{
                'index': 0,
                'path': 'single_file.mkv',
                'episode_num': ep_num,
                'subtitle': self.batch_info['subtitles'][ep_num]
            }]
        else:
            # Batch: fetch torrent metadata, select episodes, upload subtitles
            self.session = lt.session()
            self.session.listen_on(6881, 6891)
            params = {
                'save_path': '/content/data/',
                'storage_mode': lt.storage_mode_t(2),
            }
            self.handle = lt.add_magnet_uri(self.session, self.batch_info['torrent_link'], params)
            self.session.start_dht()
            print("Fetching metadata, please wait…")
            while not self.handle.has_metadata():
                time.sleep(1)
            self.torrent_info = self.handle.get_torrent_info()
            torrent_files = self.torrent_info.files()
            print("\nFiles in Torrent:")
            file_paths = {}
            for idx in range(torrent_files.num_files()):
                path = torrent_files.file_path(idx)
                file_paths[idx + 1] = path
                print(f"[{idx + 1}] {path}")
            selection = input("\nEnter indices of episodes to process (up to 3, comma-separated. For example: 2,6,7): ")
            selected_display_indices = [int(idx.strip()) for idx in selection.split(',') if idx.strip().isdigit()]
            if len(selected_display_indices) > 4:
                raise ValueError("You can select up to 4 episodes only.")
            selected_episodes = []
            for display_idx in selected_display_indices:
                real_idx = display_idx - 1
                if real_idx in range(torrent_files.num_files()):
                    path = file_paths[display_idx]

                    ep_num = input(f"\nFor file {path} (index {display_idx}):\nEnter episode number: ").strip()
                    if not ep_num:
                        ep_num = str(display_idx).zfill(2)
                    ep_num = self.sanitize_filename(ep_num)

                    print(f"Upload subtitle for episode {ep_num} (or skip):")
                    uploaded = files.upload()
                    subtitle_path = None
                    if uploaded:
                        subtitle_file = list(uploaded.keys())[0]
                        subtitle_path = self.process_uploaded_sub(ep_num, subtitle_file)
                    selected_episodes.append({
                        'index': real_idx,
                        'path': path,
                        'episode_num': ep_num,
                        'subtitle': subtitle_path
                    })
            self.batch_info['selected_episodes'] = selected_episodes
            self.batch_info['session'] = self.session
            self.batch_info['handle'] = self.handle
            self.batch_info['torrent_info'] = self.torrent_info
            print("\n✅ Selection complete. Selected episodes will be processed next.")

        print(f"\n🎯 Ready: {self.video_name} @ {', '.join(self.qualities)}")





