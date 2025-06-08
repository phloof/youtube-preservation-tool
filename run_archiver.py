#!/usr/bin/env python3
"""
Simple runner script for the Video Archiver
"""

import sys
import os
from video_archiver import VideoArchiver

def main():
    print("🎥 YouTube Channel Video Archiver")
    print("=" * 40)
    
    # Default values
    default_channel_url = "https://filmot.com/channel/UCB1XBWo7OMmvAsbiwdNpx1Q"
    default_download_folder = "saved_videos"
    
    # Get user input or use defaults
    if len(sys.argv) > 1:
        channel_url = sys.argv[1]
    else:
        channel_url = input(f"Enter Filmot channel URL (or press Enter for default):\n{default_channel_url}\n> ").strip()
        if not channel_url:
            channel_url = default_channel_url
    
    if len(sys.argv) > 2:
        download_folder = sys.argv[2]
    else:
        download_folder = input(f"Enter download folder (or press Enter for '{default_download_folder}'):\n> ").strip()
        if not download_folder:
            download_folder = default_download_folder
    
    # Ask about resuming from saved data
    if len(sys.argv) > 3:
        resume = sys.argv[3].lower() in ['true', 'yes', '1', 'resume']
    else:
        resume_input = input("Resume from previously saved video data? (y/n, default=n): ").strip().lower()
        resume = resume_input in ['y', 'yes', 'true', '1']
    
    print(f"\n📁 Channel URL: {channel_url}")
    print(f"📂 Download folder: {download_folder}")
    print(f"🔄 Resume from saved: {'Yes' if resume else 'No'}")
    
    if not resume:
        print("\n📋 PHASE 1: Will scrape ALL Filmot pages and save video data")
        print("📥 PHASE 2: Will then process all videos through archive API")
    else:
        print("\n📥 Will skip scraping and use saved video data")
    
    print("\n🚀 Starting archiver...")
    
    # Create and run archiver
    archiver = VideoArchiver(download_folder=download_folder)
    archiver.run(channel_url, resume_from_saved=resume)
    
    print("\n✅ Archiver finished!")

if __name__ == "__main__":
    main() 