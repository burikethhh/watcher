# AI Watcher - C++ OOP Debugger & Snippet Paster

## Overview
AI-powered tool for Embarcadero Dev-C++ that provides instant C++ OOP code snippets and debugging.

## Features

### Smart Snippets (@commands)
| Command | Description |
|---------|-------------|
| `@full` | Complete working code (BasicSkill + SpecialSkill) |
| `@cls` | Class header |
| `@ctor` | Constructor |
| `@virt` | Virtual display function |
| `@ope` | Operator+ overloading |
| `@stream` | Operator<< overloading |
| `@}` | Close class |
| `@sub` | Subclass header |
| `@subctor` | Sub constructor |
| `@ovr` | Override display |
| `@subope` | Sub operator+ |
| `@substream` | Sub operator<< |
| `@try` | Try-catch block |
| `@main` | Main function |

### Smart Detection
- Detects class names from your code
- Detects member variables and data types
- Detects display function names
- All snippets adapt to YOUR class names

### Debugger
| Key | Action |
|-----|--------|
| F1 | Debug highlighted code |
| F2 | Apply fix |
| F3 | Next error |

### GUI Controls
| Key | Action |
|-----|--------|
| Ctrl+~ | Toggle window visibility |
| Hover left edge 3s | Show window |
| Move away | Auto-hide |

## Installation

```bash
# 1. Clone repository
git clone https://github.com/burikethhh/watcher.git

# 2. Install dependencies
pip install -r requirements.txt

# 3. Edit config.json (set API key if needed)

# 4. Run
python ai_watcher.py
# or double-click start_ai_watcher.bat
```

## Files

| File | Description |
|------|-------------|
| `ai_watcher.py` | Main script |
| `snippets.json` | Boilerplate templates |
| `config.json` | Configuration |
| `requirements.txt` | Python dependencies |
| `start_ai_watcher.bat` | Windows launcher |

## Usage

1. Open Embarcadero Dev-C++
2. Type `@command + Space` to insert snippets
3. Example: `@main [Space]` inserts complete main function
4. Press F1 to debug code, F2 to apply fixes

## Requirements
- Python 3.x
- Windows OS
- Embarcadero Dev-C++ (also works with original Bloodshed Dev-C++)
- Python packages: `pystray`, `Pillow`, `keyboard`, `pyperclip`, `watchdog`, `psutil`, `requests`

## License
MIT
