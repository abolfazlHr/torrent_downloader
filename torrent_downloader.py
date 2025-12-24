import subprocess
import zipfile
import time
import datetime
import shutil
import libtorrent as lt
from tqdm.notebook import tqdm
import os
import re

def get_font_map():
    return {
        #"IRCompset": ("Vazirmatn RD ExtraBold", 0.71),
        #"IRAN Rounded": ("Vazirmatn RD ExtraBold", 0.94),
        #"Estedad-FD Bold": ("Vazirmatn RD ExtraBold", 1.02),
        #"Estedad Black": ("Vazirmatn RD ExtraBold", 1.04),
        #"Estedad SemiBold": ("Vazirmatn RD ExtraBold", 1.03),
        #"Estedad Bold": ("Vazirmatn RD ExtraBold", 1.02),
        #"Estedad-FD ExtraBold": ("Vazirmatn RD ExtraBold", 1.03),
        #"Lalezar": ("Vazirmatn RD ExtraBold", 0.84),
        #"b koodak": ("Vazirmatn RD ExtraBold", 0.82),
        #"Gandom FD": ("Vazirmatn RD ExtraBold", 0.96),
        #"IRKoodak": ("Vazirmatn RD ExtraBold", 0.84),
        #"B Yekan+": ("Vazirmatn RD ExtraBold", 0.91),
        #"B Yekan+ Bold": ("Vazirmatn RD ExtraBold", 0.91),
        #"IRKoodak": ("Vazirmatn RD ExtraBold", 0.84),
    }

def aria2c_torrent(torrent_link, save_path):
    os.makedirs(save_path, exist_ok=True)
    if torrent_link.endswith('.torrent'):
        if os.path.exists('torrent.torrent'):
            os.remove('torrent.torrent')
        wget.download(torrent_link, 'torrent.torrent')
        torrent_input = 'torrent.torrent'
    else:
        torrent_input = torrent_link
    print(torrent_input)
    print(datetime.datetime.now())
    print('Starting Torrent Download...')
    command = [
        "aria2c", torrent_input,
        "--dir", save_path,
        "--console-log-level=warn",
        "--summary-interval=1",
        "--seed-time=0",
        "--bt-seed-unverified=false",
        "--max-connection-per-server=10",
        "--split=10",
        "--min-split-size=1M",
        "--enable-color=false"
    ]
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, universal_newlines=True
    )
    pbar = tqdm(total=100)
    percent_re = re.compile(r'\((\d+(\.\d+)?)%\)')
    for line in iter(proc.stdout.readline, ''):
        if not line:
            break
        line_str = line.strip()
        m = percent_re.search(line_str)
        if m:
            pct = float(m.group(1))
            pbar.n = int(pct)
            pbar.refresh()
    proc.stdout.close()
    proc.wait()
    pbar.n = 100
    pbar.refresh()
    pbar.close()
    print("Download complete.")
    files = [
        f for f in os.listdir(save_path)
        if os.path.isfile(os.path.join(save_path, f))
    ]
    if not files:
        print("No files found.")
        return None
    files.sort(
        key=lambda f: os.path.getsize(os.path.join(save_path, f)),
        reverse=True
    )
    return os.path.join(save_path, files[0])

def download_torrent(torrent_link, save_path):
    params = {
        'save_path': save_path,
        'storage_mode': lt.storage_mode_t(2),
    }
    ses = lt.session()
    ses.listen_on(6881, 6891)
    ses.set_settings({
        'active_downloads': 10,
        'active_limit': 10,
        'active_seeds': 10,
        'max_connections': 1000,
        'max_uploads': 100,
        'connections_limit': 500,
        'unchoke_slots_limit': 50,
        'download_rate_limit': 0,
        'upload_rate_limit': 0,
        'dht_announce_interval': 30,
        'dht_request_interval': 15,
        'peer_connect_timeout': 2000,
    })
    if torrent_link.endswith('.torrent'):
        import wget
        from torf import Torrent
        if os.path.exists('torrent.torrent'):
            os.remove('torrent.torrent')
        wget.download(torrent_link, 'torrent.torrent')
        t = Torrent.read('torrent.torrent')
        torrent_link = str(t.magnet(name=True, size=False, trackers=False, tracker=False))
    print(torrent_link)
    handle = lt.add_magnet_uri(ses, torrent_link, params)
    trackers = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://tracker.internetwarriors.net:1337/announce",
        "udp://exodus.desync.com:6969/announce",
        "udp://tracker.leechers-paradise.org:6969/announce",
        "udp://tracker.torrent.eu.org:451/announce",
        "udp://tracker.cyberia.is:6969/announce",
        "http://nyaa.tracker.wf:7777/announce",
        "udp://tracker.tiny-vps.com:6969/announce",
        "udp://open.stealth.si:80/announce",
    ]
    for tracker in trackers:
        handle.add_tracker(tracker)
    handle.set_sequential_download(0)
    handle.set_max_connections(1000)
    handle.set_upload_limit(0)
    handle.set_download_limit(0)
    handle.set_priority(7)
    ses.start_dht()
    begin = time.time()
    print(datetime.datetime.now())
    while not handle.has_metadata():
        time.sleep(1)
    print('Starting Torrent Download...')
    print("Starting", handle.name())
    pbar = tqdm(total=100)
    while handle.status().state != lt.torrent_status.seeding:
        s = handle.status()
        pbar.set_postfix({
            'Progress': f'{s.progress * 100:.2f}%',
            'Down': f'{s.download_rate / 1000:.1f} kb/s',
            'Up': f'{s.upload_rate / 1000:.1f} kB/s',
            'Peers': s.num_peers
        }, refresh=False)
        pbar.n = int(s.progress * 100)
        pbar.refresh()
        time.sleep(10)
    end = time.time()
    print(handle.name(), " COMPLETE")
    print("Elapsed Time: ", int((end - begin) // 60), "min :", int((end - begin) % 60), "sec")
    return os.path.join(save_path, handle.name())

def add_subtitles(
    input_video,
    subtitle_file,
    encode_type='hard',
    output_encode='x264',
    crf=25,
    size_string=None,
    remove_sub=False,
    audio_streams=None
):
    subtitle_file = subtitle_file.replace('"', '')
    vf_filter = f"ass={subtitle_file},ass=main.ass"
    if size_string:
        vf_filter += f",scale={size_string}"

    if encode_type == 'hard':
        cmd = [
            "ffmpeg",
            "-i", input_video,
            "-map", "0:v:0"
        ]
        if audio_streams:
            for stream in audio_streams:
                cmd += ["-map", stream]
        else:
            best_audio_idx = get_best_audio_stream(input_video)
            cmd += ["-map", f"0:a:{best_audio_idx}"]
        cmd += [
            "-c:v", f"lib{output_encode}",
            "-preset", "faster",
            # "-tune", "ssim",
            # "-tune", "animation",
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "80k",
            "-ac", "2",
            "-sn",
            "-vf", f"\"{vf_filter}\""
        ]
    else:
        cmd = [
            "ffmpeg",
            "-i", input_video,
            "-i", subtitle_file,
            "-map", "1",
            "-c:s", "srt",
            "-metadata:s:s:1", "language=per[Persian]",
            "-vf", '"ass=main.ass"'
        ]
        if remove_sub:
            cmd += ["-map", "0:v", "-map", "0:a"]
        else:
            cmd += ["-map", "0"]
        if output_encode is not None:
            cmd += [
                "-c:v", f"lib{output_encode}",
                "-tune", "ssim",
                "-crf", str(crf),
                "-c:a", "aac",
                "-b:a", "128k"
            ]
        if size_string is not None:
            cmd += ["-s", size_string]

    shell_cmd = ' '.join(cmd)
    print(shell_cmd)
    return shell_cmd

def get_mkv_files(root_dir):
    mkv_files = []
    for dir_, _, files in os.walk(root_dir):
        for file_name in files:
            if file_name.endswith(".mkv"):
                rel_file = os.path.relpath(os.path.join(dir_, file_name), root_dir)
                mkv_files.append(rel_file)
    return mkv_files

def get_best_audio_stream(input_video):
    clean_input = input_video.strip('"').strip("'")
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index:stream_tags=language",
        "-of", "csv=p=0",
        clean_input
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"[ERROR] ffprobe execution failed: {e}")
        return 0
    if result.returncode != 0:
        print(f"[ERROR] ffprobe returned error:\n{result.stderr.strip()}")
        return 0
    lines = result.stdout.strip().splitlines()
    if not lines:
        print("[WARN] No audio streams found.")
        return 0
    audio_streams = []
    for line in lines:
        parts = line.split(',')
        global_idx = int(parts[0])
        lang = parts[1] if len(parts) > 1 else ''
        audio_streams.append((global_idx, lang))
    for i, (g_idx, lang) in enumerate(audio_streams):
        if lang == 'jpn':
            print(f"Selected audio stream: {i} (jpn, global stream index {g_idx})")
            return i
    print(f"Selected audio stream: 0 (default, global stream index {audio_streams[0][0]})")
    return 0

def list_audio_streams(input_video):
    clean_input = input_video.strip('"').strip("'")
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index:stream_tags=language",
        "-of", "csv=p=0",
        clean_input
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"[ERROR] ffprobe returned error:\n{result.stderr.strip()}")
        return []
    streams = result.stdout.strip().splitlines()
    print("\n🎵 Available audio streams:\n")
    parsed = []
    for idx, line in enumerate(streams):
        stream_idx, lang = (line.split(",") + ["unknown"])[:2]
        print(f"[{idx}] | Language: {lang}")
        parsed.append((idx, int(stream_idx), lang))
    return parsed

