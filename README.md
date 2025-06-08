# youtube-preservation-tool

This Python script helps you save videos from lost YouTube channels using a two-phase approach:

**Phase 1:** Scrapes ALL video information from [Filmot.com](https://filmot.com) channel pages  
**Phase 2:** Searches for archived versions on [findyoutubevideo.thetechrobo.ca](https://findyoutubevideo.thetechrobo.ca/) (using API) and downloads them

## Features

- 🔍 **Multi-source search**: Searches across 13+ archive sources including Wayback Machine, Archive.org, GhostArchive, and more
- 📥 **Smart downloading**: Uses yt-dlp when available, falls back to direct downloads
- 📁 **Organized storage**: Creates folders for each video with metadata
- 🔄 **Complete pagination**: Automatically scrapes ALL Filmot pages (up to 50 pages)
- 💾 **Data persistence**: Saves scraped data and supports resume functionality
- 📊 **Two-phase processing**: Separates data collection from archive processing
- 📝 **Detailed logging**: Comprehensive progress tracking and statistics
- 🛡️ **Respectful scraping**: Includes delays and proper headers

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Optional - Install yt-dlp for better video downloading:**
   ```bash
   pip install yt-dlp
   ```

## How It Works

### 📋 Phase 1: Complete Filmot Scraping
1. Scrapes the first page of the Filmot channel
2. Automatically finds and follows pagination links
3. Extracts video IDs and titles from ALL pages
4. Saves complete video data to `filmot_videos.json`
5. Provides detailed progress: "Page X: Found Y new videos"

### 📥 Phase 2: Archive Processing
1. Loads video data (from file or Phase 1)
2. For each video, queries the findyoutubevideo.thetechrobo.ca API
3. Searches across 13+ archive sources simultaneously
4. Downloads videos from available archive sources
5. Saves metadata and provides success statistics

## Usage

### Method 1: Interactive Mode (Recommended)
```bash
python run_archiver.py
```
The script will prompt you for:
- Filmot channel URL (defaults to the channel you specified)
- Download folder name (defaults to "saved_videos")
- Whether to resume from saved data (if available)

### Method 2: Command Line Arguments
```bash
# Fresh complete run
python run_archiver.py "https://filmot.com/channel/UCB1XBWo7OMmvAsbiwdNpx1Q" "my_videos" no

# Resume from saved data (skip Phase 1)
python run_archiver.py "" "" yes
```

### Method 3: Direct Script Execution
```bash
python video_archiver.py
```
This will use the default channel URL and always do a fresh run.

## Output Structure

The script creates the following folder structure:

```
saved_videos/
├── filmot_videos.json          # Complete scraped video data from Phase 1
├── Video_Title_1/
│   ├── video_file.mp4
│   ├── metadata.json           # Includes API response and archive sources
│   └── thumbnail.jpg (if available)
├── Video_Title_2/
│   ├── video_file.webm
│   └── metadata.json
└── video_archiver.log          # Detailed progress and statistics
```

### Key Files:
- **`filmot_videos.json`**: Contains all video data scraped from Filmot (used for resume functionality)
- **`metadata.json`**: Per-video metadata including API responses and archive source details
- **`video_archiver.log`**: Complete log with phase progress and success statistics

## Archive Sources

The script searches the following sources via [findyoutubevideo.thetechrobo.ca](https://findyoutubevideo.thetechrobo.ca/):

- **Wayback Machine** - Internet Archive's web snapshots
- **Archive.org Details** - Video files hosted on Archive.org
- **Archive.org CDX** - Thumbnail and metadata archives
- **GhostArchive** - Video archiving service
- **Distributed YouTube Archive** - Community-maintained archives
- **Hobune.stream** - Video archive platform
- **Filmot** - Subtitle and metadata search
- **RemovedEDM** - Music video archives
- **Odysee** - Blockchain-based video platform
- **altCensored** - Alternative platform archives
- **PreserveTube** - Video preservation service
- **Nyane.online** - Archive search service

## Advanced Usage

### Resume Functionality
If Phase 1 completes but Phase 2 fails, you can resume without re-scraping:
```bash
# Resume from saved data
python run_archiver.py "" "" yes
```

### Progress Tracking
The script provides detailed progress information:
```
=== PHASE 1: SCRAPING ALL FILMOT PAGES ===
Page 1: Found 25 new videos (25 total on page)
Page 2: Found 20 new videos (25 total on page)
...
=== FILMOT SCRAPING COMPLETE ===
Total videos found across 5 pages: 120

=== PHASE 2: ARCHIVE SEARCHING AND DOWNLOADING ===
Processing video 1/120: Video Title Here
Found archived source: Archive.org - http://archive.org/...
...
=== ARCHIVING COMPLETE ===
Videos with archives found: 45/120
Successfully downloaded: 32/120
```

## Configuration

You can modify the following in `video_archiver.py`:

- **Download folder**: Change `download_folder` parameter
- **Request delays**: Modify `time.sleep()` values to be more/less aggressive
- **Page limit**: Change the 50-page safety limit in `scrape_all_filmot_pages()`
- **File naming**: Customize the `sanitize_filename()` method

## Troubleshooting

### Common Issues

1. **No videos found in Phase 1**: 
   - Check that the Filmot URL is correct
   - Ensure the channel page loads in your browser
   - Check `video_archiver.log` for detailed error messages

2. **Phase 1 interruption**:
   - The script saves progress to `filmot_videos.json`
   - You can resume with the resume option

3. **Download failures in Phase 2**:
   - Install yt-dlp for better download support
   - Check your internet connection
   - Some archived videos may have broken links
   - Metadata is still saved even if download fails

4. **Rate limiting**:
   - Increase delay times in the script
   - Run during off-peak hours
   - The two-phase approach helps by separating concerns

### Logs

Check `video_archiver.log` for detailed information about:
- Phase 1: Page-by-page scraping progress
- Phase 2: Archive search results for each video
- Download attempts and failures
- Complete success/failure statistics
- Error messages and debugging information

## Legal Notice

This tool is for educational and preservation purposes. Please respect:
- Website terms of service
- Copyright laws in your jurisdiction
- Rate limits and server resources

## Credits

- Uses [Filmot.com](https://filmot.com) for video discovery
- Uses [findyoutubevideo.thetechrobo.ca](https://findyoutubevideo.thetechrobo.ca/) for archive searching
- Built with Python, requests, BeautifulSoup, and yt-dlp 
