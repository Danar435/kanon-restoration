#!/bin/bash

# Paths and defaults

output_path="./output"
lucksystem_bin="./lucksystem"

# Help message

show_help() {
  echo "Usage: $0 [options] /path/to/game/folder/"
  echo
  echo "Options:"
  echo "  -o, --output DIR      Specify output directory        (default: ./output)"
  echo "  -l, --lucksystem PATH Specify LuckSystem binary path  (default: ./lucksystem)"
  echo "  -h, --help            Show this help message"
  echo
  exit 1
}

# Argument parsing

while [[ $# -gt 0 ]]; do
  case $1 in
    -o|--output)
      output_path="$2"
      shift 2
      ;;
    -l|--lucksystem)
      lucksystem_bin="$2"
      shift 2
      ;;
    -h|--help)
      show_help
      ;;
    -*|--*)
      echo "Unknown option $1"
      show_help
      ;;
    *)
      if [ -z "$input_path" ]; then
        input_path="$1"
      else
        echo "Error: Multiple input paths specified"
      fi
      shift
      ;;
  esac
done

# Basic checks

if [ -z "$input_path" ]; then
  show_help
fi

if [ ! -f "$lucksystem_bin" ]; then
  echo "Error: $lucksystem_bin not found!"
  exit 1
fi

if [ ! -d "$input_path" ]; then
  echo "Error: $input_path is not a directory!"
  exit 1
fi

if [ ! -f "$input_path/Kanon.exe" ]; then
  echo "Error: $input_path/Kanon.exe not found!"
  echo "Make sure that the path leads to the game's root directory."
  exit 1
fi

# Make output directory

mkdir -p "$output_path/files/image"

repack() {
  
  # File prefix and PAK name

  file="$1"
  pak=$(echo "$file" | tr '[:lower:]' '[:upper:]').PAK

  # Basic checks

  if [ ! -f "$input_path/files/image/$pak" ]; then
      echo "Error: $input_path/files/image/$pak not found!"
      exit 1
  fi

  echo "Processing $pak..."

  # Repack the new assets

  "$lucksystem_bin" pak replace -s "$input_path/files/image/$pak" -i "./source/$file-done/" -o "$output_path/files/image/$pak" > /dev/null 2>&1
}

# Repack all PAKs

repack "bgcg"
repack "charcg"
repack "parts"
repack "syscg"
repack "othcg"

# Patch out character overlays in CHARCG.PAK

dd if=/dev/zero of="$output_path/files/CHARCG.PAK" bs=1 seek=$((0x3934)) count=$((0x3D5F - 0x3934)) conv=notrunc > /dev/null 2>&1

# Final message

echo "Patching completed!"
echo "Check the '$output_path' directory for the patched files."
exit 0
