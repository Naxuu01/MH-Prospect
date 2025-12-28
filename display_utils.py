"""
Utilitaires d'affichage pour améliorer le rendu visuel dans la console.
"""
import textwrap
from typing import Optional, List, Any


class Colors:
    """Codes ANSI pour les couleurs (fonctionnent sur la plupart des terminaux)."""
    # Styles
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Couleurs texte
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Couleurs fond
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'


def print_header(title: str, width: int = 90, color: str = Colors.CYAN):
    """Affiche un en-tête simple et épuré."""
    print()
    print(f"{color}{Colors.BOLD}▶ {title}{Colors.RESET}")
    print(f"{color}{'─' * min(len(title) + 4, width)}{Colors.RESET}")


def print_section(title: str, width: int = 90, icon: str = "", color: str = Colors.BLUE):
    """Affiche une section simple."""
    if icon:
        print(f"\n{color}{icon} {title}{Colors.RESET}")
    else:
        print(f"\n{color}{title}{Colors.RESET}")


def print_box(content: str, title: Optional[str] = None, width: int = 90, 
              border_color: str = Colors.CYAN, title_color: str = Colors.BOLD + Colors.WHITE):
    """Affiche un contenu formaté de manière simple."""
    # Gérer les valeurs None ou vides
    if content is None:
        content = "N/A"
    elif not isinstance(content, str):
        content = str(content) if content is not None else "N/A"
    
    if not content or (isinstance(content, str) and len(content.strip()) == 0):
        content = "N/A"
    
    if title:
        print(f"\n{border_color}▶ {title}{Colors.RESET}")
    lines = textwrap.wrap(content, width=width - 4)
    for line in lines:
        print(f"  {line}")


def print_info(label: str, value: Any, icon: str = "", width: int = 90, 
               label_color: str = Colors.CYAN, value_color: str = Colors.WHITE):
    """Affiche une information formatée de manière simple."""
    # Gérer les valeurs None ou vides
    if value is None:
        value = "N/A"
    elif not isinstance(value, str):
        value = str(value) if value is not None else "N/A"
    
    # S'assurer que value est une chaîne non vide
    if not value or (isinstance(value, str) and len(value) == 0):
        value = "N/A"
    
    if icon:
        label_display = f"{icon} {label}"
    else:
        label_display = label
    
    # Couper la valeur si trop longue
    max_value_len = width - len(label_display) - 10
    if len(value) > max_value_len:
        value = value[:max_value_len - 3] + "..."
    
    print(f"  {label_color}{label_display}{Colors.RESET}: {value_color}{value}{Colors.RESET}")


def print_success(message: str, icon: str = "✅"):
    """Affiche un message de succès."""
    print(f"{Colors.GREEN}{Colors.BOLD}{icon} {message}{Colors.RESET}")


def print_warning(message: str, icon: str = "⚠️"):
    """Affiche un message d'avertissement."""
    print(f"{Colors.YELLOW}{Colors.BOLD}{icon} {message}{Colors.RESET}")


def print_error(message: str, icon: str = "❌"):
    """Affiche un message d'erreur."""
    print(f"{Colors.RED}{Colors.BOLD}{icon} {message}{Colors.RESET}")


def print_separator(width: int = 90, style: str = "─", color: str = Colors.DIM + Colors.WHITE):
    """Affiche un séparateur simple."""
    print(f"{color}{style * min(40, width)}{Colors.RESET}")


def print_two_column(left: str, right: str, width: int = 90, 
                     left_color: str = Colors.CYAN, right_color: str = Colors.WHITE):
    """Affiche deux colonnes côte à côte."""
    left_len = len(left)
    right_len = len(right)
    available_space = width - left_len - right_len - 4
    if available_space < 2:
        # Pas assez d'espace, afficher sur deux lignes
        print(f"  {left_color}{left}{Colors.RESET}")
        print(f"  {right_color}{right}{Colors.RESET}")
    else:
        spacing = " " * available_space
        print(f"  {left_color}{left}{Colors.RESET}{spacing}{right_color}{right}{Colors.RESET}")


def wrap_text(text: str, width: int = 80, indent: int = 2) -> List[str]:
    """Enveloppe le texte avec indentation."""
    # Gérer les valeurs None ou vides
    if text is None:
        text = "N/A"
    elif not isinstance(text, str):
        text = str(text) if text is not None else "N/A"
    
    if not text or (isinstance(text, str) and len(text.strip()) == 0):
        text = "N/A"
    
    wrapper = textwrap.TextWrapper(width=width, initial_indent=" " * indent, 
                                   subsequent_indent=" " * indent)
    return wrapper.wrap(text)

