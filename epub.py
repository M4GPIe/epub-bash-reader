import zipfile
from bs4 import BeautifulSoup
from simple_term_menu import TerminalMenu
import readchar
import os, sys
import re
import textwrap
import shutil
import posixpath
import io
from PIL import Image


def is_valid_epub(epub_file:zipfile.ZipFile):
    files = epub_file.namelist()
        
    is_valid = files.count("mimetype")>0 and files.count("OEBPS/content.opf")

    return is_valid

def extract_toc(epub_file:zipfile.ZipFile):
    with epub_file.open("OEBPS/content.opf") as content_file:
        decoded_content_file = content_file.read().decode()
        
        content_soup = BeautifulSoup(decoded_content_file, "xml")
        
        spine_item = content_soup.find("spine")
        
        if spine_item == None:
            raise Exception("The content file has not a valid structure")
        
        toc = {}
        
        for itemref in spine_item.find_all("itemref"): # type: ignore
            item_id = itemref.get("idref")
            
            item = content_soup.find("item",id=item_id) if item_id != None else None
            
            file = item.get("href") if item != None else None # type: ignore
            
            if file == None:
                raise Exception("The content.opf file has not a valid format")
            
            toc[item_id] = f"OEBPS/{file}"
                
        return toc
    
def show_menu(toc: dict[str,str])->int:
    
    def get_content_label(key: str):
        filename = toc[key].split("/").pop()
        
        # additional x on itemId start is used as identation mark
        if key.replace(filename,"")=="x":
            return key.replace("x","    ",1).replace(".xhtml","")
        else: 
            return key.replace(".xhtml","")
    
    options = list(map(get_content_label,toc.keys()))
    
    terminal_menu = TerminalMenu(options,title="Epub contents")
    menu_entry_index = terminal_menu.show()
    
    return menu_entry_index # type: ignore
        
        
def resolve_epub_path(current_xhtml: str, src: str) -> str:
    base_dir = posixpath.dirname(current_xhtml)
    return posixpath.normpath(posixpath.join(base_dir, src))

def image_bytes_to_ascii(img_bytes: bytes, width: int = 70) -> str:
    img = Image.open(io.BytesIO(img_bytes)).convert("L")  # escala grises
    w, h = img.size
    aspect = h / w
    new_h = max(1, int(aspect * width * 0.55))  # 0.55 corrige proporción terminal

    img = img.resize((width, new_h))
    pixels = list(img.getdata()) # type: ignore

    charset = " .:-=+*#%@"
    chars = [charset[p * (len(charset) - 1) // 255] for p in pixels]

    lines = ["".join(chars[i:i+width]) for i in range(0, len(chars), width)]
    return "\n".join(lines)

def xhtml_to_console_text_with_images(xhtml: str, epub_file: zipfile.ZipFile, current_file: str) -> str:
    soup = BeautifulSoup(xhtml, "html.parser")

    for tag in soup(["script", "style", "head", "title", "meta", "link"]):
        tag.decompose()

    for img in soup.find_all("img"):
        alt = img.get("alt") or "Imagen"
        src = img.get("src") or ""

        try:
            img_path = resolve_epub_path(current_file, src) # type: ignore
            with epub_file.open(img_path) as f:
                ascii_art = image_bytes_to_ascii(f.read(), width=70)

            img.replace_with(f"\n[🖼 {alt}]\n{ascii_art}\n")
        except Exception:
            img.replace_with(f"\n[🖼 {alt} | {src}]\n")

    # Saltos de línea reales
    for br in soup.find_all("br"):
        br.replace_with("\n")

    # Bloques: párrafos y títulos
    block_tags = ["p", "div", "section", "article", "blockquote"]
    for t in soup.find_all(block_tags):
        t.insert_before("\n")
        t.insert_after("\n")

    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        h.insert_before("\n\n")
        h.insert_after("\n\n")

    # Listas: li como bullets
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
        li.insert_after("\n")

    # Sacamos texto
    text = soup.get_text()

    # Normalizar espacios (sin cargarnos los saltos de línea)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # Ajustar al ancho de terminal
    width = shutil.get_terminal_size((100, 20)).columns

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    wrapped = [textwrap.fill(p, width=width, replace_whitespace=False) for p in paragraphs]

    return "\n\n".join(wrapped)

        
def show_chapter(epub_file: zipfile.ZipFile,selected_file):
    with epub_file.open(selected_file) as file:
        decoded_content_file = file.read().decode()
        
        clear = lambda: os.system('clear')
        clear()
        
        formatted = xhtml_to_console_text_with_images(decoded_content_file, epub_file, selected_file)
        print(formatted)
        
        return readchar.readkey()
    
if __name__ == "__main__":
    
    arguments = list(sys.argv)
    
    help_option = arguments.count("-h") > 0 
    
    if(help_option):
        print("Type -f <epub_path> to open Epub")
        exit()
    
    file = arguments[arguments.index("-f")+1]
    
    try:
        with zipfile.ZipFile(file) as epub_file:
        
            if not is_valid_epub(epub_file):
                print("The given epub is not valid")
                
            toc = extract_toc(epub_file)
        
            panic = False
            menu = True
            selected_file = None
            
            while(True):
                if(menu):
                    option = show_menu(toc)
                    
                    selected_file = list(toc.values())[option]
                    menu = False
                else:
                    key = show_chapter(epub_file,selected_file)
                    if(key == readchar.key.BACKSPACE):
                        menu = True
                    elif(key == readchar.key.SPACE):
                        break
                    elif(key == readchar.key.LEFT):
                        selected_file_index = list(toc.values()).index(selected_file)
                        if(selected_file_index>0):
                            selected_file = list(toc.values())[selected_file_index-1]
                    elif(key == readchar.key.RIGHT):
                        selected_file_index = list(toc.values()).index(selected_file)
                        if(selected_file_index<len(list(toc.values()))-1):
                            selected_file = list(toc.values())[selected_file_index+1]
            
    except Exception as e:
        print("The given epub is not valid")
        print(e)