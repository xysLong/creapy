# creapy.io - getting it onto your laptop

You do not need to install Python or anything else. creapy.io is a normal program: download, unzip, double-click.
It is about 400 MB. If anything below does not work, write to Xingyu Long (xingyu.long@univie.ac.at) with a
screenshot: that is useful for us, not a bother.

## Which file?

| Your computer | File |
|---|---|
| Mac with an Apple chip (M1, M2, M3, M4; sold since late 2020: look under the Apple menu → About This Mac, "Chip") | `creapy.io-…-macOS.zip` |
| Mac with an Intel chip (sold until 2020) | `creapy.io-…-macOS-intel.zip` |
| Windows 10 or 11 | `creapy.io-…-Windows.zip` |

Both Mac versions need **macOS 14 (Sonoma) or newer**: Apple menu → About This Mac shows the version. A Mac that
cannot be updated to macOS 14 (most models from 2017 and earlier) cannot run the app; write to us in that case.

The files are attached to the releases at <https://github.com/xysLong/creapy/releases> (or handed to you directly).

## Mac

1. Double-click the zip in your Downloads folder. A `creapy.io` app appears.
2. Drag `creapy.io` into your **Applications** folder (or leave it in Downloads: both work).
3. **The first start is special.** Double-click the app once; macOS refuses ("not opened", "Apple could not
   verify") and offers only *Done* or *Move to Trash*. Click **Done**, open **System Settings → Privacy &
   Security**, scroll down to the line about creapy.io and click **Open Anyway**, then confirm with your
   password. From now on a normal double-click works. (On macOS 14 and older: **right-click** the app → **Open**
   → **Open**.)
4. If macOS says the app *"is damaged and can't be opened"*: it is not damaged, macOS is cautious about programs
   downloaded from the internet that are not registered with Apple. Open the **Terminal** app (press ⌘ + Space,
   type Terminal), paste this line and press Enter, then try step 3 again:

   `xattr -dr com.apple.quarantine ~/Downloads/creapy.io.app`

   (If you moved the app to Applications, use `/Applications/creapy.io.app` instead.)
5. The first start can take a minute or longer: macOS checks every part of the program once, and the icon keeps
   bouncing in the Dock meanwhile. Wait, and do not double-click again. Later starts take a few seconds.

## Windows

1. Right-click the zip → **Extract All…** → **Extract**. A folder `creapy.io` appears.
2. Open the folder and double-click **creapy.io.exe** (the one with the blue icon). You may create a shortcut on the
   desktop (right-click → Send to → Desktop); do not move the .exe out of its folder.
3. **The first start is special:** Windows shows *"Windows protected your PC"*. Click **More info**, then
   **Run anyway**. This happens once.
4. The first start takes 10–20 seconds. Later starts are faster.

## First steps in the app

- **Were you given a bundle** (one `.creapy` file with the recordings, the images and the areas of interest,
  ready to use)? Download it, do not unzip it, click **Open a bundle…** and choose the file. The first open unpacks
  it (a progress bar); afterwards the project appears on the start screen and opens with one click. Everything
  runs offline from then on.
- **Example dataset** (link at the bottom of the start screen) shows every view with invented data.
- For your own recordings: **Import your own data…** → **Tobii Pro Lab Export** and choose the
  `…Metrics_Event-based.tsv` file of your recording. Confirm the column mapping (it is pre-filled). When asked
  for the images, choose the folder with the snapshot photos (subfolders are searched, so the top folder is
  enough).
- **Help → Quick Guide** explains the views; **Help → The Analyses Explained** explains every measure;
  **Help → Supported Data Formats** explains the files. The two-page hand-out is `QUICKSTART.pdf`.
- **File → Save Project** keeps your groups and areas of interest for the next session.
- Everything you compute stays on your laptop. Nothing is uploaded anywhere.

## If it does not start

- Mac: steps 3 and 4 above cover almost every case. If a window flashes and closes, or macOS says the app cannot be
  used with this version of macOS, check that you have macOS 14 or newer and write to us.
- Windows: if an antivirus program quarantines `creapy.io.exe`, restore it and add an exception, and tell us.
- Both: the app needs about 2 GB of free memory for a dataset with several hundred participants, and about 3 GB of disk
  space for the program plus a few unpacked bundles. Close other programs if it feels slow.
