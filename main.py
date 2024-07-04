import os
import random
import subprocess
from youtube_search import YoutubeSearch
import yt_dlp

import cv2
import numpy as np
import subprocess
import json


def search_and_download_video(celebrity_name):
    results = YoutubeSearch(f"{celebrity_name} interview", max_results=5).to_dict()
    video_url = f"https://youtube.com{random.choice(results)['url_suffix']}"

    if not os.path.exists('downloads'):
        os.makedirs('downloads')

    output_path = os.path.join('downloads', f"{celebrity_name.replace(' ', '_')}.mp4")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    return output_path


def detect_face(image_path):
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.1, 4)
    return len(faces) > 0

def get_video_dimensions(video_path):
    command = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-count_packets',
        '-show_entries', 'stream=width,height',
        '-of', 'json',
        video_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return int(data['streams'][0]['width']), int(data['streams'][0]['height'])


def clip_video(video_path, duration, output_path):
    # Step 1: Detect scenes
    scene_command = [
        'ffmpeg',
        '-i', video_path,
        '-vf', 'select=\'gt(scene,0.4)\',showinfo',
        '-f', 'null',
        '-'
    ]
    scene_output = subprocess.run(scene_command, capture_output=True, text=True).stderr

    # Parse scene changes
    scene_changes = [float(line.split('pts_time:')[1].split()[0])
                     for line in scene_output.split('\n') if 'pts_time' in line]

    # Step 2: Check for faces in each scene
    start_time = 0
    for scene_time in scene_changes:
        frame_path = f'temp_frame_{scene_time}.jpg'
        frame_command = [
            'ffmpeg',
            '-ss', str(scene_time),
            '-i', video_path,
            '-frames:v', '1',
            frame_path
        ]
        subprocess.run(frame_command, check=True)

        if detect_face(frame_path):
            start_time = scene_time
            os.remove(frame_path)
            break

        os.remove(frame_path)

    # Get video dimensions
    width, height = get_video_dimensions(video_path)

    # Calculate crop parameters
    crop_width = min(width, int(height * 9 / 16))  # 9:16 aspect ratio
    x_offset = (width - crop_width) // 2

    # Step 3: Clip and crop the video from the detected face
    clip_command = [
        'ffmpeg',
        '-ss', str(start_time),
        '-i', video_path,
        '-t', str(duration),
        '-filter:v', f'crop={crop_width}:{height}:{x_offset}:0,scale=1080:1920',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-strict', 'experimental',
        output_path
    ]
    subprocess.run(clip_command, check=True)

    return output_path


def merge_clips(clip_paths, output_path):
    with open('temp_list.txt', 'w') as f:
        for path in clip_paths:
            f.write(f"file '{path}'\n")

    command = [
        'ffmpeg',
        '-f', 'concat',
        '-safe', '0',
        '-i', 'temp_list.txt',
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-strict', 'experimental',
        '-vf', 'scale=1080:1920',
        output_path
    ]
    subprocess.run(command, check=True)
    os.remove('temp_list.txt')


def generate_shorts(celebrity_names):
    clip_paths = []
    total_duration = 50
    clip_duration = total_duration / len(celebrity_names)

    try:
        for i, name in enumerate(celebrity_names):
            print(f"Processing {name}...")
            # video_path = search_and_download_video(name)
            video_path = os.path.join('downloads', f"{name.replace(' ', '_')}.mp4")
            clipped_video_path = f'temp_clip_{i}.mp4'
            clipped_video_path = clip_video(video_path, clip_duration, clipped_video_path)
            clip_paths.append(clipped_video_path)

        if not os.path.exists('output'):
            os.makedirs('output')

        print("Merging clips...")
        merge_clips(clip_paths, 'output/final_short.mp4')

        print("YouTube Short generated and saved to output/final_short.mp4")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

    finally:
        # Clean up temporary files
        for path in clip_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"Error removing temporary file {path}: {str(e)}")


# Example usage
celebrity_names = ["Tom Cruise", "Johnny Depp", "Chris Evans"]
generate_shorts(celebrity_names)