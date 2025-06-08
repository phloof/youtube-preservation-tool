#!/usr/bin/env python3
"""
YouTube Channel Video Archiver
Scrapes video links from Filmot, searches for archived versions using the findyoutubevideo API, and downloads them.
"""

import requests
import re
import time
import os
import json
from urllib.parse import urljoin, urlparse, parse_qs
from pathlib import Path
import subprocess
import sys
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from bs4 import BeautifulSoup
import logging

# Fix Windows console encoding issues
if sys.platform.startswith('win'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'replace')

# Setup logging with UTF-8 encoding to handle Unicode characters
logging.basicConfig(
    level=logging.DEBUG,  # Enable debug logging to help identify metadata extraction issues
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('video_archiver.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class VideoInfo:
    """Class to store video information"""
    video_id: str
    title: str
    original_url: str
    filmot_url: str
    upload_date: Optional[str] = None
    view_count: Optional[str] = None
    like_count: Optional[str] = None
    dislike_count: Optional[str] = "n/a"  # Default to n/a since YouTube removed public dislikes
    archived_sources: List[Dict] = field(default_factory=list)
    api_response: Dict = field(default_factory=dict)

class VideoArchiver:
    def __init__(self, download_folder: str = "downloaded_videos", debug_mode: bool = False):
        self.download_folder = Path(download_folder)
        self.download_folder.mkdir(exist_ok=True)
        self.debug_mode = debug_mode
        
        # Set logging level based on debug mode
        if not debug_mode:
            logging.getLogger().setLevel(logging.INFO)
        
        # Create session with headers to avoid being blocked
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })



    def _extract_videos_from_soup(self, soup: BeautifulSoup, base_url: str) -> List[VideoInfo]:
        """Extract video information from BeautifulSoup object with metadata"""
        videos = []
        
        # Look for video containers - Filmot usually has structured layouts
        video_containers = soup.find_all(['tr', 'div', 'li'], class_=re.compile(r'video|result|item', re.I))
        
        if not video_containers:
            # Fallback to finding links
            video_containers = soup.find_all('a', href=re.compile(r'(youtube\.com/watch\?v=|/video/)'))
        
        seen_video_ids = set()
        
        for container in video_containers:
            # Find the main video link
            if container.name == 'a':
                link = container
            else:
                link = container.find('a', href=re.compile(r'(youtube\.com/watch\?v=|/video/)'))
            
            if not link:
                continue
                
            href = link.get('href')
            if not href:
                continue
            
            # Extract video ID
            video_id = None
            youtube_match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', href)
            if youtube_match:
                video_id = youtube_match.group(1)
            else:
                filmot_match = re.search(r'/video/([a-zA-Z0-9_-]{11})', href)
                if filmot_match:
                    video_id = filmot_match.group(1)
            
            if not video_id or video_id in seen_video_ids:
                continue
                
            seen_video_ids.add(video_id)
            
            # Extract title
            title = link.get_text(strip=True)
            
            # Look for title in nearby elements if not found
            if not title or len(title) < 3 or title in ['↗', '→', '»', 'next', 'more']:
                title_elem = container.find(['h1', 'h2', 'h3', 'h4', 'h5', 'span', 'div'], 
                                          class_=re.compile(r'title|name', re.I))
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            # Skip if title is still invalid (likely pagination elements)
            if not title or len(title) < 3 or title in ['↗', '→', '»', 'next', 'more', 'prev', 'previous']:
                continue
            
            # Extract upload date, view count, likes, and dislikes with improved logic
            upload_date = None
            view_count = None
            like_count = None
            dislike_count = "n/a"  # Default for dislikes
            
            # Get all text content for analysis
            container_text = container.get_text()
            
            # Try to find specific elements first, then fall back to text patterns
            # Look for date in various formats and locations - Filmot often uses ISO format
            date_element = container.find(text=re.compile(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\w{3}\s+\d{1,2},?\s+\d{4}'))
            if date_element:
                date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\w{3}\s+\d{1,2},?\s+\d{4})', str(date_element))
                if date_match:
                    upload_date = date_match.group(1)
            
            # Look for view count in various formats
            view_element = container.find(text=re.compile(r'[\d,]+\s*(?:views?|V|visualiz)', re.I))
            if view_element:
                view_match = re.search(r'([\d,]+)', str(view_element))
                if view_match:
                    view_count = view_match.group(1)
            
            # Look for likes in various formats
            like_element = container.find(text=re.compile(r'[\d,]+\s*(?:likes?|👍|L)', re.I))
            if like_element:
                like_match = re.search(r'([\d,]+)', str(like_element))
                if like_match:
                    like_count = like_match.group(1)
            
            # Look for dislikes in various formats (if available)
            dislike_element = container.find(text=re.compile(r'[\d,]+\s*(?:dislikes?|👎|D)', re.I))
            if dislike_element:
                dislike_match = re.search(r'([\d,]+)', str(dislike_element))
                if dislike_match:
                    dislike_count = dislike_match.group(1)
            
            # Fallback to broader text patterns if specific elements not found
            if not upload_date:
                # Comprehensive date patterns prioritizing full dates as they appear on Filmot
                date_patterns = [
                    # Context-aware patterns (highest priority)
                    r'(?i)(?:upload(?:ed)?|publish(?:ed)?|date)[\s\-:]*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)',  # Context: ISO format
                    r'(?i)(?:upload(?:ed)?|publish(?:ed)?|date)[\s\-:]*(\d{1,2}/\d{1,2}/\d{4})',  # Context: US format
                    r'(?i)(?:upload(?:ed)?|publish(?:ed)?|date)[\s\-:]*(\w{3,9}\s+\d{1,2},?\s+\d{4})',  # Context: Written format
                    
                    # Full date patterns (standalone)
                    r'(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)',  # ISO format with optional time
                    r'(\d{1,2}/\d{1,2}/\d{4})',  # US date: M/D/YYYY or MM/DD/YYYY
                    r'(\d{4}/\d{2}/\d{2})',  # Alternative ISO: YYYY/MM/DD
                    r'(\w{3,9}\s+\d{1,2},?\s+\d{4})',  # Jan 1, 2023 or January 1 2023
                    r'(\d{1,2}\s+\w{3,9}\s+\d{4})',  # 1 Jan 2023 or 1 January 2023
                    r'(\d{2}-\d{2}-\d{4})',  # DD-MM-YYYY or MM-DD-YYYY
                    
                    # Partial date patterns (lower priority, only if no full date found)
                    r'(\w{3,9}\s+\d{4})',  # Month Year: Jan 2023, January 2023
                    r'(\d{4}-\d{2})',  # Year-Month: 2023-01
                    r'(\d{2}/\d{4})',  # MM/YYYY
                ]
                
                for pattern in date_patterns:
                    date_match = re.search(pattern, container_text)
                    if date_match:
                        potential_date = date_match.group(1).strip()
                        # Prioritize full dates (with day) over partial dates
                        if len(potential_date) >= 8:  # Full dates should be at least 8 characters
                            upload_date = potential_date
                            logger.debug(f"Found full date for {video_id}: '{potential_date}'")
                            break
                        elif len(potential_date) >= 6 and not upload_date:  # Accept partial dates as fallback
                            upload_date = potential_date
                            logger.debug(f"Found partial date for {video_id}: '{potential_date}'")
                            # Continue looking for a full date
            
            # Fallback patterns for views, likes, and dislikes
            if not view_count:
                view_patterns = [
                    r'Views?:\s*([\d,]+)',  # "Views: 123,456"
                    r'([\d,]+)\s*views?',  # "123,456 views"
                    r'([\d,]+)\s*visualiz',  # "123,456 visualizations"
                    r'([\d,]+)\s*V(?!\w)',  # "123,456 V" (but not "VIDeo" etc)
                ]
                
                for pattern in view_patterns:
                    view_match = re.search(pattern, container_text, re.I)
                    if view_match:
                        potential_count = view_match.group(1)
                        if ',' in potential_count or len(potential_count.replace(',', '')) > 2:
                            view_count = potential_count
                            break
            
            if not like_count:
                like_patterns = [
                    r'Likes?:\s*([\d,]+)',  # "Likes: 123,456"
                    r'([\d,]+)\s*likes?',  # "123,456 likes"
                    r'([\d,]+)\s*👍',  # "123,456 👍"
                    r'👍\s*([\d,]+)',  # "👍 123,456"
                    r'([\d,]+)\s*L(?!\w)',  # "123,456 L" (but not "Like" etc)
                ]
                
                for pattern in like_patterns:
                    like_match = re.search(pattern, container_text, re.I)
                    if like_match:
                        potential_count = like_match.group(1)
                        if ',' in potential_count or len(potential_count.replace(',', '')) > 1:
                            like_count = potential_count
                            break
            
            if dislike_count == "n/a":  # Only try if still default
                dislike_patterns = [
                    r'Dislikes?:\s*([\d,]+)',  # "Dislikes: 123,456"
                    r'([\d,]+)\s*dislikes?',  # "123,456 dislikes"
                    r'([\d,]+)\s*👎',  # "123,456 👎"
                    r'👎\s*([\d,]+)',  # "👎 123,456"
                    r'([\d,]+)\s*D(?!\w)',  # "123,456 D" (but not "Dislike" etc)
                ]
                
                for pattern in dislike_patterns:
                    dislike_match = re.search(pattern, container_text, re.I)
                    if dislike_match:
                        potential_count = dislike_match.group(1)
                        if ',' in potential_count or len(potential_count.replace(',', '')) > 1:
                            dislike_count = potential_count
                            break
            
            # Debug logging to help identify extraction issues
            if video_id and (upload_date or view_count or like_count or (dislike_count and dislike_count != "n/a")):
                logger.debug(f"Extracted metadata for {video_id}: date={upload_date}, views={view_count}, likes={like_count}, dislikes={dislike_count}")
            elif video_id:
                # Log some container text to help debug
                debug_text = container_text.strip()[:200] + "..." if len(container_text) > 200 else container_text.strip()
                logger.debug(f"No metadata extracted for {video_id}. Container text: {debug_text}")
            
            original_url = f"https://www.youtube.com/watch?v={video_id}"
            filmot_url = href if href.startswith('http') else urljoin(base_url, href)
            
            video_info = VideoInfo(
                video_id=video_id,
                title=self.sanitize_filename(title),
                original_url=original_url,
                filmot_url=filmot_url,
                upload_date=upload_date,
                view_count=view_count,
                like_count=like_count,
                dislike_count=dislike_count
            )
            
            videos.append(video_info)
        
        return videos

    def enhance_video_metadata(self, video_info: VideoInfo) -> VideoInfo:
        """Fetch additional metadata from individual Filmot video page"""
        if not video_info.filmot_url:
            return video_info
            
        try:
            logger.debug(f"Fetching enhanced metadata for {video_info.video_id}")
            response = self.session.get(video_info.filmot_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for metadata in the video page
            page_text = soup.get_text()
            
            # Try to find upload date if not already found
            if not video_info.upload_date:
                # Look for various date formats on the page - prioritize full dates
                date_patterns = [
                    r'Upload(?:ed)?\s*:?\s*(\d{4}-\d{2}-\d{2})',  # Uploaded: YYYY-MM-DD
                    r'Publish(?:ed)?\s*:?\s*(\d{4}-\d{2}-\d{2})',  # Published: YYYY-MM-DD
                    r'Date\s*:?\s*(\d{4}-\d{2}-\d{2})',  # Date: YYYY-MM-DD
                    r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD anywhere
                    r'Upload(?:ed)?\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',  # Uploaded: M/D/YYYY
                    r'Publish(?:ed)?\s*:?\s*(\d{1,2}/\d{1,2}/\d{4})',  # Published: M/D/YYYY
                    r'(\d{1,2}/\d{1,2}/\d{4})',  # M/D/YYYY anywhere
                    r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY anywhere
                    r'Upload(?:ed)?\s*:?\s*(\w{3}\s+\d{1,2},?\s+\d{4})',  # Uploaded: Mon DD, YYYY
                    r'Publish(?:ed)?\s*:?\s*(\w{3}\s+\d{1,2},?\s+\d{4})',  # Published: Mon DD, YYYY
                    r'(\w{3}\s+\d{1,2},?\s+\d{4})',  # Mon DD, YYYY anywhere
                    r'(\d{1,2}\s+\w{3}\s+\d{4})',  # DD Mon YYYY
                    r'Upload(?:ed)?\s*:?\s*(\w{3}\s+\d{4})',  # Uploaded: Mon YYYY (partial)
                    r'(\w{3}\s+\d{4})',  # Mon YYYY (partial)
                    r'(\d{4}-\d{2})',  # YYYY-MM (partial)
                ]
                
                for pattern in date_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        potential_date = match.group(1)
                        # Prefer full dates over partial ones
                        if len(potential_date) >= 8:  # Full date should be at least 8 chars
                            video_info.upload_date = potential_date
                            logger.debug(f"Found full upload date for {video_info.video_id}: {video_info.upload_date}")
                            break
                        elif len(potential_date) > 4 and not video_info.upload_date:  # Accept partial if no full date found
                            video_info.upload_date = potential_date
                            logger.debug(f"Found partial upload date for {video_info.video_id}: {video_info.upload_date}")
                            # Don't break here, keep looking for full date
            
            # Try to find view count if not already found
            if not video_info.view_count:
                view_patterns = [
                    r'Views?\s*:?\s*([\d,]+)',
                    r'Visualiz\w*\s*:?\s*([\d,]+)',
                    r'([\d,]+)\s*(?:views?|visualiz)',
                ]
                
                for pattern in view_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        potential_count = match.group(1)
                        # Ensure it's a reasonable view count
                        if ',' in potential_count or len(potential_count.replace(',', '')) > 2:
                            video_info.view_count = potential_count
                            logger.debug(f"Found view count for {video_info.video_id}: {video_info.view_count}")
                            break
            
            # Try to find like count if not already found
            if not video_info.like_count:
                like_patterns = [
                    r'Likes?\s*:?\s*([\d,]+)',
                    r'([\d,]+)\s*likes?',
                    r'([\d,]+)\s*👍',
                    r'👍\s*([\d,]+)',
                ]
                
                for pattern in like_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        potential_count = match.group(1)
                        # Ensure it's a reasonable like count
                        if ',' in potential_count or len(potential_count.replace(',', '')) > 0:
                            video_info.like_count = potential_count
                            logger.debug(f"Found like count for {video_info.video_id}: {video_info.like_count}")
                            break
            
            # Try to find dislike count if still default
            if video_info.dislike_count == "n/a":
                dislike_patterns = [
                    r'Dislikes?\s*:?\s*([\d,]+)',
                    r'([\d,]+)\s*dislikes?',
                    r'([\d,]+)\s*👎',
                    r'👎\s*([\d,]+)',
                ]
                
                for pattern in dislike_patterns:
                    match = re.search(pattern, page_text, re.I)
                    if match:
                        potential_count = match.group(1)
                        # Ensure it's a reasonable dislike count
                        if ',' in potential_count or len(potential_count.replace(',', '')) > 0:
                            video_info.dislike_count = potential_count
                            logger.debug(f"Found dislike count for {video_info.video_id}: {video_info.dislike_count}")
                            break
            
            # Small delay to be respectful
            time.sleep(0.5)
            
        except Exception as e:
            logger.debug(f"Could not enhance metadata for {video_info.video_id}: {str(e)}")
        
        return video_info

    def standardize_date_format(self, date_str: str) -> Dict[str, str]:
        """Standardize and validate date format, return info about completeness"""
        if not date_str:
            return {'date': None, 'format': 'none', 'completeness': 'none'}
        
        date_str = date_str.strip()
        
        # Check what type of date we have
        if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return {'date': date_str, 'format': 'ISO', 'completeness': 'full'}
        elif re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_str):
            return {'date': date_str, 'format': 'US', 'completeness': 'full'}
        elif re.match(r'\w{3}\s+\d{1,2},?\s+\d{4}', date_str):
            return {'date': date_str, 'format': 'written', 'completeness': 'full'}
        elif re.match(r'\d{1,2}\s+\w{3}\s+\d{4}', date_str):
            return {'date': date_str, 'format': 'written_dd', 'completeness': 'full'}
        elif re.match(r'\w{3}\s+\d{4}', date_str):
            return {'date': date_str, 'format': 'month_year', 'completeness': 'partial'}
        elif re.match(r'\d{4}-\d{2}', date_str):
            return {'date': date_str, 'format': 'year_month', 'completeness': 'partial'}
        elif re.match(r'\d{4}', date_str):
            return {'date': date_str, 'format': 'year_only', 'completeness': 'minimal'}
        else:
            return {'date': date_str, 'format': 'unknown', 'completeness': 'unknown'}

    def search_archived_video(self, video_info: VideoInfo) -> List[Dict]:
        """Search for archived versions of a video using findyoutubevideo.thetechrobo.ca API"""
        logger.info(f"Searching for archived version of: {video_info.title}")
        
        # Use the API endpoint - GET /api/:version/:videoid
        api_url = f"https://findyoutubevideo.thetechrobo.ca/api/v4/{video_info.video_id}"
        
        try:
            # Make API request with includeRaw=true to get more data
            response = self.session.get(api_url, params={'includeRaw': 'true'})
            response.raise_for_status()
            
            api_data = response.json()
            
            # Check if the request was successful
            if api_data.get('status') == 'bad.id':
                logger.warning(f"Invalid video ID: {video_info.video_id}")
                return []
            
            archived_sources = []
            
            # Process the service responses
            for service in api_data.get('keys', []):
                if service.get('archived', False):
                    source_info = {
                        'source': service.get('name', 'Unknown'),
                        'url': service.get('available'),
                        'text': service.get('note', ''),
                        'archived': True,
                        'metaonly': service.get('metaonly', False),
                        'comments': service.get('comments', False),
                        'maybe_paywalled': service.get('maybe_paywalled', False)
                    }
                    
                    # Only add if there's an available URL
                    if source_info['url']:
                        archived_sources.append(source_info)
                        logger.info(f"Found archived source: {source_info['source']} - {source_info['url']}")
                    elif not source_info['metaonly']:
                        # Add metadata-only sources for reference
                        source_info['url'] = None
                        source_info['text'] = f"Metadata only: {source_info['text']}"
                        archived_sources.append(source_info)
            
            logger.info(f"Found {len(archived_sources)} archived sources for {video_info.title}")
            
            # Save the full API response for debugging
            video_info.archived_sources = archived_sources
            video_info.api_response = api_data
            
            return archived_sources
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error searching for archived video {video_info.title}: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {video_info.title}: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching for archived video {video_info.title}: {str(e)}")
            return []

    def download_video(self, video_info: VideoInfo, archived_sources: List[Dict]) -> bool:
        """Download video from archived sources"""
        video_folder = self.download_folder / self.sanitize_filename(video_info.title)
        video_folder.mkdir(exist_ok=True)
        
        # Analyze date format and completeness
        date_info = self.standardize_date_format(video_info.upload_date)
        
        # Save video metadata including API response
        metadata = {
            'video_id': video_info.video_id,
            'title': video_info.title,
            'original_url': video_info.original_url,
            'filmot_url': video_info.filmot_url,
            'upload_date': video_info.upload_date,
            'upload_date_info': date_info,  # Include date format analysis
            'view_count': video_info.view_count,
            'like_count': video_info.like_count,
            'dislike_count': video_info.dislike_count,
            'archived_sources': archived_sources,
            'api_response': getattr(video_info, 'api_response', {}),
            'timestamp': time.time()
        }
        
        metadata_file = video_folder / 'metadata.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        downloaded = False
        
        # Try to download from each available source
        for source in archived_sources:
            if source.get('url'):
                try:
                    source_url = source['url']
                    source_name = source['source']
                    
                    logger.info(f"Attempting to download from {source_name}: {source_url}")
                    
                    if self._download_from_url(source_url, video_folder, video_info.title):
                        logger.info(f"Successfully downloaded from {source_name}")
                        downloaded = True
                        break
                        
                except Exception as e:
                    logger.warning(f"Failed to download from {source['source']}: {str(e)}")
                    continue
            else:
                logger.info(f"Source {source['source']} has no download URL (metadata only)")
        
        if not downloaded:
            logger.warning(f"Could not download video: {video_info.title}")
            
        return downloaded

    def _download_from_url(self, url: str, folder: Path, title: str) -> bool:
        """Download video from a specific URL"""
        try:
            # First try with yt-dlp if available
            if self._has_ytdlp():
                return self._download_with_ytdlp(url, folder, title)
            
            # Fallback to direct download
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            # Determine file extension from content type or URL
            content_type = response.headers.get('content-type', '')
            
            if 'video' in content_type:
                if 'mp4' in content_type:
                    ext = '.mp4'
                elif 'webm' in content_type:
                    ext = '.webm'
                elif 'avi' in content_type:
                    ext = '.avi'
                else:
                    ext = '.video'
            else:
                # Try to get extension from URL
                parsed_url = urlparse(url)
                path = parsed_url.path
                if '.' in path:
                    ext = '.' + path.split('.')[-1]
                else:
                    ext = '.download'
            
            filename = folder / f"{title}{ext}"
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            logger.info(f"Downloaded: {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading from {url}: {str(e)}")
            return False

    def _has_ytdlp(self) -> bool:
        """Check if yt-dlp is available"""
        try:
            subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _download_with_ytdlp(self, url: str, folder: Path, title: str) -> bool:
        """Download using yt-dlp"""
        try:
            cmd = [
                'yt-dlp',
                '--output', str(folder / f"{title}.%(ext)s"),
                '--write-info-json',
                '--write-thumbnail',
                url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"yt-dlp download successful for: {title}")
                return True
            else:
                logger.warning(f"yt-dlp failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error using yt-dlp: {str(e)}")
            return False

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for Windows/cross-platform compatibility"""
        # Handle None or empty strings
        if not filename:
            return "unknown_video"
        
        # Convert to string and strip
        filename = str(filename).strip()
        
        # Skip if too short or just symbols
        if len(filename) < 2 or filename in ['↗', '→', '»', 'next', 'more', 'prev', 'previous']:
            return "unknown_video"
        
        # Remove or replace invalid characters for Windows filenames
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Replace problematic Unicode characters that might cause issues
        replacements = {
            '…': '...',
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '–': '-',
            '—': '-',
            '│': '|',
            '└': '-',
            '├': '-',
            '┤': '-',
            '┐': '-',
            '┘': '-',
            '┌': '-',
        }
        
        for old, new in replacements.items():
            filename = filename.replace(old, new)
        
        # Remove control characters and other problematic chars
        filename = ''.join(char for char in filename if ord(char) >= 32)
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip(' .')
        
        # Limit length (Windows has 255 char limit for full path)
        if len(filename) > 100:
            filename = filename[:100].strip()
        
        # Final check - ensure we have something valid
        if not filename or len(filename) < 2:
            return "unknown_video"
        
        return filename

    def scrape_all_filmot_pages(self, channel_url: str) -> List[VideoInfo]:
        """Scrape ALL pages from Filmot channel and collect video information"""
        logger.info("=== PHASE 1: SCRAPING ALL FILMOT PAGES ===")
        logger.info(f"Starting complete Filmot scrape: {channel_url}")
        
        all_videos = []
        seen_video_ids = set()
        page_num = 1
        
        try:
            current_url = channel_url
            
            while current_url:
                logger.info(f"Scraping page {page_num}: {current_url}")
                
                response = self.session.get(current_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract videos from current page
                page_videos = self._extract_videos_from_soup(soup, channel_url)
                
                # Filter out duplicates and log with metadata
                new_videos = []
                for video in page_videos:
                    if video.video_id not in seen_video_ids:
                        seen_video_ids.add(video.video_id)
                        new_videos.append(video)
                        all_videos.append(video)
                        
                        # Try to enhance metadata if we didn't get it from the listing
                        if not video.upload_date or not video.view_count:
                            video = self.enhance_video_metadata(video)
                        
                        # Log video with metadata when available
                        metadata_str = ""
                        if video.upload_date:
                            date_info = self.standardize_date_format(video.upload_date)
                            metadata_str += f" | Date: {video.upload_date} ({date_info['completeness']})"
                        if video.view_count:
                            metadata_str += f" | Views: {video.view_count}"
                        if video.like_count:
                            metadata_str += f" | Likes: {video.like_count}"
                        if video.dislike_count and video.dislike_count != "n/a":
                            metadata_str += f" | Dislikes: {video.dislike_count}"
                        elif video.dislike_count == "n/a":
                            metadata_str += f" | Dislikes: n/a"
                        
                        logger.info(f"Found: {video.title} ({video.video_id}){metadata_str}")
                
                logger.info(f"Page {page_num}: Found {len(new_videos)} new videos ({len(page_videos)} total on page)")
                
                if not new_videos:
                    logger.info("No new videos found, stopping pagination")
                    break
                
                # Find next page URL
                next_url = self._find_next_page_url(soup, current_url)
                
                if next_url and next_url != current_url:
                    current_url = next_url
                    page_num += 1
                    time.sleep(2)  # Be respectful between pages
                else:
                    logger.info("No more pages found")
                    break
                    
                # Safety limit to prevent infinite loops
                if page_num > 50:
                    logger.warning("Reached maximum page limit (50), stopping")
                    break
            
            logger.info(f"=== FILMOT SCRAPING COMPLETE ===")
            logger.info(f"Total videos found across {page_num} pages: {len(all_videos)}")
            
            # Show metadata statistics
            dates_found = sum(1 for v in all_videos if v.upload_date)
            views_found = sum(1 for v in all_videos if v.view_count)
            likes_found = sum(1 for v in all_videos if v.like_count)
            dislikes_found = sum(1 for v in all_videos if v.dislike_count and v.dislike_count != "n/a")
            
            logger.info(f"Metadata extracted - Dates: {dates_found}/{len(all_videos)}, Views: {views_found}/{len(all_videos)}, Likes: {likes_found}/{len(all_videos)}, Dislikes: {dislikes_found}/{len(all_videos)}")
            
            return all_videos
            
        except Exception as e:
            logger.error(f"Error during complete Filmot scrape: {str(e)}")
            return all_videos  # Return what we have so far

    def _find_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Find the URL for the next page"""
        
        # Look for various pagination patterns
        next_patterns = [
            ('a', {'text': re.compile(r'next|→|»', re.I)}),
            ('a', {'href': re.compile(r'page=\d+|offset=\d+')}),
            ('a', {'class': re.compile(r'next|pagination', re.I)}),
        ]
        
        for tag, attrs in next_patterns:
            if 'text' in attrs:
                links = soup.find_all(tag, string=attrs['text'])
            else:
                links = soup.find_all(tag, attrs)
            
            for link in links:
                href = link.get('href')
                if href:
                    if href.startswith('http'):
                        return href
                    else:
                        return urljoin(current_url, href)
        
        # Look for numbered pagination
        page_links = soup.find_all('a', href=re.compile(r'page=\d+'))
        if page_links:
            # Find the highest page number
            max_page = 0
            current_page = 0
            
            # Try to determine current page
            parsed_current = urlparse(current_url)
            current_params = parse_qs(parsed_current.query)
            if 'page' in current_params:
                try:
                    current_page = int(current_params['page'][0])
                except:
                    current_page = 1
            else:
                current_page = 1
            
            for link in page_links:
                href = link.get('href')
                if href:
                    page_match = re.search(r'page=(\d+)', href)
                    if page_match:
                        page_num = int(page_match.group(1))
                        if page_num > current_page:
                            next_url = urljoin(current_url, href)
                            return next_url
        
        return None

    def save_video_data(self, videos: List[VideoInfo], filename: str = "filmot_videos.json"):
        """Save all scraped video data to a JSON file"""
        logger.info(f"Saving {len(videos)} videos to {filename}")
        
        video_data = []
        for video in videos:
            video_data.append({
                'video_id': video.video_id,
                'title': video.title,
                'original_url': video.original_url,
                'filmot_url': video.filmot_url,
                'upload_date': video.upload_date,
                'view_count': video.view_count,
                'like_count': video.like_count,
                'dislike_count': video.dislike_count,
            })
        
        data_file = self.download_folder / filename
        with open(data_file, 'w', encoding='utf-8') as f:
            json.dump({
                'timestamp': time.time(),
                'total_videos': len(videos),
                'videos': video_data
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Video data saved to: {data_file}")

    def load_video_data(self, filename: str = "filmot_videos.json") -> List[VideoInfo]:
        """Load video data from JSON file"""
        data_file = self.download_folder / filename
        
        if not data_file.exists():
            logger.warning(f"No saved video data found at: {data_file}")
            return []
        
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            videos = []
            for video_data in data.get('videos', []):
                video = VideoInfo(
                    video_id=video_data['video_id'],
                    title=video_data['title'],
                    original_url=video_data['original_url'],
                    filmot_url=video_data['filmot_url'],
                    upload_date=video_data.get('upload_date'),
                    view_count=video_data.get('view_count'),
                    like_count=video_data.get('like_count'),
                    dislike_count=video_data.get('dislike_count', 'n/a')
                )
                videos.append(video)
            
            logger.info(f"Loaded {len(videos)} videos from {filename}")
            return videos
            
        except Exception as e:
            logger.error(f"Error loading video data: {str(e)}")
            return []

    def process_archived_videos(self, videos: List[VideoInfo]):
        """Phase 2: Process all videos through archive API and download"""
        logger.info("=== PHASE 2: ARCHIVE SEARCHING AND DOWNLOADING ===")
        logger.info(f"Processing {len(videos)} videos through archive API")
        
        successful_downloads = 0
        videos_with_archives = 0
        
        for i, video in enumerate(videos, 1):
            # Create metadata string for console output
            metadata_parts = []
            if video.upload_date:
                metadata_parts.append(f"Date: {video.upload_date}")
            if video.view_count:
                metadata_parts.append(f"Views: {video.view_count}")
            if video.like_count:
                metadata_parts.append(f"Likes: {video.like_count}")
            if video.dislike_count:
                metadata_parts.append(f"Dislikes: {video.dislike_count}")
            
            metadata_str = " | " + " | ".join(metadata_parts) if metadata_parts else ""
            logger.info(f"Processing video {i}/{len(videos)}: {video.title}{metadata_str}")
            
            # Search for archived versions
            archived_sources = self.search_archived_video(video)
            
            if archived_sources:
                videos_with_archives += 1
                # Attempt to download
                if self.download_video(video, archived_sources):
                    successful_downloads += 1
            else:
                logger.warning(f"No archived sources found for: {video.title}")
            
            # Be respectful with requests
            time.sleep(3)
        
        logger.info("=== ARCHIVING COMPLETE ===")
        logger.info(f"Videos with archives found: {videos_with_archives}/{len(videos)}")
        logger.info(f"Successfully downloaded: {successful_downloads}/{len(videos)}")

    def run(self, filmot_channel_url: str, resume_from_saved: bool = False):
        """Main execution method with two phases"""
        logger.info("Starting video archiver...")
        
        if resume_from_saved:
            # Try to load from saved data
            videos = self.load_video_data()
            if videos:
                logger.info("Resuming from saved video data")
            else:
                logger.info("No saved data found, starting fresh scrape")
                resume_from_saved = False
        
        if not resume_from_saved:
            # Phase 1: Complete Filmot scraping
            videos = self.scrape_all_filmot_pages(filmot_channel_url)
            
            if not videos:
                logger.error("No videos found on Filmot channel")
                return
            
            # Save the scraped data
            self.save_video_data(videos)
        
        # Phase 2: Archive processing
        self.process_archived_videos(videos)

def main():
    """Main function"""
    # Channel URL from the user's request
    filmot_channel_url = "https://filmot.com/channel/UCB1XBWo7OMmvAsbiwdNpx1Q"
    
    # Create archiver instance with debug mode enabled to help identify metadata issues
    archiver = VideoArchiver(download_folder="saved_videos", debug_mode=True)
    
    # Run the archiver
    archiver.run(filmot_channel_url)

if __name__ == "__main__":
    main()