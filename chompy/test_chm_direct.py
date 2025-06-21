#!/usr/bin/env python3
"""
Test CHM parsing directly to verify it works
"""

import sys
sys.path.insert(0, '.')

from pychmlib.chm import _CHMFile
from hhc import parse as parse_hhc

# Test wrapper class similar to what's used in Pyodide
class CHMFileWrapper:
    """Wrapper to make CHM parsing work with in-memory data"""
    def __init__(self, file_data):
        self.data = bytes(file_data)
        self.pos = 0
        self.length = len(self.data)
    
    def read(self, size=-1):
        if size == -1:
            result = self.data[self.pos:]
            self.pos = self.length
        else:
            result = self.data[self.pos:self.pos + size]
            self.pos += len(result)
        return result
    
    def seek(self, pos):
        self.pos = pos
    
    def close(self):
        pass

class CHMFile(_CHMFile):
    """Modified CHM file class that works with in-memory data"""
    def __init__(self, file_data):
        self.filename = '<memory>'
        self.file = CHMFileWrapper(file_data)
        try:
            self._parse_chm()
        except Exception as e:
            self.file.close()
            raise Exception(f"CHM parsing failed: {e}") from e
    
    def get_hhc_content(self):
        """Get HHC content as string"""
        hhc_file = self.get_hhc()
        if hhc_file:
            content = self.retrieve_object(hhc_file)
            if isinstance(content, bytes):
                return content.decode(self.encoding, errors='ignore')
            return content
        return None
    
    def get_file_content(self, filename):
        """Get file content by filename"""
        unit_info = self.resolve_object(filename)
        if unit_info:
            return self.retrieve_object(unit_info)
        return None
    
    def list_files(self):
        """List all files in the CHM"""
        return [ui.name for ui in self.all_files()]

if __name__ == '__main__':
    # Test with actual CHM file
    chm_path = 'pychmlib/tests/chm_files/CHM-example.chm'
    
    print(f"Testing CHM file: {chm_path}")
    
    # Read file data into memory
    with open(chm_path, 'rb') as f:
        file_data = f.read()
    
    print(f"File size: {len(file_data)} bytes")
    print(f"Header: {file_data[:4]}")
    
    try:
        # Test our wrapper
        chm_file = CHMFile(file_data)
        print("✅ CHM file loaded successfully with wrapper")
        
        # Test getting files list
        files = chm_file.list_files()
        print(f"✅ Found {len(files)} files")
        
        # Test getting HHC content
        hhc_content = chm_file.get_hhc_content()
        if hhc_content:
            print("✅ HHC content extracted")
            print(f"HHC content length: {len(hhc_content)}")
            
            # Test parsing HHC
            toc = parse_hhc(hhc_content)
            if toc and hasattr(toc, 'children'):
                print(f"✅ TOC parsed, {len(toc.children)} items")
            else:
                print("❌ TOC parsing failed")
        else:
            print("❌ No HHC content found")
            
        chm_file.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()