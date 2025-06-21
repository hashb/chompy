#!/usr/bin/env python3
"""
Simple CHM viewer - extracts and displays CHM content without Symbian dependencies
"""

import os
import sys
import argparse
from pychmlib.chm import chm
import hhc


class CHMViewer:
    def __init__(self, filename):
        try:
            self.chm_file = chm(filename)
            self.filename = filename
            self.encoding = self.chm_file.encoding
        except Exception as e:
            raise Exception(f"Cannot open CHM file: {e}")

    def list_contents(self):
        """List all files in the CHM archive"""
        print(f"Contents of {self.filename}:")
        print("-" * 50)

        # Try to get table of contents
        try:
            hhc_file = self.chm_file.get_hhc()
            if hhc_file:
                contents = hhc.parse(hhc_file.get_content())
                self._print_toc(contents)
            else:
                print("No table of contents found")
        except Exception as e:
            print(f"Error reading table of contents: {e}")

    def _print_toc(self, node, indent=0):
        """Recursively print table of contents"""
        for child in node.children:
            name = (
                child.name.decode(self.encoding)
                if hasattr(child.name, "decode")
                else str(child.name)
            )
            prefix = "  " * indent

            if hasattr(child, "local") and child.local:
                print(f"{prefix}- {name} ({child.local})")
            else:
                print(f"{prefix}- {name}")

            if hasattr(child, "children") and child.children:
                self._print_toc(child, indent + 1)

    def extract_file(self, path, output_file=None):
        """Extract a specific file from the CHM archive"""
        try:
            if not path.startswith("/"):
                path = "/" + path

            ui = self.chm_file.resolve_object(path)
            if ui:
                content = ui.get_content()

                if output_file:
                    with open(output_file, "wb") as f:
                        if isinstance(content, str):
                            f.write(content.encode("utf-8"))
                        else:
                            f.write(content)
                    print(f"Extracted {path} to {output_file}")
                else:
                    # Print to stdout
                    if isinstance(content, str):
                        print(content)
                    else:
                        sys.stdout.buffer.write(content)
            else:
                print(f"File not found: {path}")
        except Exception as e:
            print(f"Error extracting file: {e}")

    def extract_all(self, output_dir):
        """Extract all files from CHM archive"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        print(f"Extracting all files to {output_dir}...")
        # This is a simplified version - a full implementation would
        # need to enumerate all files in the CHM archive
        print("Full extraction not implemented yet")

    def close(self):
        """Close the CHM file"""
        if hasattr(self, "chm_file"):
            self.chm_file.close()


def main():
    parser = argparse.ArgumentParser(description="CHM file viewer and extractor")
    parser.add_argument("chm_file", help="Path to CHM file")
    parser.add_argument(
        "--list", "-l", action="store_true", help="List table of contents"
    )
    parser.add_argument(
        "--extract", "-e", help="Extract specific file (path within CHM)"
    )
    parser.add_argument("--output", "-o", help="Output file for extraction")
    parser.add_argument("--extract-all", help="Extract all files to directory")

    args = parser.parse_args()

    if not os.path.exists(args.chm_file):
        print(f"Error: CHM file '{args.chm_file}' not found")
        sys.exit(1)

    try:
        viewer = CHMViewer(args.chm_file)

        if args.list:
            viewer.list_contents()
        elif args.extract:
            viewer.extract_file(args.extract, args.output)
        elif args.extract_all:
            viewer.extract_all(args.extract_all)
        else:
            print("No action specified. Use --help for options.")

        viewer.close()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
