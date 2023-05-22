import curses
import asyncio
import _curses
from typing import Union
from math import floor
from abc import abstractmethod, ABC
import logging
import re

class Box(ABC):
    title: str
    x: int
    y: int
    width: int
    height: int
    box: "_curses._CursesWindow"
    re_patterns: list

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.box = curses.newwin(self.height, self.width, self.y, self.x)
        self.box.box()
        self.box.addstr(0, 2, self.title)

    @abstractmethod
    def show():
        ...

    @abstractmethod
    def update(self, *args):
        #...
        #self.show()
        ...

class StrBox(Box):
    lines: list

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lines = []

    def update(self, new_lines: Union[list, str], index: int = None):
        if type(new_lines) is list:
            self.lines = new_lines
        else:
            if index is not None and len(self.lines) > index:
                self.lines[index] = new_lines
            else:
                self.lines.append(new_lines)

        self.show()
        return len(self.lines) - 1

    class TextProcessor:
        @classmethod
        def replace_with_index(cls, patterns, replacement, string):
            combined_pattern = '|'.join(map(re.escape, patterns))
            result = []
            cls.last_end = 0
            cls.replacement_index = 0

            def substitute(match):
                start = match.start()
                end = match.end()
                result.append(string[cls.last_end:start])
                result.append((string[start:end], replacement[cls.replacement_index]))
                cls.last_end = end
                cls.replacement_index = (cls.replacement_index + 1) % len(replacement)
                return ''

            new_string = re.sub(combined_pattern, substitute, string)
            result.append(string[cls.last_end:])

            if not result:
                result.append(new_string)

            return result


    def show(self):
        list_lines = self.lines
        if len(list_lines) > self.height - 2:
            list_lines = list_lines[len(list_lines)-self.height+2:]
        
        self.box.addstr(1, 1, '')
        for idx, line in enumerate(list_lines):
            attr = ...
            c_lines = [line]
            colored = False
            for pattern, colors in self.re_patterns:
                matched = re.match(pattern, line)
                if matched is not None:
                    groups = matched.groups()
                    if len(groups) > 0:
                        c_lines = self.TextProcessor.replace_with_index(groups, colors, line)
                        colored = True
                        break

            # Init line
            if colored:
                self.box.addstr(idx+1, 1, '')
                for line in c_lines:
                    args = (line, 0)
                    if type(line) is tuple:
                        line, attr = line[0], curses.color_pair(line[1])
                        args = (line, attr)
                    
                    self.box.addstr(*args)
            else:
                self.box.addstr(idx+1, 1, line)

class PBarBox(Box):
    finished: int
    total: int

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.finished = 0
        self.total = 0

    def update(self, finished: int, total: int):
        self.finished = finished
        self.total = total
        self.show()

    def show(self):
        progress = (self.finished / self.total) if self.total > 0 else 0
        progress_w = int((self.width - 2) * progress)
        self.box.addstr(0, 2, f"Progresso - {int(progress*100)}%")
        for height in range(1, self.height - 1):
            self.box.addstr(height, 1, ' ' * progress_w, curses.color_pair(1))

class SendRequestsFront(logging.Handler):
    logs_box: StrBox
    pbar_box: PBarBox
    send_box: StrBox
    stats_box: StrBox
    info_box: StrBox
    re_patterns: dict

    bash_width: int
    bash_height: int

    logger: logging.Logger

    def __init__(self):
        self.update = True
        self.stdscr = None
        self.initialize()
        self.make_display()

        # Init custom logging
        logging.Handler.__init__(self)
        self.formatter = logging.Formatter('%(asctime)-6s %(name)-6s/%(levelname)-6s| %(message)-2s', '%H:%M')
        logging.addLevelName(logging.INFO, 'info')
        logging.addLevelName(logging.ERROR, 'error')
        logging.addLevelName(logging.WARN, 'warn')

    def initialize(self):
        # Start Screen
        self.stdscr = curses.initscr()
        self.bash_height, self.bash_width = self.stdscr.getmaxyx()
        curses.noecho()
        curses.curs_set(0)
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.clear()
        self.stdscr.refresh()

        # Colors
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE) # Loading
        curses.init_pair(2, curses.COLOR_YELLOW, -1)# WARNING YELLOW
        curses.init_pair(3, curses.COLOR_RED, -1)   # ERROR RED
        curses.init_pair(4, curses.COLOR_GREEN, -1) # INFO GREEN
        curses.init_pair(5, -1, curses.COLOR_BLUE)  # IN QUEUE  SYMBOL
        curses.init_pair(6, -1, curses.COLOR_GREEN) # OK SYMBOL
        curses.init_pair(7, -1, curses.COLOR_RED)   # ERROR SYMBOL
        curses.init_pair(8, 236, -1) # GRAY TEXT
        self.define_regex_patterns()
        
        # Logging
        self.logger = logging.getLogger('Requests')
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(self)

    def cleanup(self):
        self.make_display()
        self.update = False
        if self.stdscr:
            self.stdscr.getch()
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.curs_set(1)
            curses.endwin()

    async def auto_update(self):
        while self.update:
            self.make_display()
            await asyncio.sleep(0.1)

    def define_regex_patterns(self) -> dict:
        # list of: [pattern, [colors]] Colors is for color de matchs
        re_pattern = {
            "logs_box": [
               (r"^.*?\s\w.*\/(warn).*$", [2]),
               (r"^.*?\s\w.*\/(error).*$", [3]),
               (r"^.*?\s\w.*\/(info).*$", [4])
            ],
            "send_box": [
                (r"^(\s~\s)", [5]),
                (re.compile(r'^(\s\u2714\s)(.*$)', re.UNICODE), [6, 8]),
                (r"^(\sx\s)(.*$)", [7, 8])
            ]
        }
        self.re_patterns = re_pattern
        
    def make_display(self) -> None:
        bash_height, bash_width = self.stdscr.getmaxyx()

        left_side = floor(bash_width*.6)
        right_side = bash_width - left_side
        right_sub = right_side // 2

        # Heights
        # Left
        log_box_h = floor(bash_height*.90)
        pbar_box_h = bash_height - log_box_h

        # Right
        files_box_h = floor(bash_height*.5)
        stats_box_h = bash_height - files_box_h
        info_box_h = bash_height - files_box_h

        # CRIA CAIXAS
        # Logging
        local = {
            "logs_box": StrBox(height=log_box_h, width=left_side, x=0, y=0, title="Logging", re_patterns=self.re_patterns.get('logs_box', [])),
            "pbar_box": PBarBox(height=pbar_box_h, width=left_side, x=0, y=log_box_h, title="Progresso", re_patterns=self.re_patterns.get('pbar_box', [])),

            # Arquivos
            "send_box": StrBox(height=files_box_h, width=right_side, x=left_side, y=0, title="Service tasks", re_patterns=self.re_patterns.get('send_box', [])),

            # Subinfo
            "stats_box": StrBox(height=stats_box_h, width=right_sub, x=right_side+right_sub, y=files_box_h, title="Stats", re_patterns=self.re_patterns.get('stats_box', [])),
            "info_box": StrBox(height=info_box_h, width=right_sub, x=right_side+(2*right_sub), y=files_box_h, title="Information", re_patterns=self.re_patterns.get('info_box', []))
        }
        for new_object_name in local.keys():
            new_object = local[new_object_name]
            if new_object_name in self.__dict__:
                get_object = self.__getattribute__(new_object_name)
                if type(get_object) is StrBox:
                    args = (get_object.lines,)
                else:
                    args = (get_object.finished, get_object.total)

                new_object.update(*args)
            
            self.__setattr__(new_object_name, new_object)
            self.__getattribute__(new_object_name).box.refresh()

    def emit(self, record):
        try:
            #msg = self.format(record)
            msg = self.formatter.format(record)
            window = self.logs_box
            fs = "\n%s"
            try:
                window.update(msg)
            except UnicodeError:
                window.update((fs % msg).encode("UTF-8"))
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)