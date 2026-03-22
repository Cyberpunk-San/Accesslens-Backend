


import os
import sys
import argparse
import json
import hashlib
from pathlib import Path
import requests
from tqdm import tqdm
import concurrent.futures
from typing import List, Dict, Optional
import time


MODELS = {
    "llava": {
        "name": "LLaVA 1.5 7B",
        "base_url": "https://huggingface.co/liuhaotian/llava-v1.5-7b/resolve/main",
        "files": [
            "pytorch_model.bin",
            "config.json",
            "tokenizer.model",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "preprocessor_config.json"
        ],
        "size_gb": 13.5,
        "required_ram_gb": 16,
        "description": "Vision-language model for analyzing webpage screenshots"
    },
    "mistral": {
        "name": "Mistral 7B",
        "base_url": "https://huggingface.co/mistralai/Mistral-7B-v0.1/resolve/main",
        "files": [
            "pytorch_model-00001-of-00003.bin",
            "pytorch_model-00002-of-00003.bin",
            "pytorch_model-00003-of-00003.bin",
            "config.json",
            "tokenizer.model",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "generation_config.json"
        ],
        "size_gb": 14.0,
        "required_ram_gb": 16,
        "description": "Language model for generating accessibility code fixes"
    }
}

class ModelDownloader:
    def __init__(self, base_path: Path, model_name: str = "all"):
        self.base_path = Path(base_path)
        self.model_name = model_name
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })

    def get_file_size(self, url: str) -> int:

        try:
            response = self.session.head(url, allow_redirects=True, timeout=10)
            return int(response.headers.get('content-length', 0))
        except:
            return 0

    def download_file(self, url: str, dest_path: Path, expected_size: int = None) -> bool:

        try:
            resume_header = {}
            file_mode = 'wb'
            initial_pos = 0

            if dest_path.exists():
                if expected_size and dest_path.stat().st_size == expected_size:
                    print(f"   {dest_path.name} already exists (size matches)")
                    return True
                else:
                    initial_pos = dest_path.stat().st_size
                    print(f"   {dest_path.name} partially exists. Resuming from byte {initial_pos}...")
                    resume_header = {'Range': f'bytes={initial_pos}-'}
                    file_mode = 'ab'

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            response = self.session.get(url, headers=resume_header, stream=True, timeout=30)
            
            # 416 means Range not satisfiable (file is likely completely downloaded but mismatched)
            if response.status_code == 416:
                 print(f"   {dest_path.name} range error. Restarting download...")
                 initial_pos = 0
                 file_mode = 'wb'
                 response = self.session.get(url, stream=True, timeout=30)
                 
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0)) + initial_pos

            with open(dest_path, file_mode) as f:
                with tqdm(
                    total=total_size,
                    initial=initial_pos,
                    unit='B',
                    unit_scale=True,
                    desc=f"  Downloading {dest_path.name}",
                    leave=False
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))


            if total_size > 0 and dest_path.stat().st_size != total_size:
                print(f"   {dest_path.name} size mismatch")
                return False

            print(f"   {dest_path.name} downloaded successfully")
            return True

        except Exception as e:
            print(f"   Failed to download {dest_path.name}: {e}")
            return False

    def download_model(self, model_key: str) -> bool:

        model = MODELS[model_key]
        model_path = self.base_path / model_key

        print(f"\n Downloading {model['name']}")
        print(f"   Description: {model['description']}")
        print(f"   Total size: ~{model['size_gb']}GB")
        print(f"   Destination: {model_path}")
        print()


        try:
            import shutil
            total, used, free = shutil.disk_usage(self.base_path)
            free_gb = free // (2**30)
            required_gb = model['size_gb'] * 1.2

            if free_gb < required_gb:
                print(f" Warning: Only {free_gb}GB free, need ~{required_gb:.1f}GB")
                response = input("Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    return False
        except:
            pass


        files_to_download = []
        for filename in model['files']:
            url = f"{model['base_url']}/{filename}"
            dest = model_path / filename
            files_to_download.append((url, dest, filename))


        success = True
        for url, dest, filename in files_to_download:
            if not self.download_file(url, dest):
                success = False
                break

        if success:

            with open(model_path / ".downloaded", 'w') as f:
                f.write(f"Downloaded at {time.ctime()}")

            print(f"\n {model['name']} downloaded successfully!")
        else:
            print(f"\n Failed to download {model['name']}")

        return success

    def verify_downloads(self, model_key: str) -> bool:

        model = MODELS[model_key]
        model_path = self.base_path / model_key

        if not model_path.exists():
            return False

        missing_files = []
        for filename in model['files']:
            if not (model_path / filename).exists():
                missing_files.append(filename)

        if missing_files:
            print(f"Missing files for {model['name']}:")
            for f in missing_files:
                print(f"  - {f}")
            return False

        return True

    def get_download_summary(self):

        summary = {}
        for model_key in MODELS:
            model_path = self.base_path / model_key
            if self.verify_downloads(model_key):

                total_size = 0
                for f in model_path.glob("*"):
                    if f.is_file():
                        total_size += f.stat().st_size

                summary[model_key] = {
                    "status": "downloaded",
                    "path": str(model_path),
                    "size_gb": total_size / (1024**3)
                }
            else:
                summary[model_key] = {
                    "status": "missing",
                    "path": str(model_path)
                }

        return summary

def main():
    parser = argparse.ArgumentParser(description="Download AI models for AccessLens")
    parser.add_argument(
        "--model",
        choices=["llava", "mistral", "all"],
        default="all",
        help="Model to download (default: all)"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("./models"),
        help="Path to download models to (default: ./models)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing downloads, don't download"
    )
    parser.add_argument(
        "--show-size",
        action="store_true",
        help="Show model sizes and exit"
    )

    args = parser.parse_args()

    if args.show_size:
        print("\n Model Information:")
        print("-" * 50)
        for key, model in MODELS.items():
            print(f"\n{model['name']}:")
            print(f"  Size: ~{model['size_gb']}GB")
            print(f"  RAM Required: {model['required_ram_gb']}GB")
            print(f"  Files: {len(model['files'])}")
        print()
        return 0

    downloader = ModelDownloader(args.path)

    if args.verify_only:
        print("\n Verifying downloaded models...")
        summary = downloader.get_download_summary()

        for model_key, info in summary.items():
            status_icon = "" if info['status'] == 'downloaded' else ""
            size_info = f" ({info['size_gb']:.2f}GB)" if 'size_gb' in info else ""
            print(f"{status_icon} {model_key}: {info['status']}{size_info}")

        return 0


    import psutil
    available_ram = psutil.virtual_memory().available / (1024**3)

    print("\n System Check:")
    print(f"   Available RAM: {available_ram:.1f}GB")

    models_to_download = ["llava", "mistral"] if args.model == "all" else [args.model]

    for model_key in models_to_download:
        required_ram = MODELS[model_key]['required_ram_gb']

        if available_ram < required_ram:
            print(f" Warning: {MODELS[model_key]['name']} requires {required_ram}GB RAM")
            print(f"   You have {available_ram:.1f}GB available")
            response = input("Continue anyway? (y/N): ")
            if response.lower() != 'y':
                continue


    total_size = sum(MODELS[m]['size_gb'] for m in models_to_download)
    print(f"\n Total download size: ~{total_size:.1f}GB")

    response = input("\nProceed with download? (y/N): ")
    if response.lower() != 'y':
        print("Download cancelled")
        return 0


    success_count = 0
    for model_key in models_to_download:
        if downloader.download_model(model_key):
            success_count += 1


    print("\n" + "=" * 50)
    print(" Download Summary:")
    summary = downloader.get_download_summary()
    for model_key, info in summary.items():
        status_icon = "" if info['status'] == 'downloaded' else ""
        size_info = f" ({info['size_gb']:.2f}GB)" if 'size_gb' in info else ""
        print(f"{status_icon} {model_key}: {info['status']}{size_info}")

    print(f"\n Downloaded {success_count}/{len(models_to_download)} models")
    print(f" Models saved to: {args.path.absolute()}")

    return 0 if success_count == len(models_to_download) else 1

if __name__ == "__main__":
    sys.exit(main())