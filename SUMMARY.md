# AI Watcher - C++ OOP Debugger & Snippet Paster

## Overview
AI-powered tool for Embarcadero Dev-C++ that provides instant C++ OOP code snippets and debugging. Runs entirely offline with no API dependency.

## Features

### 1. Smart Snippets (@commands)
Type `@command + Space` to insert code. Snippets adapt to YOUR class names and variables.

| Command | Description | Adapts to |
|---------|-------------|-----------|
| `@full` | Complete working code (BasicSkill + SpecialSkill) | Fixed template |
| `@cls` | Class header with protected/public sections | Your class name, member variables |
| `@ctor` | Constructor with throw validation | Your class name, member variables, throw message |
| `@virt` | Virtual display function | Your display function name |
| `@ope` | Operator+ overloading | Your class name, member variables |
| `@stream` | Operator<< overloading | Your class name, display function |
| `@}` | Close class with semicolon | - |
| `@sub` | Subclass header | Your derived class name |
| `@subctor` | Sub constructor calling base | Both class names |
| `@ovr` | Override display function | Your display function name |
| `@subope` | Sub operator+ | Both class names, member variables |
| `@substream` | Sub operator<< | Both class names, display function |
| `@try` | Try-catch block with testing | Your class names, display function |
| `@main` | Complete main function | Your class names, display function, operators |

### 2. Smart Detection
When you call a snippet, the software:
1. Clears the clipboard (removes old data)
2. Presses Ctrl+A (selects all your code)
3. Presses Ctrl+C (copies to clipboard)
4. Presses Ctrl+Z (undoes selection, preserving your code)
5. Reads the clipboard
6. Detects: class names, member variables, data types, function names
7. Generates snippet using YOUR names
8. Pastes via Ctrl+V (avoids auto-indent issues)

**Supported data types:** `int`, `float`, `double`, `string`, `char`, `bool`

### 3. Debugger (F1-F3)
| Key | Action |
|-----|--------|
| F1 | Analyze highlighted code for errors |
| F2 | Apply fix to current error |
| F3 | Jump to next error |

**Detects:**
- Missing semicolons
- Private inheritance (suggests public)
- Unclosed parentheses
- Missing `return out` in operator<<
- `operator==` not const
- `operator<<` not friend
- Missing semicolon after class
- Assignment in conditions (= instead of ==)
- Division by zero
- Float comparison with ==
- Array bounds errors
- throw without try
- cin without fail check
- Missing return statements
- Wrong function names (e.g., mmain instead of main)

### 4. Stealth GUI
- **20% opacity** — semi-transparent sidebar
- **Hover to show** — hover left edge for 3 seconds
- **Auto-hide** — moves away, window disappears instantly
- **No taskbar** — runs in background
- **System tray** — green icon for control

| Key | Action |
|-----|--------|
| Ctrl+~ | Toggle window visibility |
| Hover left edge 3s | Show window |
| Move away | Auto-hide |

### 5. Clipboard Handling
The software handles Dev-C++ clipboard errors with a multi-step process:

```
Step 1: Clear clipboard (removes stale data from other apps)
Step 2: Ctrl+A (select all code in Dev-C++)
Step 3: Ctrl+C (copy selected code)
Step 4: Ctrl+Z (undo selection, code stays intact)
Step 5: Read clipboard content
Step 6: Process the code
```

**For snippet insertion:**
```
Step 1: Clear clipboard (Tkinter)
Step 2: Append snippet code to clipboard
Step 3: Ctrl+V (paste into Dev-C++)
```

**Why this works:**
- Dev-C++ uses RichEdit control for code editing
- Ctrl+C only copies if text is selected
- Ctrl+A selects all, then Ctrl+C copies it
- Ctrl+Z undoes the selection (code stays where it was)
- Ctrl+V pastes without triggering auto-indent issues

### 6. Keyboard Hook System
- Monitors all keypresses globally
- Detects `@command` patterns in buffer
- Handles special characters (Shift+keys)
- Ignores keys during snippet insertion
- 2-second buffer timeout (clears stale commands)

### 7. Auto-Start on Boot
- Startup folder shortcut: `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ai_watcher.bat`
- Runs `pythonw.exe` (no console window)
- To disable: delete the startup batch file

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
| `ai_watcher.py` | Main script (all logic) |
| `snippets.json` | Boilerplate templates (19 commands) |
| `config.json` | Configuration settings |
| `requirements.txt` | Python dependencies |
| `start_ai_watcher.bat` | Windows launcher |
| `SUMMARY.md` | This documentation |

## Quick Start

1. Open Embarcadero Dev-C++
2. Type your class definition:
```cpp
class Armor {
    int defense;
    void display() { ... }
    Armor operator+(int value) { ... }
```
3. Call `@main [Space]` — generates main function using YOUR classes
4. Press F1 to debug, F2 to fix errors

## Keyboard Shortcuts

| Key | Context | Action |
|-----|---------|--------|
| `@cmd + Space` | Anywhere | Insert snippet |
| F1 | Dev-C++ focused | Debug code |
| F2 | Dev-C++ focused | Apply fix |
| F3 | Dev-C++ focused | Next error |
| Ctrl+~ | Anywhere | Toggle GUI |
| Right Arrow | Suggestion active | Accept suggestion |
| Left Arrow | Suggestion active | Dismiss suggestion |

## Requirements
- Python 3.8+
- Windows 10/11
- Embarcadero Dev-C++ (or Bloodshed/Orwell Dev-C++)
- Python packages: `pystray`, `Pillow`, `keyboard`, `pyperclip`, `watchdog`, `psutil`, `requests`, `tkinter`

## Architecture

```
ai_watcher.py
├── BoilerplateEngine     # Snippet detection and generation
├── CodeAnalyzer          # Error detection and fixing
├── GUIApp                # Tkinter GUI (sidebar)
│   ├── Hover zone        # Invisible zone for show/hide
│   ├── Key buffer        # Captures @commands
│   ├── Snippet inserter  # Clipboard-based paste
│   └── Debugger          # F1-F3 functionality
└── System tray           # pystray icon
```

## License
MIT
