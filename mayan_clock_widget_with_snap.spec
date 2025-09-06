"mayan_clock_widget_with_snap.spec"
# PyInstaller spec for building a single exe of the Mayan widget.
# Usage: pyinstaller mayan_clock_widget_with_snap.spec
# Replace icon with your own if desired.
# Note: include Qt plugins and data as needed by PyInstaller on your system.
block_cipher = None

a = Analysis(['mayan_clock_widget_with_snap.py'],
             pathex=['.'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='MayanClockWidget',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )

coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=True, name='MayanClockWidget')