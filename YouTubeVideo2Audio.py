import os
import yt_dlp
#brew install ffmpeg
#pip install yt-dlp 

def download_audio_from_youtube(video_url, output_path):
    """
    Downloads audio from a YouTube video and saves it to the specified output path.
    
    :param video_url: URL of the YouTube video
    :param output_path: Path to save the audio file
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_path, '%(title)s.%(ext)s'),
        'noplaylist': True,  # Do not download playlists
        'verbose': True,  # Print verbose output for debugging
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192', # Standard quality
        }],
    }

    try:
        print("Starting download... (This may take a moment)")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        print("Audio downloaded successfully!")
    except yt_dlp.utils.DownloadError as e:
        # Check for the specific ffmpeg error to provide a more helpful message.
        if "ffmpeg" in str(e).lower() and "not found" in str(e).lower():
            print("\n[ERROR] FFmpeg not found.")
            print("This script requires FFmpeg to convert the downloaded audio to MP3.")
            print("Please install it from https://ffmpeg.org/download.html and ensure it's in your system's PATH.")
        else:
            print(f"\nError: Failed to download or process the video.")
            print(f"Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    video_url = input("Enter the YouTube video URL: ")
    output_path = input("Enter the output directory path: ")

    if not os.path.exists(output_path):
        os.makedirs(output_path, exist_ok=True)

    download_audio_from_youtube(video_url, output_path)