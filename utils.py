import curses
import asyncio
import _curses
from typing import Union
from math import floor
from abc import abstractmethod, ABC

class Box(ABC):
    title: str
    x: int
    y: int
    width: int
    height: int
    box: "_curses._CursesWindow"

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

    def update(self, new_lines: Union[list, str]):
        if type(new_lines) is list:
            self.lines = new_lines
        else:
            self.lines.append(new_lines)

        self.show()

    def show(self):
        list_lines = self.lines
        if len(list_lines) > self.height - 2:
            list_lines = list_lines[len(list_lines)-self.height+2:]
        try:
            for idx, line in enumerate(list_lines):
                self.box.addstr(idx+1, 1, line)
        except Exception as ex:
            raise Exception(f"{str(list_lines)} {self.height} {str(len(list_lines))} {str(len(list_lines)-self.height-2)}")

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

class SendRequestsFront():
    logs_box: StrBox
    pbar_box: PBarBox
    send_box: StrBox
    stats_box: StrBox
    info_box: StrBox

    bash_width: int
    bash_height: int

    def __init__(self):
        self.update = True
        self.stdscr = None
        self.initialize()
        self.make_display()

    def initialize(self):
        self.stdscr = curses.initscr()
        self.bash_height, self.bash_width = self.stdscr.getmaxyx()
        curses.noecho()
        curses.curs_set(0)
        curses.cbreak()
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        self.stdscr.keypad(True)
        self.stdscr.clear()
        self.stdscr.refresh()

    def cleanup(self):
        self.update = False
        if self.stdscr:
            curses.nocbreak()
            self.stdscr.keypad(False)
            curses.echo()
            curses.curs_set(1)
            curses.endwin()

    async def auto_update(self):
        while self.update:
            self.make_display()
            await asyncio.sleep(0.1)
        
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
            "logs_box": StrBox(height=log_box_h, width=left_side, x=0, y=0, title="Logs"),
            "pbar_box": PBarBox(height=pbar_box_h, width=left_side, x=0, y=log_box_h, title="Progresso"),

            # Arquivos
            "send_box": StrBox(height=files_box_h, width=right_side, x=left_side, y=0, title="Service tasks"),

            # Subinfo
            "stats_box": StrBox(height=stats_box_h, width=right_sub, x=right_side+right_sub, y=files_box_h, title="Stats"),
            "info_box": StrBox(height=info_box_h, width=right_sub, x=right_side+(2*right_sub), y=files_box_h, title="Information")
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