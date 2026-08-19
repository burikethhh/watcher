import json
import os
import re
import time
import threading
import ctypes
import ctypes.wintypes
import keyboard
import pystray
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import font as tkfont

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SNIPPETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snippets.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def load_snippets():
    with open(SNIPPETS_PATH, "r") as f:
        return json.load(f)

CFG = load_config()
SNIPPETS = load_snippets()

class CodeAnalyzer:
    def detect_errors(self, code):
        errors = []
        lines = code.split("\n")
        in_class = False
        class_name = ""
        class_brace_depth = 0
        current_depth = 0
        in_try = False
        throw_lines = []
        catch_types = []
        func_returns = {}
        inheritance_map = {}

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*"):
                current_depth += stripped.count("{") - stripped.count("}")
                continue

            # Parenthesis check
            open_p = stripped.count("(")
            close_p = stripped.count(")")
            if open_p != close_p:
                if "(" in stripped and ")" not in stripped and "{" not in stripped:
                    if not stripped.endswith(";") and not stripped.startswith("//"):
                        errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                                       "msg": "Unclosed parenthesis",
                                       "fix": stripped + ")"})
                elif ")" in stripped and "(" not in stripped:
                    errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                                   "msg": "Extra closing parenthesis",
                                   "fix": stripped.replace(")", "", 1)})

            # Bracket check
            if stripped.count("[") != stripped.count("]"):
                errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                               "msg": "Mismatched brackets []"})

            # Double semicolon
            if stripped.endswith(";;"):
                errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                               "msg": "Double semicolon",
                               "fix": stripped[:-1]})

            # Wrong operator order
            if "= +" in stripped:
                errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                               "msg": "Wrong operator order (= + should be +=)",
                               "fix": stripped.replace("= +", "+=")})
            if "= -" in stripped and "==" not in stripped:
                errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                               "msg": "Wrong operator order (= - should be -=)",
                               "fix": stripped.replace("= -", "-=")})

            # Missing semicolon after return
            if stripped.startswith("return") and ";" not in stripped and stripped != "return":
                errors.append({"line": i + 1, "type": "main", "severity": "error",
                               "msg": "Missing semicolon after return",
                               "fix": stripped + ";"})

            # Class definition
            class_match = re.match(r'class\s+(\w+)', stripped)
            if class_match:
                class_name = class_match.group(1)
                in_class = True
                class_brace_depth = current_depth + stripped.count("{") - stripped.count("}")
                inh_match = re.search(r':\s*(public|protected|private)\s+(\w+)', stripped)
                if inh_match:
                    inheritance_map[class_name] = {"base": inh_match.group(2), "access": inh_match.group(1)}
                else:
                    inh_match2 = re.search(r':\s*(\w+)', stripped)
                    if inh_match2:
                        inheritance_map[class_name] = {"base": inh_match2.group(1), "access": "private"}
                current_depth += stripped.count("{") - stripped.count("}")
                continue

            # Private inheritance
            if in_class and class_name in inheritance_map:
                inh = inheritance_map[class_name]
                if inh.get("access") == "private" and inh.get("base") and not inh.get("reported"):
                    errors.append({"line": i + 1, "type": "inheritance", "severity": "warning",
                                   "msg": "Private inheritance from " + inh["base"] + " (use public for polymorphism)",
                                   "fix": "class " + class_name + " : public " + inh["base"] + " {"})
                    inh["reported"] = True

            opens = stripped.count("{")
            closes = stripped.count("}")

            # Missing semicolon after class
            if in_class and current_depth == class_brace_depth and opens == 0 and closes > 0:
                if stripped == "}":
                    errors.append({"line": i + 1, "type": "class", "severity": "error",
                                   "msg": "Missing semicolon after class " + class_name,
                                   "fix": "};"})
                in_class = False

            # Try/catch
            if stripped.startswith("try"):
                in_try = True
            if "catch" in stripped:
                catch_match = re.search(r'catch\s*\((\w+(?:\s*\*)?)\s+(\w+)\)', stripped)
                if catch_match:
                    catch_types.append({"line": i + 1, "type": catch_match.group(1)})
                in_try = False

            # Throw
            if "throw" in stripped and "catch" not in stripped:
                throw_match = re.search(r'throw\s+(.+?);', stripped)
                if throw_match:
                    throw_lines.append({"line": i + 1, "value": throw_match.group(1).strip()})

            # Throw/catch mismatch
            if "}" in stripped and not in_try and throw_lines and catch_types:
                last_throw = throw_lines[-1]
                last_catch = catch_types[-1]
                if last_throw["value"].startswith('"') and last_catch["type"] in ("int", "float", "double", "char"):
                    errors.append({"line": last_catch["line"], "type": "error_handling", "severity": "error",
                                   "msg": "Throwing string but catch expects " + last_catch["type"],
                                   "fix": "catch (const char* msg){"})
                    throw_lines.clear()
                    catch_types.clear()

            # Function with missing return
            func_match = re.match(r'(?:int|float|double|char|bool|long|unsigned)\s+(\w+)\s*\(', stripped)
            if func_match and not stripped.startswith(("if", "while", "for", "switch", "catch", "return", "class", "struct")):
                func_returns[func_match.group(1)] = {"line": i + 1, "found_return": False}

            if stripped.startswith("return") and func_returns:
                for fname, finfo in func_returns.items():
                    if finfo and not finfo["found_return"]:
                        finfo["found_return"] = True

            # Operator overloading issues
            if "operator==" in stripped:
                if "const" not in stripped:
                    errors.append({"line": i + 1, "type": "overloading", "severity": "warning",
                                   "msg": "operator== should be const",
                                   "fix": stripped.replace("==(", "== const(")})

            if "operator<<" in stripped and "friend" not in stripped:
                errors.append({"line": i + 1, "type": "overloading", "severity": "error",
                               "msg": "operator<< must be friend",
                               "fix": "friend " + stripped})

            current_depth += opens - closes

        # Check missing returns
        for fname, finfo in func_returns.items():
            if finfo and not finfo["found_return"] and fname != "main":
                errors.append({"line": finfo["line"], "type": "main", "severity": "warning",
                               "msg": "Function " + fname + " may be missing return"})

        # Check main return
        in_main = False
        main_brace = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "main()" in stripped:
                in_main = True
                main_brace = 0
            if in_main:
                main_brace += stripped.count("{") - stripped.count("}")
                if main_brace <= 0 and i > 0:
                    in_main = False
                if stripped.startswith("return") and ";" not in stripped:
                    errors.append({"line": i + 1, "type": "main", "severity": "error",
                                   "msg": "Missing semicolon after return",
                                   "fix": stripped + ";"})

        # cin without fail check
        code_text = "\n".join(lines)
        if "cin >>" in code_text and "cin.fail()" not in code_text:
            errors.append({"line": code_text.count("\n") + 1, "type": "main", "severity": "warning",
                           "msg": "cin >> without fail check"})

        # Throw without try
        in_try_block = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("try"):
                in_try_block = True
            if stripped.startswith("catch"):
                in_try_block = False
            if "throw " in stripped and not in_try_block:
                errors.append({"line": i + 1, "type": "error_handling", "severity": "warning",
                               "msg": "throw without try block",
                               "fix": "try {"})
                break

        # mmain instead of main
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'int\s+m+ain\s*\(', stripped):
                errors.append({"line": i + 1, "type": "main", "severity": "error",
                               "msg": "Function name 'mmain' should be 'main'",
                               "fix": stripped.replace("mmain", "main")})

        # cout<< cin (wrong syntax)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "cout<<" in stripped and "cin" in stripped:
                errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                               "msg": "cout<< cin is wrong syntax",
                               "fix": "// Separate into: cout << prompt; cin >> var;"})

        # Orphaned string (string on its own line not assigned)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('"') and stripped.endswith('";'):
                if not any(kw in stripped for kw in ["cout", "cin", "throw", "return", "="]):
                    errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                                   "msg": "Orphaned string (not connected to cout)",
                                   "fix": 'cout << ' + stripped})

        # Wrong cout syntax (cout << expr << ;)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "cout" in stripped and stripped.endswith(";"):
                # Check for << at end before ;
                if re.search(r'<<\s*;\s*$', stripped):
                    errors.append({"line": i + 1, "type": "syntax", "severity": "error",
                                   "msg": "cout << ends with << (missing value)"})

        # Missing main function
        has_main = "int main()" in code_text
        if not has_main and "int main" not in code_text:
            # Check for mmain or other variants
            main_variants = re.findall(r'int\s+(\w*main\w*)\s*\(', code_text)
            if main_variants and main_variants[0] != "main":
                pass  # Already caught mmain above
            elif not main_variants:
                errors.append({"line": 1, "type": "main", "severity": "error",
                               "msg": "Missing main function"})

        # LOGIC ERRORS

        # Assignment in if/while condition (= instead of ==)
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'(if|while)\s*\(.*[^!=<>]=[^=]', stripped):
                if "==" not in stripped and "!=" not in stripped and ">=" not in stripped and "<=" not in stripped:
                    errors.append({"line": i + 1, "type": "logic", "severity": "error",
                                   "msg": "Assignment in condition (use == to compare)",
                                   "fix": stripped.replace("=", "==", 1)})

        # Wrong comparison direction
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.search(r'if\s*\(\s*\w+\s*<\s*0\s*\)', stripped):
                if "unsigned" in stripped or "size_t" in stripped:
                    errors.append({"line": i + 1, "type": "logic", "severity": "warning",
                                   "msg": "Unsigned value can never be < 0"})

        # Missing break in switch case
        in_switch = False
        in_case = False
        case_line = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "switch" in stripped:
                in_switch = True
            if in_switch and stripped.startswith("case "):
                in_case = True
                case_line = i + 1
            if in_switch and in_case and stripped == "break;":
                in_case = False
            if in_switch and in_case and stripped.startswith("case ") and i > case_line:
                errors.append({"line": case_line, "type": "logic", "severity": "warning",
                               "msg": "Missing break in previous case",
                               "fix": "        break;"})
                case_line = i + 1
            if in_switch and stripped == "}":
                in_switch = False
                in_case = False

        # Division by zero
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.search(r'/\s*0\b', stripped) and "==" not in stripped:
                errors.append({"line": i + 1, "type": "logic", "severity": "error",
                               "msg": "Division by zero"})

        # Comparing float with ==
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.search(r'(float|double)\s+\w+', stripped):
                if "==" in stripped:
                    errors.append({"line": i + 1, "type": "logic", "severity": "warning",
                                   "msg": "Avoid comparing floats with == (use epsilon)"})

        # Uninitialized variable usage
        declared = set()
        for i, line in enumerate(lines):
            stripped = line.strip()
            decl = re.match(r'(?:int|float|double|char|bool|string)\s+(\w+)\s*;', stripped)
            if decl:
                declared.add(decl.group(1))

        # Wrong array bounds
        for i, line in enumerate(lines):
            stripped = line.strip()
            arr_match = re.search(r'(\w+)\[(\w+)\]', stripped)
            if arr_match:
                idx = arr_match.group(2)
                if idx.isdigit():
                    size_match = re.search(r'(\w+)\[(\d+)\]', "\n".join(lines[:i]))
                    if size_match and int(idx) >= int(size_match.group(2)):
                        errors.append({"line": i + 1, "type": "logic", "severity": "error",
                                       "msg": "Array index out of bounds"})

        # Memory: new without delete
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "new " in stripped and "delete" not in code_text:
                errors.append({"line": i + 1, "type": "logic", "severity": "warning",
                               "msg": "Memory allocated with new but no delete found"})

        # Return wrong type
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("return"):
                ret_match = re.search(r'return\s+(.+);', stripped)
                if ret_match:
                    val = ret_match.group(1).strip()
                    if val.startswith('"') and val.endswith('"'):
                        for j in range(i - 1, max(0, i - 20), -1):
                            func_line = lines[j].strip()
                            if re.search(r'(int|float|double)\s+\w+\s*\(', func_line):
                                errors.append({"line": i + 1, "type": "logic", "severity": "error",
                                               "msg": "Returning string from non-string function"})
                                break

        return errors

    def analyze_missing(self, code):
        missing = []
        suggestions = []
        full_code = code

        has_class = "class " in full_code
        has_inherit = ": public " in full_code or ": private " in full_code
        has_constructor = bool(re.search(r'\w+\([^)]*\)\s*[:{]', full_code))
        has_virtual = "virtual " in full_code
        has_override = "override" in full_code
        has_plus = "operator+" in full_code
        has_stream = "operator<<" in full_code
        has_try = "try {" in full_code or "try{" in full_code
        has_catch = "catch " in full_code
        has_main = "int main()" in full_code
        has_return = "return 0" in full_code
        has_display = "display" in full_code or "print" in full_code or "show" in full_code

        if has_class and not has_constructor:
            missing.append("constructor")
            suggestions.append("Add constructor")

        if has_class and not has_display and not has_virtual:
            missing.append("display function")
            suggestions.append("Add display function")

        if has_class and not has_plus:
            missing.append("operator+")
            suggestions.append("Add operator+")

        if has_class and not has_stream:
            missing.append("operator<<")
            suggestions.append("Add operator<<")

        if has_inherit and not has_override:
            missing.append("override function")
            suggestions.append("Add override")

        if has_inherit and not has_plus:
            missing.append("inherited operator+")
            suggestions.append("Add inherited operator+")

        if has_inherit and not has_stream:
            missing.append("inherited operator<<")
            suggestions.append("Add inherited operator<<")

        if has_class and has_plus and has_stream and "};" not in full_code:
            missing.append("close class")
            suggestions.append("Add };")

        if has_try and not has_catch:
            missing.append("catch block")
            suggestions.append("Add catch block")

        if has_try and has_catch and not has_main:
            missing.append("main function")
            suggestions.append("Add main function")

        if has_main and not has_return:
            missing.append("return statement")
            suggestions.append("Add return 0;")

        if not missing:
            return None, "Code complete - all parts present"

        hint = "Missing:\n" + "\n".join([f"  - {m}" for m in missing])
        return suggestions, hint

class GUIApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AI Watcher")
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"280x{screen_h - 100}+0+50")
        self.root.configure(bg="#1E1E2E")
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.2)
        self.root.minsize(280, 400)
        self.root.overrideredirect(True)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)

        self.visible = False
        self.auto_hide = True
        self.suggestion = ""
        self.fix_data = None
        self.running = True
        self.status_text = "Ready"
        self.is_hovering = False
        self.hover_timer = None
        self.inserting = False
        self.pending_lines = []
        self.current_line_idx = 0
        self.key_buffer = ""
        self.key_buffer_time = 0
        self.all_errors = []
        self.current_error_idx = 0
        self.window_x = 0
        self.window_y = 50

        self.analyzer = CodeAnalyzer()

        self._build_gui()
        self._setup_tray()
        self._setup_hotkeys()
        self._setup_hover()
        self._start_key_watcher()
        self.root.withdraw()
        self._create_hover_zone()

    def _build_gui(self):
        code_font = tkfont.Font(family="Consolas", size=9)
        small_font = tkfont.Font(family="Consolas", size=8)
        tiny_font = tkfont.Font(family="Consolas", size=7)

        tk.Frame(self.root, bg="#BD93F9", height=2).pack(fill="x")

        top = tk.Frame(self.root, bg="#1E1E2E")
        top.pack(fill="x", padx=8, pady=(4, 2))

        tk.Label(top, text="AI", font=("Consolas", 10, "bold"),
                 fg="#BD93F9", bg="#1E1E2E").pack(side="left")

        self.debug_btn = tk.Button(top, text="F1", font=small_font,
            fg="#FFB86C", bg="#282A36", command=self._run_debug, relief="flat", padx=3)
        self.debug_btn.pack(side="right", padx=1)

        self.status_label = tk.Label(top, text=self.status_text, font=tiny_font,
            fg="#6272A4", bg="#1E1E2E")
        self.status_label.pack(side="right", padx=2)

        help_frame = tk.Frame(self.root, bg="#1E1E2E")
        help_frame.pack(fill="x", padx=8, pady=2)

        cmds = list(SNIPPETS.keys())
        row1 = " ".join([f"@{c}" for c in cmds[:5]])
        row2 = " ".join([f"@{c}" for c in cmds[5:]])
        tk.Label(help_frame, text=row1, font=tiny_font, fg="#8BE9FD", bg="#1E1E2E").pack(anchor="w")
        tk.Label(help_frame, text=row2, font=tiny_font, fg="#8BE9FD", bg="#1E1E2E").pack(anchor="w")

        sug_frame = tk.LabelFrame(self.root, text=" Suggestion ", font=small_font,
            fg="#50FA7B", bg="#1E1E2E", labelanchor="nw", bd=1, relief="solid")
        sug_frame.pack(fill="x", padx=8, pady=2)

        self.suggestion_label = tk.Label(sug_frame, text="  Ready", font=code_font,
            fg="#50FA7B", bg="#282A36", anchor="w", wraplength=250, padx=4, pady=2)
        self.suggestion_label.pack(fill="x")

        fix_frame = tk.LabelFrame(self.root, text=" Debug / Fix ", font=small_font,
            fg="#FFB86C", bg="#1E1E2E", labelanchor="nw", bd=1, relief="solid")
        fix_frame.pack(fill="x", padx=8, pady=2)

        self.fix_label = tk.Label(fix_frame, text="  No errors", font=code_font,
            fg="#FFB86C", bg="#282A36", anchor="w", wraplength=250, padx=4, pady=2)
        self.fix_label.pack(fill="x")

        btn_frame = tk.Frame(self.root, bg="#1E1E2E")
        btn_frame.pack(fill="x", padx=8, pady=2)

        self.accept_btn = tk.Button(btn_frame, text="Right", font=tiny_font,
            bg="#50FA7B", fg="#1E1E2E", command=self._accept_suggestion, state="disabled", relief="flat")
        self.accept_btn.pack(side="left", padx=1)

        self.apply_fix_btn = tk.Button(btn_frame, text="F2", font=tiny_font,
            bg="#FFB86C", fg="#1E1E2E", command=self._apply_fix, state="disabled", relief="flat")
        self.apply_fix_btn.pack(side="left", padx=1)

        self.next_err_btn = tk.Button(btn_frame, text="F3", font=tiny_font,
            fg="#BD93F9", bg="#282A36", command=self._next_error, state="disabled", relief="flat")
        self.next_err_btn.pack(side="left", padx=1)

        self.hide_btn = tk.Button(btn_frame, text="~", font=tiny_font,
            fg="#F1FA8C", bg="#282A36", command=self._hide_window, relief="flat")
        self.hide_btn.pack(side="right")

    def _setup_hover(self):
        pass

    def _on_hover_enter(self, event=None):
        self.is_hovering = True
        if not self.visible:
            if self.hover_timer:
                self.root.after_cancel(self.hover_timer)
            self.hover_timer = self.root.after(3000, self._show_from_hover)

    def _on_hover_leave(self, event=None):
        self.is_hovering = False
        if self.hover_timer:
            self.root.after_cancel(self.hover_timer)
            self.hover_timer = None
        if self.visible:
            self.root.after(100, self._check_mouse_leave)

    def _check_mouse_leave(self):
        try:
            x, y = self.root.winfo_pointerxy()
            wx = self.root.winfo_rootx()
            wy = self.root.winfo_rooty()
            ww = self.root.winfo_width()
            wh = self.root.winfo_height()
            if not (wx <= x <= wx + ww and wy <= y <= wy + wh):
                self._hide_window()
        except Exception:
            pass

    def _show_from_hover(self):
        if self.is_hovering:
            self._show_window()

    def _create_hover_zone(self):
        self.hover_zone = tk.Toplevel(self.root)
        self.hover_zone.overrideredirect(True)
        self.hover_zone.attributes("-topmost", True)
        self.hover_zone.attributes("-alpha", 0.01)
        self.hover_zone.configure(bg="black")
        zone_size = 20
        self.hover_zone.geometry(f"{zone_size}x{zone_size}+{self.window_x}+{self.window_y + 200}")
        self.hover_zone.bind("<Enter>", self._on_hover_enter)
        self.hover_zone.bind("<Leave>", self._on_hover_leave)
        self.hover_zone.lift()

    def _setup_tray(self):
        img = Image.new("RGBA", (64, 64), (30, 30, 46, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([16, 16, 48, 48], fill=(80, 250, 123, 255))
        draw.text((26, 20), "AI", fill=(30, 30, 46, 255))
        menu = pystray.Menu(
            pystray.MenuItem("AI Watcher", None, enabled=False),
            pystray.MenuItem("Toggle", self._tray_toggle),
            pystray.MenuItem("Auto-hide", self._tray_toggle_autohide,
                checked=lambda item: self.auto_hide),
            pystray.MenuItem("Quit", self._tray_quit)
        )
        self.tray = pystray.Icon("ai_watcher", img, "AI Watcher", menu)
        threading.Thread(target=self.tray.run, daemon=True).start()

    def _setup_hotkeys(self):
        keyboard.add_hotkey("right", lambda: self.root.after(0, self._on_right_key), suppress=False)
        keyboard.add_hotkey("down", lambda: self.root.after(0, self._on_right_key), suppress=False)
        keyboard.add_hotkey("left", lambda: self.root.after(0, self._dismiss_all), suppress=False)
        keyboard.add_hotkey("up", lambda: self.root.after(0, self._dismiss_all), suppress=False)
        keyboard.add_hotkey("ctrl+~", lambda: self.root.after(0, self._toggle_visibility), suppress=False)
        keyboard.add_hotkey("F1", lambda: self.root.after(0, self._run_debug), suppress=False)
        keyboard.add_hotkey("F2", lambda: self.root.after(0, self._apply_fix), suppress=False)
        keyboard.add_hotkey("F3", lambda: self.root.after(0, self._next_error), suppress=False)
        keyboard.add_hotkey("F4", lambda: self.root.after(0, self._run_devcpp_fix), suppress=False)

    def _on_right_key(self):
        if self.inserting:
            return
        if self.suggestion:
            self._accept_suggestion()

    def _tray_toggle(self, icon=None, item=None):
        self.root.after(0, self._toggle_visibility)
    def _tray_toggle_autohide(self, icon=None, item=None):
        self.auto_hide = not self.auto_hide
    def _tray_quit(self, icon=None, item=None):
        self.running = False
        self.tray.stop()
        try:
            self.hover_zone.destroy()
        except Exception:
            pass
        self.root.after(0, self.root.destroy)

    def _toggle_visibility(self):
        if self.visible:
            self._hide_window()
        else:
            self._show_window()
    def _show_window(self):
        self.visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.update()
        self.root.bind("<Leave>", self._on_hover_leave)
    def _hide_window(self):
        self.visible = False
        self.root.withdraw()
        self.root.update()

    def _set_status(self, text):
        self.status_text = text
        self.status_label.config(text=text)

    def _show_suggestion(self, text):
        self.suggestion = text
        self.suggestion_label.config(text=f"  {text}")
        self.accept_btn.config(state="normal")

    def _show_fix(self, error_type, error_msg, fix_line, line_num=1):
        self.fix_data = {"type": error_type, "msg": error_msg, "fix": fix_line, "line": line_num}
        type_icons = {"class": "C", "inheritance": "I", "error_handling": "E", "main": "M",
                      "syntax": "S", "overloading": "O", "missing": "?"}
        icon = type_icons.get(error_type, "?")
        self.fix_label.config(text=f"  [{icon}] L{line_num}: {error_msg}\n  Fix: {fix_line}")
        if fix_line:
            self.apply_fix_btn.config(state="normal")
        self._set_status(f"Error: {error_type}")

    def _show_errors(self, errors):
        if not errors:
            self.fix_label.config(text="  No errors")
            return
        type_icons = {"class": "C", "inheritance": "I", "error_handling": "E", "main": "M",
                      "syntax": "S", "overloading": "O"}
        lines = []
        for e in errors[:5]:
            icon = type_icons.get(e.get("type", ""), "?")
            fix_indicator = " -> has fix" if e.get("fix") else ""
            lines.append(f"  [{icon}] L{e['line']}: {e['msg']}{fix_indicator}")
        self.fix_label.config(text="\n".join(lines))

    def _accept_suggestion(self):
        if not self.suggestion:
            return
        text = self.suggestion
        self._dismiss_all()
        time.sleep(0.03)
        keyboard.send("end")
        time.sleep(0.01)
        keyboard.write(text, delay=0)
        self._set_status("Applied!")

    def _apply_fix(self):
        if not self.fix_data:
            return
        fix = self.fix_data["fix"]
        error_type = self.fix_data.get("type", "")
        error_msg = self.fix_data.get("msg", "")
        line_num = self.fix_data.get("line", 1)
        self.fix_data = None
        self.fix_label.config(text="  No errors")
        self.apply_fix_btn.config(state="disabled")

        if not fix:
            self._set_status("No fix available")
            return

        # Extract what to find and what to replace
        find_text = ""
        replace_text = fix

        if "mmain" in error_msg:
            find_text = "mmain"
            replace_text = "main"
        elif "throw without try" in error_msg:
            # Find the throw line and add try before it
            find_text = "throw"
            replace_text = "try {\n        throw"
        elif "cout<<" in error_msg and "cin" in error_msg:
            find_text = "cout<<"
            replace_text = "cout <<"
        elif "missing semicolon" in error_msg.lower():
            if "return 0" in error_msg:
                find_text = "return 0"
                replace_text = "return 0;"
            else:
                find_text = ""
        elif "private inheritance" in error_msg:
            find_text = ": BasicSkill{"
            replace_text = ": public BasicSkill{"
        elif "Orphaned string" in error_msg:
            find_text = ';"\\nEnter'
            replace_text = ""
        else:
            # Try to extract find text from error message
            words = error_msg.split()
            for w in words:
                if len(w) > 3 and w.isalpha():
                    find_text = w
                    break

        if not find_text:
            self._set_status("Cannot determine what to find")
            return

        def _do_fix():
            time.sleep(0.1)
            try:
                # Go to top of file
                keyboard.send("ctrl+home")
                time.sleep(0.2)

                # Open Find dialog
                keyboard.send("ctrl+f")
                time.sleep(0.3)

                # Type search text
                keyboard.write(find_text, delay=0)
                time.sleep(0.1)

                # Press Enter to find
                keyboard.send("enter")
                time.sleep(0.3)

                # Close Find dialog
                keyboard.send("escape")
                time.sleep(0.2)

                # Now cursor is at the error - select it
                # Use Ctrl+Shift+Right to select word
                for _ in range(len(find_text)):
                    keyboard.send("shift+right")
                    time.sleep(0.02)

                time.sleep(0.1)

                # Type the replacement
                keyboard.write(replace_text, delay=0)
                time.sleep(0.1)

            except Exception:
                pass

        threading.Thread(target=_do_fix, daemon=True).start()
        self._set_status(f"Fixed: {find_text} -> {replace_text}")

    def _next_error(self):
        if not self.all_errors:
            return
        self.current_error_idx = (self.current_error_idx + 1) % len(self.all_errors)
        err = self.all_errors[self.current_error_idx]
        fix = err.get("fix", "")
        self.fix_data = {"type": err.get("type", ""), "msg": err["msg"], "fix": fix}
        type_icons = {"class": "C", "inheritance": "I", "error_handling": "E", "main": "M",
                      "syntax": "S", "overloading": "O"}
        icon = type_icons.get(err.get("type", ""), "?")
        self.fix_label.config(text=f"  [{icon}] L{err['line']}: {err['msg']}\n  Fix: {fix}")
        if fix:
            self.apply_fix_btn.config(state="normal")
        self._set_status(f"Error {self.current_error_idx + 1}/{len(self.all_errors)}")

    def _dismiss_all(self):
        self.suggestion = ""
        self.suggestion_label.config(text="  Ready")
        self.accept_btn.config(state="disabled")

    def _detect_class_names(self):
        try:
            keyboard.send("ctrl+c")
            time.sleep(0.1)
            code = self.root.clipboard_get()
        except Exception:
            return "ClassName", "DerivedClass", [], "display", "Error"

        base = "ClassName"
        derived = "DerivedClass"
        members = []
        display_name = "display"
        throw_msg = "Error"

        if code and len(code) > 10:
            classes = re.findall(r'class\s+(\w+)', code)
            if len(classes) >= 2:
                base = classes[0]
                derived = classes[1]
            elif len(classes) == 1:
                inherit_match = re.search(r'class\s+(\w+)\s*:\s*(?:public|private|protected)\s+(\w+)', code)
                if inherit_match:
                    derived = inherit_match.group(1)
                    base = inherit_match.group(2)
                else:
                    base = classes[0]
                    derived = classes[0] + "Derived"

            member_patterns = [
                r'(int|float|double|string|char|bool)\s+(\w+)\s*[;=]',
            ]
            for pattern in member_patterns:
                found = re.findall(pattern, code)
                for dtype, name in found:
                    if name not in ["main", "value", "obj1", "obj2", "obj3", "obj4", "upgrade", "msg", "out", "a", "la"]:
                        members.append({"type": dtype, "name": name})

            display_match = re.search(r'void\s+(\w+)\s*\(', code)
            if display_match:
                display_name = display_match.group(1)

            throw_match = re.search(r'throw\s+"([^"]+)"', code)
            if throw_match:
                throw_msg = throw_match.group(1)

        return base, derived, members, display_name, throw_msg

    def _get_smart_snippet(self, name):
        base, derived, members, display_name, throw_msg = self._detect_class_names()

        if members:
            member_decl = "\n".join([f"    {m['type']} {m['name']};" for m in members])
            ctor_params = ", ".join([f"{m['type'][0]} {m['name'][0]}=0" for m in members])
            ctor_body = "\n".join([f"        if({m['name'][0]}<0)throw \"{m['name']} cannot be negative\";\n        {m['name']} = {m['name'][0]};" for m in members])
            display_body = "\n".join([f"        cout << \"{m['name']}: \" << {m['name']} << endl;" for m in members])
            plus_params = ", ".join([f"{m['name']} + value" for m in members])
            stream_body = "\n".join([f"        cout << \"{m['name']}: \" << obj.{m['name']};" for m in members])
        else:
            member_decl = "    int value;"
            ctor_params = "int v=0"
            ctor_body = "        if(v<0)throw \"Value cannot be negative\";\n        value = v;"
            display_body = "        cout << \"Value: \" << value << endl;"
            plus_params = "value + value"
            stream_body = "        cout << \"Value: \" << obj.value;"

        member_name = members[0]["name"] if members else "value"

        smart_snippets = {
            "cls": f"class {base}{{\nprotected:\n{member_decl}\n\npublic:",
            "ctor": f"    {base}(int m = 0){{\n        if (m < 0) throw \"{member_name} cannot be negative!\";\n        {member_name} = m;\n    }}",
            "virt": f"    virtual void {display_name}(){{\n        cout << \"Value: \" << {member_name} << endl;\n    }}",
            "ope": f"    {base} operator + (int value){{\n        return {base}({member_name} + value);\n    }}",
            "stream": f"    friend ostream & operator << (ostream& out, {base}& obj){{\n        cout << \"Value: \" << obj.{member_name} << endl;\n        return out;\n    }}",
            "}": "};",
            "sub": f"class {derived}: public {base}{{\nprivate:\n    int bonus;\n\npublic:",
            "subctor": f"    {derived}(int m = 0, int b = 0): {base}(m){{\n        if (b < 0) throw \"bonus cannot be negative!\";\n        bonus = b;\n    }}",
            "ovr": f"    void {display_name}(){{\n        cout << \"Value: \" << {member_name} << endl;\n        cout << \"Bonus: \" << bonus << endl;\n    }}",
            "subope": f"    {derived} operator + (int value){{\n        return {derived}({member_name} + value, bonus + value);\n    }}",
            "substream": f"    friend ostream & operator << (ostream& out, {derived}& obj){{\n        cout << \"Value: \" << obj.{member_name} << endl;\n        cout << \"Bonus: \" << obj.bonus;\n        return out;\n    }}",
            "try": f"try{{\n    {base} bs1, bs2(100);\n    {derived} ss1;\n    {derived} ss2(100, 50);\n\n    cout << \"{base} 1 Details\\n\";\n    bs1.{display_name}();\n    cout << \"--------------------\\n\";\n    cout << \"\\n {base} 2 Details\\n\";\n    bs2.{display_name}();\n    cout << \"--------------------\\n\";\n    cout << \"\\n{derived} 1 Details\\n\";\n    ss1.{display_name}();\n    cout << \"--------------------\\n\";\n    cout << \"\\n{derived} 2 Details\\n\";\n    ss2.{display_name}();\n    cout << \"--------------------\\n\";\n\n    int upgrade;\n    cout << \"\\n Upgrade: \";\n    cin >> upgrade;\n\n    if(cin.fail())\n        throw \"\\n Invalid Input\";\n    if(upgrade < 0)\n        throw \"\\n Invalid Input\";\n\n    bs1 = bs1 + upgrade;\n    bs2 = bs2 + upgrade;\n    ss1 = ss1 + upgrade;\n    ss2 = ss2 + upgrade;\n\n    cout << \"{base} 1 Details\\n\" << bs1 << endl;\n    cout << \"--------------------\\n\";\n    cout << \"\\n {base} 2 Details\\n\" << bs2 << endl;\n    cout << \"--------------------\\n\";\n    cout << \"\\n{derived} 1 Details\\n\" << ss1 << endl;\n    cout << \"--------------------\\n\";\n    cout << \"\\n{derived} 2 Details\\n\" << ss2 << endl;\n    cout << \"--------------------\\n\";\n}}\ncatch(const char* msg){{\n    cout << \"\\n Error\" << msg << endl;\n}}",
            "main": f"int main(){{\n    try{{\n        {base} bs1, bs2(100);\n        {derived} ss1;\n        {derived} ss2(100, 50);\n\n        cout << \"{base} 1 Details\\n\";\n        bs1.{display_name}();\n        cout << \"--------------------\\n\";\n        cout << \"\\n {base} 2 Details\\n\";\n        bs2.{display_name}();\n        cout << \"--------------------\\n\";\n        cout << \"\\n{derived} 1 Details\\n\";\n        ss1.{display_name}();\n        cout << \"--------------------\\n\";\n        cout << \"\\n{derived} 2 Details\\n\";\n        ss2.{display_name}();\n        cout << \"--------------------\\n\";\n\n        int upgrade;\n        cout << \"\\n Upgrade: \";\n        cin >> upgrade;\n\n        if(cin.fail())\n            throw \"\\n Invalid Input\";\n        if(upgrade < 0)\n            throw \"\\n Invalid Input\";\n\n        bs1 = bs1 + upgrade;\n        bs2 = bs2 + upgrade;\n        ss1 = ss1 + upgrade;\n        ss2 = ss2 + upgrade;\n\n        cout << \"{base} 1 Details\\n\" << bs1 << endl;\n        cout << \"--------------------\\n\";\n        cout << \"\\n {base} 2 Details\\n\" << bs2 << endl;\n        cout << \"--------------------\\n\";\n        cout << \"\\n{derived} 1 Details\\n\" << ss1 << endl;\n        cout << \"--------------------\\n\";\n        cout << \"\\n{derived} 2 Details\\n\" << ss2 << endl;\n        cout << \"--------------------\\n\";\n    }}\n    catch(const char* msg){{\n        cout << \"\\n Error\" << msg << endl;\n    }}\n    return 0;\n}}",
        }

        return smart_snippets.get(name)

    def _detect_class_names(self):
        try:
            # Clear clipboard first
            try:
                root = tk.Tk()
                root.withdraw()
                root.clipboard_clear()
                root.update()
                root.destroy()
            except:
                pass
            
            time.sleep(0.05)
            
            # Select all and copy
            keyboard.send("ctrl+a")
            time.sleep(0.1)
            keyboard.send("ctrl+c")
            time.sleep(0.15)
            code = self.root.clipboard_get()
            
            # Undo the selection
            keyboard.send("ctrl+z")
            time.sleep(0.05)
        except Exception:
            return "ClassName", "DerivedClass", [], "display", []

        base = "ClassName"
        derived = "DerivedClass"
        members = []
        display_name = "display"
        functions = []

        if code and len(code) > 10:
            classes = re.findall(r'class\s+(\w+)', code)
            if len(classes) >= 2:
                base = classes[0]
                derived = classes[1]
            elif len(classes) == 1:
                inherit_match = re.search(r'class\s+(\w+)\s*:\s*(?:public|private|protected)\s+(\w+)', code)
                if inherit_match:
                    derived = inherit_match.group(1)
                    base = inherit_match.group(2)
                else:
                    base = classes[0]
                    derived = classes[0] + "Derived"

            for pattern in [r'(int|float|double|string|char|bool)\s+(\w+)\s*[;=]']:
                found = re.findall(pattern, code)
                for dtype, name in found:
                    if name not in ["main", "value", "obj1", "obj2", "obj3", "obj4", "upgrade", "msg", "out", "a", "la"]:
                        members.append({"type": dtype, "name": name})

            # Detect which functions exist
            if re.search(r'void\s+display', code):
                functions.append("display")
                display_name = "display"
            elif re.search(r'void\s+\w+', code):
                func_match = re.search(r'void\s+(\w+)\s*\(', code)
                if func_match:
                    display_name = func_match.group(1)
                    functions.append(display_name)

            if "operator+" in code:
                functions.append("ope")
            if "operator<<" in code:
                functions.append("stream")

        return base, derived, members, display_name, functions

    def _get_smart_code(self, name):
        base, derived, members, display_name, functions = self._detect_class_names()

        if members:
            member_decl = "\n".join([f"    {m['type']} {m['name']};" for m in members])
            ctor_params = ", ".join([f"{m['type'][0]} {m['name'][0]}=0" for m in members])
            ctor_body = "\n".join([f"        if({m['name'][0]}<0)throw \"{m['name']} cannot be negative\";\n        {m['name']} = {m['name'][0]};" for m in members])
            display_body = "\n".join([f"        cout << \"{m['name']}: \" << {m['name']} << endl;" for m in members])
            plus_params = ", ".join([f"{m['name']} + value" for m in members])
            stream_body = "\n".join([f"        cout << \"{m['name']}: \" << obj.{m['name']};" for m in members])
        else:
            member_decl = "    int value;"
            ctor_params = "int v=0"
            ctor_body = "        if(v<0)throw \"Value cannot be negative\";\n        value = v;"
            display_body = "        cout << \"Value: \" << value << endl;"
            plus_params = "value + value"
            stream_body = "        cout << \"Value: \" << obj.value;"

        # Build test lines based on detected functions
        test_lines = []
        test_lines.append(f"        {base} bs1, bs2(100);")
        test_lines.append(f"        {derived} ss1;")
        test_lines.append(f"        {derived} ss2(100, 50);")
        test_lines.append("")
        
        if "display" in functions or display_name in functions:
            test_lines.append(f'        cout << "{base} 1 Details\\n";')
            test_lines.append(f"        bs1.{display_name}();")
            test_lines.append('        cout << "--------------------\\n";')
            test_lines.append(f'        cout << "\\n {base} 2 Details\\n";')
            test_lines.append(f"        bs2.{display_name}();")
            test_lines.append('        cout << "--------------------\\n";')
            test_lines.append(f'        cout << "\\n{derived} 1 Details\\n";')
            test_lines.append(f"        ss1.{display_name}();")
            test_lines.append('        cout << "--------------------\\n";')
            test_lines.append(f'        cout << "\\n{derived} 2 Details\\n";')
            test_lines.append(f"        ss2.{display_name}();")
            test_lines.append('        cout << "--------------------\\n";')
        
        if "ope" in functions:
            test_lines.append("")
            test_lines.append("        int upgrade;")
            test_lines.append('        cout << "\\n Upgrade: ";')
            test_lines.append("        cin >> upgrade;")
            test_lines.append("")
            test_lines.append("        if(cin.fail())")
            test_lines.append('            throw "\\n Invalid Input";')
            test_lines.append("        if(upgrade < 0)")
            test_lines.append('            throw "\\n Invalid Input";')
            test_lines.append("")
            test_lines.append("        bs1 = bs1 + upgrade;")
            test_lines.append("        bs2 = bs2 + upgrade;")
            test_lines.append("        ss1 = ss1 + upgrade;")
            test_lines.append("        ss2 = ss2 + upgrade;")
        
        if "stream" in functions:
            test_lines.append("")
            test_lines.append(f'        cout << "{base} 1 Details\\n" << bs1 << endl;')
            test_lines.append('        cout << "--------------------\\n";')
            test_lines.append(f'        cout << "\\n {base} 2 Details\\n" << bs2 << endl;')
            test_lines.append('        cout << "--------------------\\n";')
            test_lines.append(f'        cout << "\\n{derived} 1 Details\\n" << ss1 << endl;')
            test_lines.append('        cout << "--------------------\\n";')
            test_lines.append(f'        cout << "\\n{derived} 2 Details\\n" << ss2 << endl;')
            test_lines.append('        cout << "--------------------\\n";')

        test_code = "\n".join(test_lines)

        smart = {
            "cls": f"class {base}{{\nprivate:\n{member_decl}\n\npublic:",
            "ctor": f"    {base}({ctor_params}){{\n{ctor_body}\n    }}",
            "virt": f"    virtual void {display_name}(){{\n{display_body}\n    }}",
            "ope": f"    {base} operator+(int value){{\n        return {base}({plus_params});\n    }}",
            "stream": f"    friend ostream& operator<<(ostream& out, {base}& obj){{\n{stream_body}\n        return out;\n    }}",
            "}": "};",
            "sub": f"class {derived}: public {base}{{\nprivate:\n    int extra;\n\npublic:",
            "subctor": f"    {derived}(int v=0, int e=0):{base}(v){{\n        if(e<0)throw \"Extra cannot be negative\";\n        extra = e;\n    }}",
            "ovr": f"    void {display_name}() override{{\n{display_body}\n        cout << \"Extra: \" << extra << endl;\n    }}",
            "subope": f"    {derived} operator+(int value){{\n        return {derived}({plus_params}, extra + value);\n    }}",
            "substream": f"    friend ostream& operator<<(ostream& out, {derived}& obj){{\n{stream_body}\n        cout << \", Extra: \" << obj.extra;\n        return out;\n    }}",
            "try": f"try {{\n{test_code}\n}}\ncatch (const char* msg){{\n    cout << \"\\nError: \" << msg << endl;\n}}",
            "main": f"int main(){{\n    try {{\n{test_code}\n    }}\n    catch (const char* msg){{\n        cout << \"\\nError: \" << msg << endl;\n    }}\n    return 0;\n}}",
        }

        return smart.get(name)

    def _insert_snippet(self, name):
        # @full uses static snippet, others use smart detection
        if name == "full":
            snippet = SNIPPETS.get(name)
            if not snippet:
                return
            code = snippet["code"]
        else:
            code = self._get_smart_code(name)
            if not code:
                return
        
        self.inserting = True
        self.key_buffer = ""
        self.root.after(0, lambda: self._set_status(f"Inserting @{name}..."))

        def _do_insert():
            time.sleep(0.15)
            
            if name == "full":
                # Insert in chunks to avoid lag
                chunks = code.split("\n\n")
                for chunk in chunks:
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    try:
                        root = tk.Tk()
                        root.withdraw()
                        root.clipboard_clear()
                        root.clipboard_append(chunk)
                        root.update()
                        root.destroy()
                    except:
                        pass
                    time.sleep(0.1)
                    keyboard.send("ctrl+v")
                    time.sleep(0.2)
                    keyboard.send("enter")
                    time.sleep(0.1)
            else:
                try:
                    root = tk.Tk()
                    root.withdraw()
                    root.clipboard_clear()
                    root.clipboard_append(code)
                    root.update()
                    root.destroy()
                except:
                    pass
                time.sleep(0.1)
                keyboard.send("ctrl+v")
                time.sleep(0.2)
            
            self.inserting = False
            self.key_buffer = ""
            self.root.after(0, lambda: self._set_status(f"Inserted @{name}"))

        threading.Thread(target=_do_insert, daemon=True).start()

    def _continue_snippet(self):
        pass

    def _on_key_event(self, event):
        if self.inserting:
            return
        if event.event_type != "down":
            return

        now = time.time()

        if event.name == "space":
            if self.key_buffer.startswith("@"):
                cmd = self.key_buffer[1:].lower()
                if cmd in SNIPPETS:
                    # Delete the @command text
                    for _ in range(len(self.key_buffer) + 2):
                        keyboard.send("backspace")
                        time.sleep(0.02)
                    time.sleep(0.2)
                    self._insert_snippet(cmd)
                    self.key_buffer = ""
                    return
            self.key_buffer = ""
            return

        if event.name == "backspace":
            self.key_buffer = self.key_buffer[:-1]
            return

        char_map = {
            "shift+8": "*", "shift+=": "+", "shift+comma": "<",
            "shift+period": ">", "shift+minus": "_", "shift+semicolon": ":",
            "shift+9": "(", "shift+0": ")", "shift+[": "{", "shift+]": "}",
            "shift+5": "%", "shift+6": "^", "shift+7": "&",
            "quote": "'", "shift+quote": '"',
        }

        if event.name in char_map:
            self.key_buffer += char_map[event.name]
        elif len(event.name) == 1:
            self.key_buffer += event.name
        else:
            self.key_buffer = ""

        if now - self.key_buffer_time > 2:
            self.key_buffer = ""
        self.key_buffer_time = now

        if len(self.key_buffer) > 20:
            self.key_buffer = self.key_buffer[-20:]

    def _start_key_watcher(self):
        keyboard.on_press(self._on_key_event)

    def _run_debug(self):
        if self.inserting:
            return
        threading.Thread(target=self._debug_thread, daemon=True).start()

    def _read_devcpp_errors(self):
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, None)
            errors = []
            def enum_callback(hwnd, lParam):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    # Check for both Embarcadero and original Dev-C++
                    is_devcpp = ("devcpp" in title.lower() or 
                                "dev-c" in title.lower() or
                                "bloodshed" in title.lower() or
                                "orwell" in title.lower() or
                                "embarcadero" in title.lower())
                    if is_devcpp:
                        # Found Dev-C++ window, try to read its child windows
                        def enum_children(child_hwnd, lParam):
                            child_len = ctypes.windll.user32.GetWindowTextLengthW(child_hwnd)
                            if child_len > 0:
                                child_buf = ctypes.create_unicode_buffer(child_len + 1)
                                ctypes.windll.user32.GetWindowTextW(child_hwnd, child_buf, child_len + 1)
                            return True
                        ctypes.windll.user32.EnumChildWindows(hwnd, enum_children, 0)
                return True
            ctypes.windll.user32.EnumWindows(enum_callback, 0)

            # Try reading from clipboard after compile
            keyboard.send("ctrl+c")
            time.sleep(0.1)
            text = self.root.clipboard_get()
            if text:
                for line in text.split("\n"):
                    line = line.strip()
                    if re.match(r'\d+\s*:', line) or "error:" in line.lower() or "warning:" in line.lower():
                        errors.append(line)
            return errors
        except Exception:
            return []

    def _parse_devcpp_error(self, error_line):
        fix = ""
        msg = error_line

        # Parse common Dev-C++ error formats
        # Format: "Line:col: error: message"
        match = re.match(r'(\d+):?\d*:\s*(error|warning):\s*(.+)', error_line)
        if match:
            line_num = int(match.group(1))
            err_type = match.group(2)
            err_msg = match.group(3)

            # Generate fix based on error message
            if "was not declared" in err_msg:
                var_match = re.search(r"'(\w+)' was not declared", err_msg)
                if var_match:
                    fix = "// Did you mean to declare: int " + var_match.group(1) + ";"
            elif "before" in err_msg and "token" in err_msg:
                token_match = re.search(r"before '(\w+)'", err_msg)
                if token_match:
                    fix = "// Missing token before: " + token_match.group(1)
            elif "expected" in err_msg:
                fix = "// " + err_msg
            elif "redefinition" in err_msg:
                fix = "// Variable already defined - remove duplicate"
            elif "undeclared" in err_msg:
                var_match = re.search(r"'(\w+)'", err_msg)
                if var_match:
                    fix = "// Did you forget to declare: " + var_match.group(1)
            elif "cannot convert" in err_msg:
                fix = "// " + err_msg
            elif "no matching function" in err_msg:
                fix = "// Check function signature"
            elif "initialized" in err_msg:
                fix = "// " + err_msg

            return {"line": line_num, "type": "compiler", "severity": err_type,
                    "msg": err_msg, "fix": fix}

        return None

    def _debug_thread(self):
        self.root.after(0, lambda: self._set_status("Reading selection..."))
        try:
            keyboard.send("ctrl+c")
            time.sleep(0.1)
            code = self.root.clipboard_get()
        except Exception:
            code = ""

        if not code or len(code) < 5:
            self.root.after(0, lambda: self._set_status("No selection - highlight code first"))
            return

        self.root.after(0, lambda: self._set_status("Analyzing..."))
        errors = self.analyzer.detect_errors(code)
        self.all_errors = errors
        self.current_error_idx = 0

        if errors:
            self.root.after(0, lambda e=errors: self._show_errors(e))
            fix = errors[0].get("fix", "")
            if fix:
                self.root.after(0, lambda t=errors[0]["type"], m=errors[0]["msg"], f=fix, l=errors[0]["line"]: self._show_fix(t, m, f, l))
                self.root.after(0, lambda: self.next_err_btn.config(state="normal"))
        else:
            suggestions, hint = self.analyzer.analyze_missing(code)
            if suggestions:
                self.root.after(0, lambda h=hint: self._show_fix("missing", h, "", 1))
                self.root.after(0, lambda: self._set_status("Missing parts detected"))
            else:
                self.root.after(0, lambda: self._set_status("Code complete - no errors"))

    def _run_devcpp_fix(self):
        threading.Thread(target=self._devcpp_fix_thread, daemon=True).start()

    def _devcpp_fix_thread(self):
        self.root.after(0, lambda: self._set_status("Reading Dev-C++ errors..."))
        devcpp_errors = self._read_devcpp_errors()

        if not devcpp_errors:
            self.root.after(0, lambda: self._set_status("No compiler errors found"))
            return

        parsed_errors = []
        for err_line in devcpp_errors:
            parsed = self._parse_devcpp_error(err_line)
            if parsed:
                parsed_errors.append(parsed)

        if parsed_errors:
            self.all_errors = parsed_errors
            self.current_error_idx = 0
            self.root.after(0, lambda e=parsed_errors: self._show_errors(e))
            fix = parsed_errors[0].get("fix", "")
            if fix:
                self.root.after(0, lambda t=parsed_errors[0]["type"], m=parsed_errors[0]["msg"], f=fix, l=parsed_errors[0]["line"]: self._show_fix(t, m, f, l))
            self.root.after(0, lambda: self._set_status(f"Found {len(parsed_errors)} compiler errors"))
        else:
            self.root.after(0, lambda: self._set_status("Could not parse errors"))

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = GUIApp()
    app.run()
