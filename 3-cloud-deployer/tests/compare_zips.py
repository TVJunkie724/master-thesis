"""Compare L1 and L2 ZIP bundles."""
import sys
sys.path.insert(0, '/app/src')
from providers.azure.layers.function_bundler import bundle_l1_functions, bundle_l2_functions
import zipfile
import io

print('='*60)
print('L1 (dispatcher) ZIP')
print('='*60)
l1_bytes = bundle_l1_functions('/app/upload/template')
if l1_bytes:
    zf = zipfile.ZipFile(io.BytesIO(l1_bytes))
    for name in sorted(zf.namelist()):
        info = zf.getinfo(name)
        print(f'  {name} ({info.file_size} bytes)')
    print()
    print('--- main function_app.py ---')
    content = zf.read('function_app.py').decode('utf-8')
    print(content)
    print()
    print('--- dispatcher/function_app.py ---')
    content = zf.read('dispatcher/function_app.py').decode('utf-8')
    print(content[:800])

print()
print('='*60)
print('L2 (persister/event-checker) ZIP - WORKING')
print('='*60)
l2_bytes = bundle_l2_functions('/app/upload/template')
if l2_bytes:
    zf = zipfile.ZipFile(io.BytesIO(l2_bytes))
    for name in sorted(zf.namelist()):
        info = zf.getinfo(name)
        print(f'  {name} ({info.file_size} bytes)')
    print()
    print('--- main function_app.py ---')
    content = zf.read('function_app.py').decode('utf-8')
    print(content)
    print()
    print('--- persister/function_app.py ---')
    content = zf.read('persister/function_app.py').decode('utf-8')
    print(content[:800])
