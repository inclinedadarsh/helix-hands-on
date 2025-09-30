import requests
import trafilatura
from github import Github
import base64
from youtube_transcript_api import YouTubeTranscriptApi
import re
from urllib.parse import urlparse
import sys


def detect_url_type(url):
    if "github.com" in url:
        return "github"
    elif "youtube.com" in url:
        return "youtube"
    else:
        return "web"
    
def process_web_url(url):
    try:
        downloaded = trafilatura.fetch_url(url)
        
        if not downloaded:
            return "Error: Could not fetch webpage"
        
        markdown = trafilatura.extract(
            downloaded,
            output_format='markdown',
            include_comments=False,
            include_tables=True,
            include_images=True,
            include_links=True
        )
        
        if not markdown:
            return "Error: Could not process markdwon for give page"
        
        return markdown
    
    except Exception as e:
        return f"Error processing web URL: {e}"
    
def process_github_url(url):
    try:
        parts = url.split("github.com/")[1].split("/")
        user, repo_name = parts[0], parts[1].replace('.git', '')
        
        g = Github()
        
        repo = g.get_repo(f"{user}/{repo_name}")
        
        markdown_output = f"# Repository: {user}/{repo_name}\n\n"
        markdown_output += f"**URL:** https://github.com/{user}/{repo_name}\n\n"
        markdown_output += "---\n\n"
        
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode('utf-8')
            markdown_output += "## README\n\n"
            markdown_output += readme_content + "\n\n"
        except Exception:
            # README not found
            markdown_output += "## README\n\n*No README found*\n\n"
        
        return markdown_output
    
    except Exception as e:
        return f"Error accessing GitHub repository: {e.status} - {e.data.get('message', str(e))}"
    except IndexError:
        return "Error: Invalid GitHub URL format. Expected format: https://github.com/user/repo"
    except Exception as e:
        return f"Error processing GitHub URL: {e}"
            
def process_youtube_url(url):
    try:
        # Extract video ID
        video_id = None
        if 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]
        else:
            match = re.search(r"(?:v=|embed/)([\w-]+)", url)
            if match:
                video_id = match.group(1)
        
        if not video_id:
            return "Error: Could not extract video ID from URL"
        
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        
        markdown = f"# YouTube Transcript: {video_id}\n\n"
        markdown += f"**URL:** {url}\n\n"
        markdown += "---\n\n"
        markdown += "## Transcript\n\n"
        
        for t in transcript:
            timestamp = format_timestamp(t['start'])
            markdown += f"**[{timestamp}]** {t['text']}\n\n"
        
        return markdown
    except Exception as e:
        return f"Error processing YouTube URL: {e}\n\nNote: Make sure the video has captions/subtitles available."

def format_timestamp(seconds):
    """Convert seconds to MM:SS or HH:MM:SS format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"

def url_to_markdown(url):
    url_type = detect_url_type(url)
    
    if url_type == "web":
        return process_web_url(url)
    elif url_type == "github":
        return process_github_url(url)
    elif url_type == "youtube":
        return process_youtube_url(url)
    else:
        raise ValueError("Unknown URL type")

def init():
    """
    Initialize the script by asking the user for a URL.
    Returns:
        str: The URL entered by the user.
    """
    url = input("Enter a URL: ").strip()
    return url

if __name__ == "__main__":
    # Initialize and get URL
    url = init()
    
    # Process the URL and get Markdown
    markdown = url_to_markdown(url)
    
    # Print the Markdown directly
    print(markdown)

       
        
        
        
    
