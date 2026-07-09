from gooey import Gooey, GooeyParser
from pathlib import Path
from zipfile import ZipFile
import os
import requests
import shutil
import subprocess
import sys

VERSION = "1.0.0"
SOURCE_SIZE = 680

# Needed for Gnome to work properly
os.environ['GTK_THEME'] = 'Adwaita:light'

no_term = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0

# Determine image path
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    else:
        return os.path.join(os.path.abspath("."), relative_path)

# Handle arguments in GUI
@Gooey(
        default_size=(750, 550),
        program_name=f'Kanon Restoration Patch v{VERSION}',
        program_description="Restore the original look and feel of 'Kanon' steam ver.",
        show_restart_button=False,
        clear_before_run=True,
        image_dir=resource_path('assets/gooey'),
        progress_regex = r"(?P<progress>\d+)/(?P<total>\d+)",
        progress_expr="progress / total * 100"
        )
def main():
    # Define paths
    source = Path(f"./kanon-restoration-{VERSION}/source")
    source_url = f'https://github.com/Danar435/kanon-restoration/archive/refs/tags/v{VERSION}.zip'
    if os.name == 'nt':
        pakutil = Path(f"./kanon-restoration-{VERSION}/dependencies/pakutil-v0.2.1-a6-windows.exe")
        xdelta3 = Path(f"./kanon-restoration-{VERSION}/dependencies/xdelta3-v3.1.0-windows.exe")
    else:
        pakutil = Path(f"./kanon-restoration-{VERSION}/dependencies/pakutil-v0.2.1-a6-linux")
        xdelta3 = Path(f"./kanon-restoration-{VERSION}/dependencies/xdelta3-v3.1.0-linux")

    # List of paks to repack
    pak_list = [ "bgcg", "charcg", "manual_deck", "manual", 
                "othcg", "parts", "script", "syscg", ]

    # Set up the parser
    parser = GooeyParser()

    # Required arguments
    required = parser.add_argument_group()
    required.add_argument('path', 
                          metavar='Game Path', 
                          help="The folder in which Kanon is installed", 
                          widget='DirChooser')
    
    options = parser.add_argument_group("Optional Settings", gooey_options={'show_border': True})
    options.add_argument( '-t', '--textbox',
                          metavar='Textbox Opacity', 
                          help="How opaque or solid should the textbox be",  
                          widget='Slider',
                          default=6,
                          gooey_options={
                            'min': 0, 
                            'max': 10, 
                            'increment': 1
                          })
    options.add_argument('-op', '--opening', 
                         metavar='Original OP', 
                         help="Use the original, lower-res 4:3 opening", 
                         action="store_true",
                         widget='BlockCheckbox', 
                         default=False,
                         gooey_options={'checkbox_label': ' Enable'})

    args = parser.parse_args()
    input = Path(args.path)
    exe = Path(f"{input}/Kanon.exe")
    exe_backup = Path(f"{input}/Kanon-backup.exe")
    
    # Check if the path is right
    if not exe.exists():
        print("[ERROR] Kanon.exe not found!", flush=True)
        print("Make sure that the game path is correct. It should point" \
        " to the folder 'Kanon'. Default installation path is" \
        " 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Kanon'", flush=True)
        sys.exit(1)

    # Set up progress variables
    progress = 0
    total = len(pak_list) + 1

    # Download the source
    if not source.exists():
        print("Downloading the assets, this may take a few minutes...", flush=True)
        check_internet()
        with requests.get(source_url, stream=True) as r:
            r.raise_for_status()

            # GitHub doesn't provide `content-length`, must be set manually
            total_size = SOURCE_SIZE
            block_size = 8192
            downloaded = 0
            update = 0

            with open("source.zip", 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)/1024/1024
                        if downloaded >= update:
                            print(f"Downloading the assets: {int(downloaded)}/{total_size} MB", flush=True) 
                            update += 8

        # Extract via zipfile
        print("Extracting the assets...", flush=True)
        with ZipFile("source.zip", 'r') as zObject:
            zObject.extractall(".")
        os.remove("source.zip")
    else:
        print("The assets are already downloaded!", flush=True)

    # Make dependencies executable on linux
    if os.name != 'nt':
        os.chmod(pakutil, 0o755)
        os.chmod(xdelta3, 0o755)

    # Patch the exe
    print("Patching the executable...", flush=True)
    
    if not exe_backup.exists():
        shutil.copy(exe, exe_backup)

    # Hide console window on Windows
    exe_patch = subprocess.run([
                    os.path.join('.', xdelta3), "-d", "-f", "-s", 
                    exe_backup,
                    source / "auxiliary-files" / "Kanon.xdelta", 
                    exe
                    ], creationflags=no_term)
    
    if exe_patch.returncode != 0:
        print("[ERROR] Failed to patch the executable!", flush=True)
        print("Make sure that you are using a legitimate copy of Kanon. Any recent updates may break " \
        "the patch. If you have used this patch before and have deleted 'Kanon-backup.exe', " \
        "then please verify game files within Steam and run the patch again.", flush=True)
        sys.exit(1)

    # Patch the movies
    print("Copying the movies...", flush=True)
    if args.opening:
        shutil.copytree(source / "auxiliary-files" / "movie-og", input / "files" / "movie", dirs_exist_ok=True)
        if Path(input / "files" / "movie" / "Kanon_OP_zc.webm").exists():
            os.remove(input / "files" / "movie" / "Kanon_OP_zc.webm")
    else:
        shutil.copytree(source / "auxiliary-files" / "movie", input / "files" / "movie", dirs_exist_ok=True)

    # Run the main repack script
    print("Processing main assets...", flush=True)
    for i in pak_list:
        progress += 1
        repack(pakutil, source, input, i, progress, total)

    # Set textbox opacity
    print("Processing textbox opacity...", flush=True)
    progress += 1
    repack(pakutil, source / "textbox-files" / args.textbox , input, "parts", progress, total)

    # Remove overlays in characters pak
    print("Fixing CHARCG.PAK...", flush=True)
    with open(input / "files" / "image" / "CHARCG.PAK", "r+b") as file:
        file.seek(0x3934)
        file.write(b"\x00" * (0x3C5F - 0x3934))

    # Finish
    print("[SUCCESS] Patching completed!", flush=True)

def check_internet():
    try:
        response = requests.get('https://www.google.com/', timeout=5)
        return
    except (requests.ConnectionError, requests.Timeout):
        print("[ERROR] Failed to connect to internet!", flush=True)
        print("If you want to use the installer offline, then download the source code separately " \
        "and extract it in the same folder as this patch. It should contain a folder named " \
        "'kanon-restoration-{VERSION}'.", flush=True)
        sys.exit(1)

def repack(pakutil, source, input, file, progress, total):
    # Define paths
    pak = f"{file.upper()}.PAK"
    pak_input = Path(f"{source}/{file}-done/")
    pak_output = Path(f"{input}/files/image/{pak}-temp")
    pak_source = Path(f"{input}/files/image/{pak}")
    if file == "script":
        pak_output = Path(f"{input}/files/{pak}-temp")
        pak_source = Path(f"{input}/files/{pak}")

    # Error catching
    if not pak_source.exists():
        print(f"[ERROR] {pak} not found!", flush=True)
        print("Please verify game files within Steam and run the patch again.", flush=True)
        sys.exit(1)

    # Run pakutil and replace original file
    print(f"Repacking file {progress}/{total}: {pak}...", flush=True)
    subprocess.run([
        os.path.join('.', pakutil),
        pak_source,
        'replace', '-b',
        pak_input,
        pak_output
        ], creationflags=no_term)
    shutil.move(pak_output, pak_source)

if __name__ == '__main__':
    main()
