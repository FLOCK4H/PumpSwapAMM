import readchar
class ColorCodes:
    # Standard Colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BLACK = "\033[30m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"

    # Bright Colors
    LIGHT_GREEN = "\033[92m"
    LIGHT_BLUE = "\033[94m"
    LIGHT_CYAN = "\033[96m"
    LIGHT_RED = "\033[91m"
    LIGHT_MAGENTA = "\033[95m"
    LIGHT_YELLOW = "\033[93m"
    LIGHT_WHITE = "\033[97m"
    LIGHT_BLACK = "\033[90m"

    # 256-Color Extended Colors
    ORANGE = "\033[38;5;208m"
    PURPLE = "\033[38;5;93m"
    DARK_GRAY = "\033[38;5;238m"
    LIGHT_GRAY = "\033[38;5;245m"
    PINK = "\033[38;5;213m"
    BROWN = "\033[38;5;130m"
    GOLD = "\033[38;5;178m"
    AQUA = "\033[38;5;87m"
    VIOLET = "\033[38;5;129m"

    # Background Colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    BG_ORANGE = "\033[48;5;208m"
    BG_PURPLE = "\033[48;5;93m"
    BG_PINK = "\033[48;5;213m"

    # Effects
    BRIGHT = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    REVERSE = "\033[7m"
    HIDDEN = "\033[8m"
    STRIKETHROUGH = "\033[9m"

    # Reset
    RESET = "\033[0m"
    RESET_BOLD = "\033[21m"
    RESET_UNDERLINE = "\033[24m"
    RESET_REVERSE = "\033[27m"
    
cc = ColorCodes()

def cprint(string, color=ColorCodes.BLUE):
    print(f'{ColorCodes.RESET}{ColorCodes.CYAN}[+]{ColorCodes.RESET}' + ' ' + f'{ColorCodes.BRIGHT}{color}{string}{ColorCodes.RESET}')

def wprint(string):
    print(f'{ColorCodes.WHITE}[+]{ColorCodes.RESET}' + ' ' + f'{ColorCodes.RED}{string}{ColorCodes.RESET}')

def iprint(string):
    print(f'{ColorCodes.BRIGHT}{ColorCodes.GREEN}[{ColorCodes.ORANGE}PumpSwapAMM{ColorCodes.GREEN}]{ColorCodes.RESET}' + ' ' + f'{ColorCodes.WHITE}{ColorCodes.BRIGHT}{string}{ColorCodes.BRIGHT}{ColorCodes.RESET} ')

def cinput(string, color=ColorCodes.CYAN, b=False, maxlen=None):
    try:
        if maxlen is None:
            r = input(f'{ColorCodes.GREEN}[>]{ColorCodes.RESET} {color}{ColorCodes.BRIGHT if b else color}{string}:{ColorCodes.RESET} ')
            return None if r == "" else r

        # Manual character collection mode
        print(f'{ColorCodes.GREEN}[>]{ColorCodes.RESET} {color}{ColorCodes.BRIGHT if b else color}{string}:{ColorCodes.RESET} ', end='', flush=True)
        buf = []
        while True:
            char = readchar.readchar()

            # Handle Enter manually if user presses it before maxlen
            if char in ('\r', '\n'):
                break

            # Handle backspace
            if char == '\x08' or char == '\x7f':
                if buf:
                    buf.pop()
                    print(f'\b \b', end='', flush=True)
                continue

            # Add valid char
            if len(char) == 1 and len(buf) < maxlen:
                buf.append(char)
                print(char, end='', flush=True)

            # Auto-submit if maxlen reached
            if maxlen is not None and len(buf) >= maxlen:
                break

        print()  # move to next line
        return ''.join(buf) if buf else None
    except EOFError:
        print("\n")
        exit(0)

def rinput(color=ColorCodes.CYAN):
    try:
        r = input(f'{ColorCodes.BRIGHT}{ColorCodes.PURPLE}[{ColorCodes.ORANGE}PumpSwapCLI{ColorCodes.PURPLE}]{ColorCodes.CYAN} > {ColorCodes.RESET}')
        return r
    except EOFError:
        print("\n")
        exit(0)