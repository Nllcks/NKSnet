# NKSnet

A modern Windows desktop application for **network speed testing** and **ad blocker testing**, built with Python and PySide6.

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

- Python 3.10+
- Windows (tested on Windows 10/11)

## Installation

```powershell
pip install -r requirements.txt
```

## Usage

```powershell
python run.py
```

## Build Executable

```powershell
pip install pyinstaller
python -m PyInstaller --onefile --windowed --name SpeedTest --hidden-import speedtest run.py
```

The executable will be at `dist/SpeedTest.exe`.

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
