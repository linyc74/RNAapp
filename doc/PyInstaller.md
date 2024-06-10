Install PyInstaller

```PowerShell
pip install PyInstaller
```

Package as a .exe file

```PowerShell
$VERSION = "v0.0.0"
pyinstaller --clean --onefile --icon="icon/logo.ico" --add-data="icon;icon" RNAapp.py
Move-Item -Path "dist\RNAapp.exe" -Destination "RNAapp-win-$VERSION.exe"
rm -r build ; rm -r dist ; rm RNAapp.spec
```

Package as a folder

```PowerShell
$VERSION = "v0.0.0"
pyinstaller --clean --icon="icon/logo.ico" --add-data="icon;icon" RNAapp.py
Move-Item -Path "dist\RNAapp.exe" -Destination "RNAapp.exe"
Compress-Archive -Path "RNAapp" -DestinationPath "RNAapp-win-$VERSION.zip"
rm -r build ; rm -r dist ; rm -r RNAapp ; rm RNAapp.spec
```
