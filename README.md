# NKSnet

A modern Windows desktop application for **network speed testing** and **ad blocker testing**, built with Python and PySide6.

## Download

[**⬇️ Download NKSnet.exe**](https://github.com/Nllcks/NKSnet/releases/download/v1.0.0/NKSnet.exe) — Just download and run! No installation required.

## Features

### Network Speed Test
- Measures **Download**, **Upload**, **Ping**, and **Jitter**
- Animated circular gauge with real-time progress
- Automatic ISP and location detection via IP

### Ad Blocker Test
- Tests ad-blocking effectiveness in real time
- Checks hundreds of known ad/tracker domains via DNS
- Displays percentage of blocked ads

### Interface
- Dark theme with animated particle background
- Modern circular buttons with hover glow effects
- Slide-out settings panel
- Built with PySide6 (Qt for Python)

## Requirements

- Windows 10/11
- No Python required for the executable version

## Run from Source

```powershell
pip install -r requirements.txt
python run.py
```

## Build Executable

```powershell
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name NKSnet --hidden-import speedtest run.py
```

The executable will be at `dist/NKSnet.exe`.

## Project Structure

```
├── run.py          # Entry point
├── app.py          # GUI (MainWindow, CircularButton, dialogs)
├── worker.py       # Background workers (speed test, adblock test)
├── utils.py        # ISP detection, history, settings
├── requirements.txt
└── README.md
```

## Dependencies

- **PySide6** — Qt framework for Python GUI
- **speedtest-cli** — Internet speed measurement
- **requests** — HTTP requests for ISP detection
- **pyinstaller** — Build standalone executables

## License

MIT
