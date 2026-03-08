#!/usr/bin/env python3
import os
import shutil
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

def is_sd_card(volume_path):
    """Check if a volume is an SD card (Removable Media)."""
    try:
        result = subprocess.run(["diskutil", "info", str(volume_path)], capture_output=True, text=True, check=True)
        return "Removable Media:           Removable" in result.stdout
    except subprocess.CalledProcessError:
        return False

# Common extensions to look for
EXTENSIONS = {
    '.jpg', '.jpeg', '.png',  # JPEG/Image
    '.mp4', '.mov', '.avi',    # Video
    '.cr2', '.cr3', '.nef', '.arw', '.dng', '.raf', '.orf'  # RAW formats
}

def get_creation_date(file_path):
    """Get the creation or modification date of a file."""
    stat = os.stat(file_path)
    try:
        # st_birthtime is available on macOS
        timestamp = stat.st_birthtime
    except AttributeError:
        # Fallback to modification time
        timestamp = stat.st_mtime
    
    return datetime.fromtimestamp(timestamp)

def import_photos(source_dir, dest_base_dir="~/local/photos"):
    source_path = Path(source_dir).expanduser()
    dest_base_path = Path(dest_base_dir).expanduser()

    if not source_path.exists() or not source_path.is_dir():
        print(f"Error: Source directory '{source_path}' does not exist.")
        return

    print(f"Scanning '{source_path}' for media files...")
    
    moved_count = 0
    
    # Walk through the source directory
    for root, dirs, files in os.walk(source_path):
        for file in files:
            file_path = Path(root) / file
            
            # Check if it's a media file based on extension (ignore hidden files)
            if file_path.suffix.lower() in EXTENSIONS and not file_path.name.startswith('.'):
                try:
                    # Determine target folder based on date
                    date = get_creation_date(file_path)
                    date_folder = date.strftime("%Y-%m-%d")
                    target_dir = dest_base_path / date_folder
                    
                    # Create target directory if it doesn't exist
                    target_dir.mkdir(parents=True, exist_ok=True)
                    
                    target_file_path = target_dir / file_path.name
                    
                    # Handle filename collisions
                    counter = 1
                    while target_file_path.exists():
                        new_name = f"{file_path.stem}_{counter}{file_path.suffix}"
                        target_file_path = target_dir / new_name
                        counter += 1
                    
                    # Move the file
                    print(f"Moving {file_path.name} -> {target_dir}")
                    shutil.move(str(file_path), str(target_file_path))
                    moved_count += 1
                    
                except Exception as e:
                    print(f"Error moving {file_path.name}: {e}")

    print(f"Done! Successfully moved {moved_count} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Move SD card raw/jpeg/mp4 files to ~/local/photos/[date]")
    parser.add_argument("source", nargs="?", help="Source directory (e.g., /Volumes/SD_CARD)")
    parser.add_argument("--dest", default="~/local/photos", help="Destination base directory (default: ~/local/photos)")
    
    args = parser.parse_args()
    
    if not args.source:
        print("Please provide a source directory.")
        print("Available SD cards:")
        volumes_dir = Path("/Volumes")
        found_sd_card = False
        if volumes_dir.exists():
            for vol in volumes_dir.iterdir():
                if vol.is_dir() and vol.name not in ["Macintosh HD", "Macintosh HD - Data", "Recovery", "VM"]:
                    if is_sd_card(vol):
                        print(f"  - {vol}")
                        found_sd_card = True
        
        if not found_sd_card:
            print("  (No SD cards found)")
            
        print("\nUsage example: ./import_photos.py /Volumes/R8_SDCard")
    else:
        import_photos(args.source, args.dest)
