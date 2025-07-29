import os
import logging
import re
import yt_dlp
from groq import Groq

# --- Configuration ---
# To use this script, you need to install the required libraries:
# pip install yt-dlp groq python-dotenv
# You also need FFmpeg for audio extraction: https://ffmpeg.org/download.html
# Set your Groq API key in a .env file or as an environment variable:
# GROQ_API_KEY="your_api_key_here"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class YouTubeProcessor:
    """
    A class to process YouTube videos for audio, transcripts, summaries, and MCQs.
    """

    def __init__(self, video_url: str, output_path: str):
        """
        Initializes the processor with the video URL and output path.

        :param video_url: URL of the YouTube video.
        :param output_path: Directory to save output files.
        """
        self.video_url = video_url
        self.output_path = output_path
        self.video_title = self._get_video_title()
        if not self.video_title:
            raise ValueError("Could not retrieve video title. Please check the URL.")

        # Initialize Groq client
        try:
            self.groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        except Exception:
            self.groq_client = None
            logging.warning("Could not initialize Groq client. Ensure GROQ_API_KEY is set.")

    def _get_video_title(self) -> str | None:
        """Extracts the video title without downloading the video."""
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
                info_dict = ydl.extract_info(self.video_url, download=False)
                # Sanitize title to be a valid filename
                title = info_dict.get('title', 'Untitled_Video')
                return re.sub(r'[\\/*?:"<>|]', "", title)
        except Exception as e:
            logging.error(f"Failed to get video title: {e}")
            return None

    def download_audio(self):
        """Downloads audio from the YouTube video as an MP3 file."""
        logging.info(f"Starting audio download for: {self.video_title}")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(self.output_path, f'{self.video_title}.%(ext)s'),
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.video_url])
            logging.info(f"Audio downloaded successfully to {self.output_path}")
        except yt_dlp.utils.DownloadError as e:
            if "ffmpeg" in str(e).lower():
                logging.error("FFmpeg not found. Please install it and ensure it's in your system's PATH.")
            else:
                logging.error(f"Download error: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred during audio download: {e}")

    def get_transcript(self) -> str | None:
        """
        Downloads and returns the full video transcript.
        It saves the transcript to a .txt file.
        """
        logging.info(f"Fetching transcript for: {self.video_title}")
        subtitle_path_template = os.path.join(self.output_path, f'{self.video_title}.%(ext)s')
        ydl_opts = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en'],
            'skip_download': True,
            'outtmpl': subtitle_path_template,
            'noplaylist': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.video_url, download=True)
                sub_file = info.get('requested_subtitles', {}).get('en', {}).get('filepath')
                if not sub_file or not os.path.exists(sub_file):
                    # Fallback for auto-subs with different naming
                    sub_file = os.path.join(self.output_path, f"{self.video_title}.en.vtt")

                if not os.path.exists(sub_file):
                    logging.warning("Could not find a subtitle file.")
                    return None

                with open(sub_file, 'r', encoding='utf-8') as f:
                    vtt_content = f.read()

                transcript = self._clean_vtt(vtt_content)
                transcript_filename = os.path.join(self.output_path, f"{self.video_title}_transcript.txt")
                with open(transcript_filename, 'w', encoding='utf-8') as f:
                    f.write(transcript)

                logging.info(f"Transcript saved to {transcript_filename}")
                os.remove(sub_file) # Clean up the .vtt file
                return transcript

        except Exception as e:
            logging.error(f"Failed to get transcript: {e}")
            return None

    def _clean_vtt(self, vtt_content: str) -> str:
        """A helper method to clean VTT content into a readable transcript."""
        lines = vtt_content.splitlines()
        transcript_lines = []
        for line in lines:
            if line.strip().startswith('WEBVTT') or '-->' in line or not line.strip():
                continue
            cleaned_line = re.sub(r'<[^>]+>', '', line).strip()
            if cleaned_line and (not transcript_lines or transcript_lines[-1] != cleaned_line):
                transcript_lines.append(cleaned_line)
        return "\n".join(transcript_lines)

    def _call_groq_api(self, prompt: str) -> str | None:
        """Generic method to call the Groq API."""
        if not self.groq_client:
            logging.error("Groq client not available. Cannot make API call.")
            return None
        try:
            logging.info("Sending request to Groq API (Llama-3-70b)...")
            chat_completion = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama3-70b-8192",
            )
            response = chat_completion.choices[0].message.content
            logging.info("Successfully received response from Groq API.")
            return response
        except Exception as e:
            logging.error(f"Groq API call failed: {e}")
            return None

    def generate_summary(self, transcript: str):
        """Generates a one-page summary of the transcript using Groq."""
        prompt = f"""
        Analyze the following video transcript and provide a concise, one-page summary.
        Structure the output with:
        1.  **Overall Summary:** A brief paragraph of the main points.
        2.  **Key Topics & Keywords:** A bulleted list of important topics and keywords.
        3.  **Actionable Takeaways:** A bulleted list of key conclusions or advice.

        Remove all conversational fluff and filler words.

        --- TRANSCRIPT ---
        {transcript}
        """
        summary = self._call_groq_api(prompt)
        if summary:
            summary_filename = os.path.join(self.output_path, f"{self.video_title}_summary.txt")
            with open(summary_filename, 'w', encoding='utf-8') as f:
                f.write(summary)
            logging.info(f"Summary saved to {summary_filename}")

    def generate_mcqs(self, transcript: str):
        """Generates 20 MCQs based on the transcript using Groq."""
        prompt = f"""
        Based on the following transcript, generate exactly 20 multiple-choice questions (MCQs) to test comprehension.
        For each question, provide:
        1. The question.
        2. Four options (A, B, C, D).
        3. The correct answer (e.g., "Correct Answer: C").
        4. A brief, clear reason explaining why the answer is correct.

        --- TRANSCRIPT ---
        {transcript}
        """
        mcqs = self._call_groq_api(prompt)
        if mcqs:
            mcqs_filename = os.path.join(self.output_path, f"{self.video_title}_mcqs.txt")
            with open(mcqs_filename, 'w', encoding='utf-8') as f:
                f.write(mcqs)
            logging.info(f"MCQs saved to {mcqs_filename}")


def main():
    """Main function to run the script."""
    try:
        video_url = input("Enter the YouTube video URL: ")
        output_path = input("Enter the output directory path (e.g., ./output): ")

        if not os.path.exists(output_path):
            os.makedirs(output_path)

        processor = YouTubeProcessor(video_url, output_path)

        print("\nWhat would you like to do?")
        print("1. Download Audio only")
        print("2. Get Transcript only")
        print("3. Get Summary and MCQs (requires transcript)")
        print("4. All of the above")
        choice = input("Enter your choice (1-4): ")

        if choice in ['1', '4']:
            processor.download_audio()

        transcript = None
        if choice in ['2', '3', '4']:
            transcript = processor.get_transcript()

        if choice in ['3', '4'] and transcript:
            if processor.groq_client:
                processor.generate_summary(transcript)
                processor.generate_mcqs(transcript)
            else:
                logging.warning("Skipping Summary/MCQs because Groq client is not configured.")

        logging.info("Processing complete.")

    except (ValueError, TypeError) as e:
        logging.error(f"Input Error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred in main: {e}")


if __name__ == "__main__":
    main()

