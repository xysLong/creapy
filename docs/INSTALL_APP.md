# creapy.io - getting it onto your laptop

You do not need to install Python or anything else. creapy.io is a normal program: download, unzip, double-click.
It is about 400 MB. If anything below does not work, write to Xingyu Long (xingyu.long@univie.ac.at) with a
screenshot: that is useful for us, not a bother.

## Which file?

| Your computer | File |
|---|---|
| Mac from 2020 or later (Apple chip: M1, M2, M3, M4: look under  → About This Mac, "Chip") | `creapy.io-…-macOS.zip` |
| Older Mac (Intel) | `creapy.io-…-macOS-intel.zip` |
| Windows 10 or 11 | `creapy.io-…-Windows.zip` |

The files are attached to the releases at <https://github.com/xysLong/creapy/releases> (or handed to you directly).

## Mac

1. Double-click the zip in your Downloads folder. A `creapy.io` app appears.
2. Drag `creapy.io` into your **Applications** folder (or leave it in Downloads: both work).
3. **The first start is special:** do not double-click. **Right-click** (or Control-click) the app → **Open**.
   macOS says the developer cannot be verified → click **Open** again. From now on a normal double-click works.
4. If macOS says the app *"is damaged and can't be opened"*: it is not damaged, macOS is cautious about programs
   downloaded from the internet that are not registered with Apple. Open the **Terminal** app (press ⌘ + Space,
   type Terminal), paste this line and press Enter, then try step 3 again:

   `xattr -dr com.apple.quarantine ~/Downloads/creapy.io.app`

   (If you moved the app to Applications, use `/Applications/creapy.io.app` instead.)

## Windows

1. Right-click the zip → **Extract All…** → **Extract**. A folder `creapy.io` appears.
2. Open the folder and double-click **creapy.io.exe** (the one with the blue icon). You may create a shortcut on the
   desktop (right-click → Send to → Desktop); do not move the .exe out of its folder.
3. **The first start is special:** Windows shows *"Windows protected your PC"*. Click **More info**, then
   **Run anyway**. This happens once.
4. The first start takes 10–20 seconds (Windows unpacks the program). Later starts are faster.

## First steps in the app

- Click **Open the example dataset** to see every view with invented data.
- For your own recordings: **Import Tobii Pro Lab Export…** and choose the `…Metrics_Event-based.tsv` file of
  your recording. Confirm the column mapping (it is pre-filled). When asked for the images, choose the folder
  with the snapshot photos (subfolders are searched, so the top folder is enough).
- **Help → Quick Guide** explains the views; **Help → The Analyses Explained** explains every measure;
  **Help → Supported Data Formats** explains the files. The two-page hand-out is `QUICKSTART.pdf`.
- **File → Save Project** keeps your groups and areas of interest for the next session.
- Everything you compute stays on your laptop. Nothing is uploaded anywhere.

## If it does not start

- Mac: steps 3 and 4 above cover almost every case. If a window flashes and closes, write to us.
- Windows: if an antivirus program quarantines `creapy.io.exe`, restore it and add an exception, or ask us for the
  alternative download.
- Both: the app needs about 1 GB of free memory. Close other programs if it feels slow with large wall photographs.
