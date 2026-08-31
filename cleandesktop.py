#!/usr/bin/env python3
import argparse
import os
import shutil
import time
from pathlib import Path
from pprint import pprint
from pathlib import Path
import argparse


extension_mapping = {'image': ['png', 'gif', 'jpg', 'jpeg', 'psd', 'pxd', 'heic', 'webp', 'tif', 'tiff'],
                     'ignore': ['DS_Store', 'swp', 'localized', 'exe', 'bak'],
                     'text': ['txt', 'html', 'md'],
                     'data': ['yaml', 'kmz', 'kml', 'yml', 'json', 'ics'],
                     'app': ['app', 'dmg', 'pkg', 'iso'],
                     'sourcecode': ['groovy', 'py', 'cpp', 'pl', 'sh', 'zsh'],
                     'presentation': ['ppt', 'pptx', 'key'],
                     'email': ['eml', 'msg'],
                     'document': ['doc', 'docx', 'pdf', 'pages', 'graffle'],
                     'audio': ['wav', 'mp3'],
                     'video': ['mp4', 'mov', 'vtt', 'm4a'],
                     'bundle': ['zip', 'tar', 'tgz', 'dmg', 'gz'],
                     'spreadsheets': ['csv', 'xlsx', 'xls','tsv', 'numbers'],
                     }

def main(dir, move=True, age=True, doprune=True, verbose=False):
    '''
    :param dir: directory to scan for cleanup
    :param move: move the files to the categoriezed subdirectories
    :param age: move files to aged directories (weeks, months, etc.
    :param doprune: remove empty directories
    :param verbose: output of whats going on to STDOUT
    :return: dictionary with info about the files before cleanup
    '''
    data = scandir(dir)
    if move:
        files_moved = move_to_categorized_folders(data, dir)

        if verbose:
            if len(files_moved) < 1:
                print(f"No files moved in {dir}")
            else:
                move_metrics = {key: 0 for key in extension_mapping.keys()}
                move_metrics['unknown'] = 0
                move_metrics['screenshot'] = 0
                for filename in files_moved.keys():
                    try:
                        cat = data[filename.replace(f"{dir}/", '')]['type']
                        move_metrics[cat] += 1
                    except Exception as e:
                        move_metrics['unknown'] += 1
                        print(f"categorization error in main: {e}")
                    total = sum(move_metrics.values())
                print(f"Moved {total} file{'s'[:total ^ 1]} in {dir}")
                for k, v in move_metrics.items():
                    if v > 0:
                        print(f" {k}{'s'[:v ^ 1]}: {v}")
            print()

    if age:
        aged_files, pruned_dirs = age_archive(dir, doprune=doprune)
        if verbose and len(aged_files) > 0:
            print(f"files in {dir} categorized according to last access")
            for timeperiod, files_moved in aged_files.items():
                if len(files_moved) > 0:
                    print(f"{timeperiod}: {len(files_moved)} file{'s'[:len(files_moved) ^ 1]}")
        if verbose and len(pruned_dirs) > 0:
            for k, v in pruned_dirs.items():
                print(f"{len(v)} empty directorie{'s'[:len(v) ^ 1]} pruned in {k}")
    if doprune:
        files_removed = prune(f"{dir}/archive", ignore_DS_Store=True)
        if verbose and len(files_removed) > 0:
            print(f"Removed {len(files_removed)} folder{'s'[:len(files_removed) ^ 1]}")
            for x, filename in enumerate(files_removed):
                print(f"{x + 1:3}. {filename}")
    return data


def prune(dir, ignore_DS_Store=True):
    '''
    removes empty directories or those containing only .DS_Store (scourge of the Mac)
    :param dir:
    :param ignore_DS_Store:
    :return: list of files removed
    '''
    #
    # note: this does not recurse, it considers only the directory passed
    files = os.listdir(dir)
    removed = []
    # look for empty subdirs
    for d in [f for f in files if os.path.isdir(dir + '/' + f)]:
        filelist = os.listdir(f"{dir}/{d}")
        if len(filelist) == 0 or (ignore_DS_Store and len(filelist) == 1 and filelist[0] == '.DS_Store'):
            shutil.rmtree(f"{dir}/{d}", ignore_errors=True)
            removed.append(f"{dir}/{d}")
    return removed


def scandir(dir, screen_shot=True):
    '''
    scans directory (does not recurse), categorizing and gathering information about that file's usage

    :param dir: directory to scan
    :param screen_shot: separate screenshots from other images
    :return: dictionary of the form 'filename': {'type': <file type (see extension_map,py>,
                                                 'modified': <hours since last modification>,
                                                 'accessed': <hours since last accessed>,
                                                 }
    '''

    files = os.listdir(dir)
    files = [f for f in files if os.path.isfile(dir + '/' + f)]  # Filtering only the files.
    data = {}
    now = int(time.time())  # machine local time
    for file in files:
        statinfo = os.stat(dir + '/' + file)
        data[file] = {'type': None,
                      'created': (now - statinfo.st_birthtime) / 86400.0,  # in fractional hours
                      'modified': (now - statinfo.st_mtime) / 86400.0,  # in fractional hours
                      'accessed': (now - statinfo.st_atime) / 86400.0,  # in fractional hours
                      }
        if screen_shot and (file.startswith('Screen Shot') or file.startswith('Screenshot')):
            data[file]['type'] = "screenshot"
        else:
            for t in extension_mapping.keys():
                for ext in extension_mapping[t]:
                    if file.lower().endswith(f".{ext.lower()}"):
                        data[file]['type'] = t
    return data


def age_dir(data, dirpath, dirname, metric_to_use='accessed', use_parent=False, verbose=False):
    '''
    move files to subdirectories by the last time they were accessed (or modified or created depending on metric_use_passed)

    :param data: dictionary with info about the files
    :param dirpath: direcotry full path
    :param dirname: directory name
    :param metric_to_use: filestat measurement to use (created, modified, accessed
    :param use_parent: create subdirs in the parent directory
    :param verbose: output of whats going on to STDOUT
    :return:
    '''
    aged_files = {}
    for filename, details in data.items():
        details['newdir'] = None
        jkl = details[metric_to_use]
        if details[metric_to_use] >= 360:
            details['newdir'] = 'year+'
        elif details[metric_to_use] >= 180:
            details['newdir'] = '6 months'
        elif details[metric_to_use] >= 60:
            details['newdir'] = '2 months'
        elif details[metric_to_use] >= 30:
            details['newdir'] = '1 month'
        elif details[metric_to_use] >= 14:
            details['newdir'] = '2 weeks'
        elif details[metric_to_use] >= 7:
            details['newdir'] = '1 week'

        if details['newdir'] is not None:
            if details['newdir'] not in aged_files:
                aged_files[details['newdir']] = []
            if use_parent:
                targetpath = f"{dirpath}/../{details['newdir']}"
            else:
                targetpath = f"{dirpath}/{details['newdir']}"
            try:
                Path(targetpath).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"error creating directory {targetpath}: {e}")
            try:
                shutil.move(f"{dirpath}/{filename}", f"{targetpath}/{filename}")
                aged_files[details['newdir']].append(f"{targetpath}/{filename}")
            except Exception as e:
                print(f"error moving {filename} to {targetpath}/{filename}: {e}")
    return aged_files


def age_archive(dir, doprune=False):
    '''
    moves files to subdirectories according to the last time they were accessed (1, 2 weeks; 1, 2, 6 months, 1+ years)

    :param dir: directory to age
    :param doprune: remove empty directories after moving files around
    :return: directionaries with the files moved and directories pruned
    '''
    files = os.listdir(f"{dir}/Archive")
    aged_dirs = {}
    pruned_dirs = {}
    for file in files:
        targetdir = f"{dir}/Archive/{file}"
        if os.path.isdir(targetdir):
            data = scandir(targetdir)
            age_dir(data, targetdir, file)
            for subfile in os.listdir(targetdir):
                targetfile = f"{targetdir}/{subfile}"
                if os.path.isdir(targetfile):
                    data = scandir(targetfile)
                    aged_file = age_dir(data, targetfile, subfile, use_parent=True)
                    for k, v in aged_file.items():
                        if k not in aged_dirs:
                            aged_dirs[k] = []
                        aged_dirs[k] += v
            if doprune:
                pruned_dirs_in_target = prune(targetdir, ignore_DS_Store=True)
                if len(pruned_dirs_in_target) > 0:
                    pruned_dirs[targetdir] = pruned_dirs_in_target
    return aged_dirs, pruned_dirs


def move_to_categorized_folders(data, dir):
    '''

    :param data: dictionary with info about the files
    :param dir: directory fullpath
    :return: dictionary with old and new filepath
    '''
    moved = {}
    for filename, v in data.items():
        if v['type'] == 'ignore':
            continue
        targetdir = f"{dir}/archive/{v['type']}"
        try:
            Path(targetdir).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error creating directory {targetdir}/{filename}, skipping: {e}")
            continue
        try:
            shutil.move(f"{dir}/{filename}", f"{targetdir}/{filename}")
            moved[f"{dir}/{filename}"] = f"{targetdir}/{filename}"
        except Exception as e:
            print(f"Error moving {filename} to {targetdir}/{filename}: {e}")
    return moved


if __name__ == '__main__':
    home = str(Path.home())
    parser = argparse.ArgumentParser( prog='clean desktop',
                            description='organizes files into categories and then by last access time for easier curation and cleanup.',
                            epilog='')
    parser.add_argument('--skip_desktop', action='store_true', help=f'skip cleaning {home}/Desktop')
    parser.add_argument('--skip_downloads', action='store_true', help=f'skip cleaning {home}/Downloads')
    parser.add_argument('--skip_Stellarium', action='store_true', help=f'skip cleaning {home}/Pictures/Stellarium')
    parser.add_argument('--skip_tmp', action='store_true', help=f'skip cleaning /tmp')
    parser.add_argument('--silent', action='store_true', help=f'avoid output to STDOUT')
    parser.add_argument('directory', nargs='?', help=f'fullpath to directory to organize (optional)')
    args = parser.parse_args()

    directories = []

    if not args.skip_downloads:
        directories.append(f"{home}/Desktop")
    if not args.skip_Stellarium:
        directories.append(f"{home}//Pictures/Stellarium")
    if not args.skip_desktop:
        directories.append(f"{home}/Downloads")
    if not args.skip_tmp is not None:
        directories.append('/tmp')
    if args.directory is not None:
        directories.append(args.directory)

    for directory in directories:
        if os.path.isdir(directory):
            main(directory, verbose=not args.silent)
        else:
            raise ValueError(f'directory {directory} does not exist')
