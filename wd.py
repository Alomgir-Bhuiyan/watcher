import os
import shutil
import argparse
import time
from colorama import Fore, Style, init
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

init(autoreset=True)

def load_ignore_patterns(base_folder):
    ignore_file = os.path.join(base_folder, ".watchignore")
    if os.path.exists(ignore_file):
        with open(ignore_file, "r") as f:
            return [line.strip() for line in f if line.strip()]
    return []

def is_ignored(path, ignore_patterns, base_folder):
    rel_path = os.path.relpath(path, base_folder).replace("\\", "/")
    if os.path.basename(path) == ".watchignore":
        return True
    for pattern in ignore_patterns:
        pattern = pattern.rstrip("/")
        if rel_path == pattern or rel_path.startswith(pattern + "/"):
            return True
        if os.path.basename(path) == pattern:
            return True
    return False

def sync_file(src, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.isdir(src):
        os.makedirs(dest, exist_ok=True)
    else:
        
        if os.path.exists(dest):
            if os.path.getmtime(src) <= os.path.getmtime(dest):
                return
        shutil.copy2(src, dest)

def initial_sync(base, input_folder, ignore_patterns):
    for root, dirs, files in os.walk(base):
        for d in dirs:
            dir_path = os.path.join(root, d)
            if is_ignored(dir_path, ignore_patterns, base):
                continue
            dest_dir = os.path.join(input_folder, os.path.relpath(dir_path, base))
            os.makedirs(dest_dir, exist_ok=True)
        for f in files:
            file_path = os.path.join(root, f)
            if is_ignored(file_path, ignore_patterns, base):
                continue
            dest_file = os.path.join(input_folder, os.path.relpath(file_path, base))
            sync_file(file_path, dest_file)

class SyncHandler(FileSystemEventHandler):
    def __init__(self, src, dest, ignore_patterns):
        self.src = src
        self.dest = dest                                           self.ignore_patterns = ignore_patterns
        self.file_count = {}
        self.last_modified = {}
                                                               def _log_event(self, action, path):
        self.file_count[path] = self.file_count.get(path, 0) + 1
        count = self.file_count[path]
        color = {"created": Fore.GREEN, "modified": Fore.YELLOW, "deleted": Fore.RED, "moved": Fore.CYAN}.get(action, Fore.WHITE)
        print(f"{color}[{action.upper()}]{Style.RESET_ALL} {path} (changed {count} times)")

    def _should_process(self, path):                               now = time.time()
        last = self.last_modified.get(path, 0)
        if now - last < 2:  
            return False
        self.last_modified[path] = now
        return True

    def on_created(self, event):
        if is_ignored(event.src_path, self.ignore_patterns, self.src):
            return
        if not self._should_process(event.src_path):
            return
        rel_path = os.path.relpath(event.src_path, self.src)
        dest_path = os.path.join(self.dest, rel_path)
        sync_file(event.src_path, dest_path)
        self._log_event("created", rel_path)

    def on_modified(self, event):
        if is_ignored(event.src_path, self.ignore_patterns, self.src):
            return
        if not self._should_process(event.src_path):
            return
        if os.path.isdir(event.src_path):
            return
        rel_path = os.path.relpath(event.src_path, self.src)
        dest_path = os.path.join(self.dest, rel_path)
        sync_file(event.src_path, dest_path)
        self._log_event("modified", rel_path)

    def on_deleted(self, event):
        if is_ignored(event.src_path, self.ignore_patterns, self.src):
            return
        if not self._should_process(event.src_path):
            return
        rel_path = os.path.relpath(event.src_path, self.src)
        dest_path = os.path.join(self.dest, rel_path)              if os.path.isdir(dest_path):
            shutil.rmtree(dest_path, ignore_errors=True)
        elif os.path.exists(dest_path):
            os.remove(dest_path)
        self._log_event("deleted", rel_path)

    def on_moved(self, event):
        if is_ignored(event.src_path, self.ignore_patterns, self.src) or is_ignored(event.dest_path, self.ignore_patterns, self.src):                                                        return
        if not self._should_process(event.src_path):
            return
        rel_src = os.path.relpath(event.src_path, self.src)
        rel_dest = os.path.relpath(event.dest_path, self.src)
        dest_src = os.path.join(self.dest, rel_src)
        dest_dest = os.path.join(self.dest, rel_dest)
        if os.path.exists(dest_src):
            os.makedirs(os.path.dirname(dest_dest), exist_ok=True)
            shutil.move(dest_src, dest_dest)
        else:
            sync_file(event.dest_path, dest_dest)
        self._log_event("moved", f"{rel_src} → {rel_dest}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, help="Input folder")
    parser.add_argument("-o", "--output", required=True, help="Output folder")
    parser.add_argument("-b", "--base", required=True, help="Base folder where .watchignore lives")
    args = parser.parse_args()

    ignore_patterns = load_ignore_patterns(args.base)
    initial_sync(args.base, args.input, ignore_patterns)

    event_handler = SyncHandler(args.input, args.output, ignore_patterns)
    observer = Observer()
    observer.schedule(event_handler, args.input, recursive=True)
    observer.start()

    print(f"{Fore.CYAN}Watching for changes... Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
