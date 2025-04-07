import os
import sys
import argparse
from pathlib import Path
import datetime
import fnmatch
import re


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Export codebase to a single text file")
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        default=os.getcwd(),
        help="Root directory of the codebase (default: current directory)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=f'codebase_export_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.txt',
        help="Output file path (default: codebase_export_<timestamp>.txt)",
    )
    parser.add_argument(
        "-e",
        "--extensions",
        type=str,
        default=".py,.js,.java,.cpp,.h,.html,.css,.md,.txt,.json,.yml,.ts,.ico,.idx,.keep,.pack,.rev,.sample",
        help="Comma-separated list of file extensions to include (default: common code files)",
    )
    parser.add_argument(
        "-x",
        "--exclude",
        type=str,
        default="node_modules,venv,.git,__pycache__,*.pyc,*.pyo,*.pyd,*.so,*.dll,*.exe",
        help="Comma-separated list of directories and file patterns to exclude",
    )
    parser.add_argument(
        "--max-size",
        type=int,
        default=1024 * 1024,
        help="Maximum file size to include in bytes (default: 1MB)",
    )
    parser.add_argument(
        "--include-line-numbers", action="store_true", help="Include line numbers in the output"
    )
    parser.add_argument(
        "--toc", action="store_true", help="Generate a table of contents at the beginning"
    )
    parser.add_argument(
        "--header",
        type=str,
        default="Codebase Export - {timestamp}",
        help="Header text for the export file. Use {timestamp} for current timestamp.",
    )
    return parser.parse_args()


def should_include_file(file_path, args):
    """Determine if a file should be included in the export."""
    # Check extension
    extensions = args.extensions.split(",")
    if not any(file_path.name.endswith(ext) for ext in extensions):
        return False
    # Check excluded patterns
    exclude_patterns = args.exclude.split(",")
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(file_path.name, pattern):
            return False
    # Check if file is in excluded directory
    for pattern in exclude_patterns:
        if pattern in str(file_path):
            return False
    # Check file size
    if file_path.stat().st_size > args.max_size:
        print(f"Skipping large file: {file_path} ({file_path.stat().st_size} bytes)")
        return False
    return True


def get_file_language(file_path):
    """Determine the programming language based on file extension."""
    extension = file_path.suffix.lower()
    language_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".go": "go",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".hs": "haskell",
        ".rs": "rust",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".sass": "scss",
        ".json": "json",
        ".xml": "xml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sh": "bash",
        ".bat": "batch",
        ".ps1": "powershell",
        ".sql": "sql",
        ".r": "r",
        ".ico": "binary",
        ".idx": "binary",
        ".keep": "text",
        ".pack": "binary",
        ".rev": "text",
        ".sample": "text",
        ".txt": "text",
    }
    return language_map.get(extension, "text")


def scan_directory(root_dir, files_list, args):
    """Recursively scan directory and collect files to include."""
    root_path = Path(root_dir)
    exclude_dirs = [item for item in args.exclude.split(",") if not item.startswith("*")]
    for path in root_path.rglob("*"):
        if any(
            exclude_dir in str(path.relative_to(root_path))
            for exclude_dir in exclude_dirs
            if exclude_dir
        ):
            continue
        if path.is_file() and should_include_file(path, args):
            files_list.append(path)


def create_separator(length=80):
    """Create a separator line."""
    return "=" * length


def format_file_header(file_path, root_dir):
    """Format header for a file."""
    rel_path = os.path.relpath(file_path, root_dir)
    header = create_separator()
    header += f"\nFILE: {rel_path}\n"
    header += f"LANGUAGE: {get_file_language(file_path)}\n"
    header += f"SIZE: {file_path.stat().st_size} bytes\n"
    header += create_separator()
    return header


def generate_toc(files_list, root_dir):
    """Generate table of contents."""
    toc = "TABLE OF CONTENTS\n"
    toc += create_separator() + "\n"
    for i, file_path in enumerate(files_list, 1):
        rel_path = os.path.relpath(file_path, root_dir)
        toc += f"{i}. {rel_path}\n"
    toc += create_separator() + "\n\n"
    return toc


def export_codebase(args):
    """Export codebase files to a single text file."""
    root_dir = os.path.abspath(args.directory)
    output_file = args.output
    files_list = []
    print(f"Scanning directory: {root_dir}")
    scan_directory(root_dir, files_list, args)
    # Sort files alphabetically
    files_list.sort()
    print(f"Found {len(files_list)} files to export")
    with open(output_file, "w", encoding="utf-8") as f:
        # Write header
        header = args.header.replace(
            "{timestamp}", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        f.write(header + "\n\n")
        # Write table of contents if requested
        if args.toc:
            f.write(generate_toc(files_list, root_dir))
        # Process each file
        for file_path in files_list:
            try:
                # Write file header
                f.write(format_file_header(file_path, root_dir) + "\n\n")
                # Read and write file content with optional line numbers
                with open(file_path, "r", encoding="utf-8", errors="replace") as source_file:
                    if args.include_line_numbers:
                        for i, line in enumerate(source_file, 1):
                            f.write(f"{i:4d} | {line}")
                    else:
                        f.write(source_file.read())
                # Add newlines for spacing
                f.write("\n\n")
            except Exception as e:
                f.write(f"ERROR: Could not read file {file_path}: {str(e)}\n\n")
    print(f"Export completed successfully to: {output_file}")
    print(f"Total size: {os.path.getsize(output_file)} bytes")


def main():
    """Main entry point."""
    args = parse_arguments()
    export_codebase(args)


if __name__ == "__main__":
    main()
