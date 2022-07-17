# coding=utf-8
#!/usr/bin/python

__author__ = "Russell Johnson"
__doc__ = "Command line script designed to be placed in the parent install folder of a release build of FreeCAD for Windows. \
The script attempts to identify and remove debug files within the release build, trimming the overall size of the install directory."


import os

CWD = os.getcwd()


def deleteTargets(files, directories):
    print("\n\nRemoving these targets:")
    # Delete each identified file
    for f in files:
        print(f"   {f}")
        os.remove(f)

    # Delete each identified directory
    for d in directories:
        print(f"   {d}")
        os.rmdir(d)


def identify_debug_files(file_names_list):
    debug_files = []
    candidates = []
    for filename in file_names_list:
        parts = filename.split(".")
        extension = parts.pop()
        name = ".".join(parts)
        if (
            name.endswith("_d")
            or name.endswith("_D")
            or name.endswith("_debug")
            or "mt-gd-" in name
            or extension == "pdb"
        ):
            debug_files.append(name + "." + extension)
        elif name.endswith("d"):
            candidates.append((name[:-1] + "." + extension, name + "." + extension))
    return (debug_files, candidates)


def scan_directory():
    all_remove_files = []
    all_remove_directories = []

    # Cycle through input directory recursively with config.os.walk()
    for dir_path, dir_list, file_names_list in os.walk(CWD):
        # print(f"dir_path: {dir_path}")
        if dir_path.endswith("__pycache__"):
            debug_files = file_names_list
            all_remove_directories.append(dir_path)
        elif "Examples" in dir_path:
            debug_files = file_names_list
            all_remove_directories.append(dir_path)
        else:
            debug_files, candidates = identify_debug_files(file_names_list)
            for reg, dbg in candidates:
                # check if regular *.* file exists in same directory as *d.* version
                if os.path.exists(dir_path + "/" + reg):
                    debug_files.append(dbg)

        if debug_files:
            print(f"dir_path: {dir_path}")
            print(f"   ... {len(debug_files)} files identified")
            for f in debug_files:
                all_remove_files.append(dir_path + "/" + f)
    # Efor

    all_remove_files.sort(reverse=True)
    all_remove_directories.sort(reverse=True)

    print(f"\n{len(all_remove_files)} total files identified")
    print(f"{len(all_remove_directories)} directories identified")

    return (all_remove_files, all_remove_directories)


print("Executing remove_debug_files script ...")

files, directories = scan_directory()
deleteTargets(files, directories)
