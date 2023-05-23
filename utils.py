import curses
import asyncio
import _curses
from typing import Union
from math import floor
from abc import abstractmethod, ABC
import logging
import re
from datetime import datetime

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
                for x in (string[cls.last_end:start]).split(' '):
                    result.append((x, 0))

                result.append((string[start:end], replacement[cls.replacement_index]))
                cls.last_end = end
                cls.replacement_index = (cls.replacement_index + 1) % len(replacement)
                return ''
            
            re.sub(combined_pattern, substitute, string)
            for x in (string[cls.last_end:]).split(' '):
                result.append((x, 0))

            return result

    def show(self):
        all_lines = self.lines
        box_width = self.width

        self.box.addstr(1, 1, '') # Initialize strings in box
        real_lines = []
        for line in reversed(all_lines):
            list_line = []
            for pattern, colors in self.re_patterns:
                matched = re.match(pattern, line)
                if matched is not None:
                    groups = matched.groups()
                    if len(groups) > 0:
                        list_line = self.TextProcessor.replace_with_index(groups, colors, line)
                        break
            
            if list_line == []:
                list_line = [(word, 0) for word in line.split(' ')]

            lenght = 0

            new_lines = [[]]
            for word_obj in list_line:
                lenght += (len(word_obj[0]) + 1)
                
                if lenght > box_width - 5:
                    lenght = len(word_obj[0])
                    word_obj = ("|--\t" + word_obj[0], word_obj[1])
                    new_lines.append([word_obj])
                else:
                    new_lines[-1].append(word_obj)
            
            real_lines += reversed(new_lines)

            if len(real_lines) > self.height - 2:
                break
        
        for idx, list_line in enumerate(reversed(real_lines)):
            if idx + 1 > self.height - 2:
                break

            self.box.addstr(idx+1, 1, '')
            for word in list_line:
                line, color = word
                if color:
                   color =  curses.color_pair(color)

                self.box.addstr(line + ' ', color)

class PBarBox(Box):
    finished: int
    total: int
    started: datetime
    elapsed: datetime
    rate: float         # files/s

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.finished = 0
        self.total = 0

        time_now = datetime.now()
        self.elapsed = int((time_now - self.started).total_seconds())
        self.rate = 0
        self.remaining = 0

    def update(self, finished: int, total: int):
        self.finished = finished
        self.total = total

        time_now = datetime.now()
        self.elapsed = int((time_now - self.started).total_seconds())
        self.rate = round(self.finished / self.elapsed, 2) if self.finished and self.elapsed else "0"
        self.remaining = int((self.total - self.finished) * self.rate)
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
    started: datetime

    def __init__(self):
        self.update = True
        self.stdscr = None

        # Boxes
        self.logs_box = None
        self.pbar_box = None
        self.send_box = None
        self.stats_box = None
        self.info_box = None

        self.started = datetime.now()
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
        try:
            self.logger.warning("Aperte qualquer tecla para sair")
            self.make_display()
        except:
            logging.error("Erro ao executar ultima atualizacao do display")

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
        if (bash_height, bash_width) == (self.bash_height, self.bash_width):
            attributes = [self.logs_box, self.pbar_box, self.send_box, self.stats_box, self.info_box]
            if None not in attributes:
                for attribute in attributes:
                    attribute.box.refresh()
                
                return

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
            "pbar_box": PBarBox(height=pbar_box_h, width=left_side, x=0, y=log_box_h, title="Progresso",
                                re_patterns=self.re_patterns.get('pbar_box', []), started=self.started),

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
                if get_object is not None:
                    if type(get_object) is StrBox:
                        args = (get_object.lines,)
                    else:
                        args = (get_object.finished, get_object.total)

                    new_object.update(*args)
            
            self.__setattr__(new_object_name, new_object)
            self.__getattribute__(new_object_name).box.refresh()

    def emit(self, record):
        try:
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

    def monitor_decorator(self, func):
        async def wrapper(*arg, **kw):
            requests = asyncio.create_task(func(*arg, **kw))
            auto_update = asyncio.create_task(self.auto_update())
            try:
                done, pending = await asyncio.wait({auto_update, requests}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                self.cleanup()

        return wrapper