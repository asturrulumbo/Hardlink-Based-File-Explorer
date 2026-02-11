#!/usr/bin/env python3
"""Generate the Hardlink Manager instruction manual as a PDF."""

import os
from fpdf import FPDF

# ── Font paths ──────────────────────────────────────────────────────────────
FONT_DIR = "/usr/share/fonts/truetype/liberation"
MONO_DIR = "/usr/share/fonts/truetype/dejavu"

SERIF = os.path.join(FONT_DIR, "LiberationSerif-Regular.ttf")
SERIF_BOLD = os.path.join(FONT_DIR, "LiberationSerif-Bold.ttf")
SERIF_ITALIC = os.path.join(FONT_DIR, "LiberationSerif-Italic.ttf")
SERIF_BI = os.path.join(FONT_DIR, "LiberationSerif-BoldItalic.ttf")

SANS = os.path.join(FONT_DIR, "LiberationSans-Regular.ttf")
SANS_BOLD = os.path.join(FONT_DIR, "LiberationSans-Bold.ttf")
SANS_ITALIC = os.path.join(FONT_DIR, "LiberationSans-Italic.ttf")
SANS_BI = os.path.join(FONT_DIR, "LiberationSans-BoldItalic.ttf")

MONO = os.path.join(MONO_DIR, "DejaVuSansMono.ttf")
MONO_BOLD = os.path.join(MONO_DIR, "DejaVuSansMono-Bold.ttf")


class Manual(FPDF):
    """Custom PDF class for the Hardlink Manager instruction manual."""

    MARGIN = 20
    PAGE_W = 210  # A4
    CONTENT_W = 210 - 2 * 20  # 170

    def __init__(self):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=True, margin=25)
        self.set_margins(self.MARGIN, self.MARGIN, self.MARGIN)
        self._register_fonts()
        self.chapter_num = 0
        self.section_num = 0

    def _register_fonts(self):
        self.add_font("Serif", "", SERIF)
        self.add_font("Serif", "B", SERIF_BOLD)
        self.add_font("Serif", "I", SERIF_ITALIC)
        self.add_font("Serif", "BI", SERIF_BI)
        self.add_font("Sans", "", SANS)
        self.add_font("Sans", "B", SANS_BOLD)
        self.add_font("Sans", "I", SANS_ITALIC)
        self.add_font("Sans", "BI", SANS_BI)
        self.add_font("Mono", "", MONO)
        self.add_font("Mono", "B", MONO_BOLD)

    # ── Page chrome ─────────────────────────────────────────────────────────
    def header(self):
        if self.page_no() <= 2:
            return
        self.set_font("Sans", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "HardlinkManager.exe \u2014 Instruction Manual", align="L")
        self.cell(0, 8, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(180, 180, 180)
        self.line(self.MARGIN, self.get_y(), self.PAGE_W - self.MARGIN, self.get_y())
        self.ln(4)

    def footer(self):
        if self.page_no() <= 2:
            return
        self.set_y(-20)
        self.set_draw_color(180, 180, 180)
        self.line(self.MARGIN, self.get_y(), self.PAGE_W - self.MARGIN, self.get_y())
        self.ln(2)
        self.set_font("Sans", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, "Version 0.2.0", align="L")
        self.cell(0, 8, f"{self.page_no()}", align="R")

    # ── Building blocks ─────────────────────────────────────────────────────
    def _reset_text(self):
        self.set_text_color(30, 30, 30)

    def title_page(self):
        self.add_page()
        # ── Outer decorative border ──
        bm = 12  # border margin from page edge
        self.set_draw_color(80, 80, 80)
        self.set_line_width(0.6)
        self.rect(bm, bm, self.PAGE_W - 2 * bm, 297 - 2 * bm)
        self.set_line_width(0.2)
        self.rect(bm + 2, bm + 2, self.PAGE_W - 2 * bm - 4, 297 - 2 * bm - 4)
        self.set_line_width(0.2)  # reset

        # ── Top decorative rule ──
        self.ln(38)
        cx = self.PAGE_W / 2
        self.set_draw_color(100, 100, 100)
        self.set_line_width(0.4)
        self.line(cx - 50, self.get_y(), cx + 50, self.get_y())
        self.set_line_width(0.2)
        self.ln(12)

        # ── Title ──
        self.set_font("Sans", "B", 34)
        self._reset_text()
        self.cell(0, 18, "HardlinkManager.exe", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)

        # ── Subtitle ──
        self.set_font("Sans", "", 20)
        self.set_text_color(70, 70, 70)
        self.cell(0, 12, "Instruction Manual", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)

        # ── Central rule ──
        self.set_draw_color(140, 140, 140)
        self.line(cx - 35, self.get_y(), cx + 35, self.get_y())
        self.ln(10)

        # ── Version ──
        self.set_font("Sans", "I", 13)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, "Version 0.2.0", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(20)

        # ── Description ──
        self.set_font("Serif", "I", 11)
        self.set_text_color(80, 80, 80)
        self.multi_cell(
            0, 6.5,
            "A standalone Windows application for managing hardlink-based\n"
            "file indexing and synchronization across multiple directories.",
            align="C",
        )
        self.ln(6)
        self.set_font("Serif", "", 10)
        self.set_text_color(100, 100, 100)
        self.multi_cell(
            0, 5.5,
            "No installation required \u2014 run the executable directly.",
            align="C",
        )

        # ── Bottom decorative rule ──
        self.set_y(297 - bm - 30)
        self.set_draw_color(100, 100, 100)
        self.set_line_width(0.4)
        self.line(cx - 50, self.get_y(), cx + 50, self.get_y())
        self.set_line_width(0.2)

    def toc_page(self):
        self.add_page()
        self.set_font("Sans", "B", 22)
        self._reset_text()
        self.cell(0, 14, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
        self.ln(6)
        self.set_draw_color(60, 60, 60)
        self.line(self.MARGIN, self.get_y(), self.PAGE_W - self.MARGIN, self.get_y())
        self.ln(8)

    def toc_entry(self, level, text):
        if level == 1:
            self.set_font("Sans", "B", 11)
        else:
            self.set_font("Sans", "", 10)
            self.set_x(self.MARGIN + 8)
        self._reset_text()
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def chapter_title(self, title):
        self.chapter_num += 1
        self.section_num = 0
        self.add_page()
        self.set_font("Sans", "B", 22)
        self._reset_text()
        label = f"{self.chapter_num}. {title}"
        self.cell(0, 14, label, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)
        self.set_draw_color(60, 60, 60)
        self.line(self.MARGIN, self.get_y(), self.PAGE_W - self.MARGIN, self.get_y())
        self.ln(8)

    def section_title(self, title):
        self.section_num += 1
        self.ln(4)
        self.set_font("Sans", "B", 14)
        self._reset_text()
        label = f"{self.chapter_num}.{self.section_num}  {title}"
        self.cell(0, 10, label, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def subsection_title(self, title):
        self.ln(2)
        self.set_font("Sans", "B", 11)
        self._reset_text()
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body(self, text):
        self.set_font("Serif", "", 10.5)
        self._reset_text()
        self.multi_cell(0, 5.5, text, align="L")
        self.ln(2)

    def body_italic(self, text):
        self.set_font("Serif", "I", 10.5)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 5.5, text, align="L")
        self._reset_text()
        self.ln(2)

    def bullet(self, text, indent=6):
        self.set_font("Serif", "", 10.5)
        self._reset_text()
        self.cell(indent)
        bullet_w = 5
        self.cell(bullet_w, 5.5, "\u2022")
        self.multi_cell(self.CONTENT_W - indent - bullet_w, 5.5, text, align="L")
        self.ln(1)

    def numbered_item(self, num, text, indent=6):
        self.set_font("Serif", "", 10.5)
        self._reset_text()
        self.cell(indent)
        num_w = 8
        self.cell(num_w, 5.5, f"{num}.")
        self.multi_cell(self.CONTENT_W - indent - num_w, 5.5, text, align="L")
        self.ln(1)

    def code_block(self, text):
        self.ln(1)
        self.set_fill_color(240, 240, 240)
        self.set_draw_color(200, 200, 200)
        x0 = self.get_x()
        y0 = self.get_y()
        self.set_font("Mono", "", 9)
        self.set_text_color(40, 40, 40)
        lines = text.strip().split("\n")
        line_h = 5
        block_h = len(lines) * line_h + 6
        # Check page break
        if self.get_y() + block_h > self.h - 25:
            self.add_page()
            y0 = self.get_y()
        self.rect(x0, y0, self.CONTENT_W, block_h, style="FD")
        self.set_xy(x0 + 4, y0 + 3)
        for i, line in enumerate(lines):
            self.cell(0, line_h, line, new_x="LMARGIN", new_y="NEXT")
            if i < len(lines) - 1:
                self.set_x(x0 + 4)
        self.ln(4)
        self._reset_text()

    def note_box(self, text):
        self.ln(2)
        self.set_fill_color(255, 248, 220)
        self.set_draw_color(220, 200, 120)
        x0 = self.get_x()
        y0 = self.get_y()
        self.set_font("Sans", "B", 9)
        self._reset_text()
        # Pre-calculate height
        self.set_font("Serif", "", 10)
        line_h = 5.2
        # rough estimate: 80 chars per line
        est_lines = max(1, len(text) // 75 + text.count("\n") + 1)
        box_h = est_lines * line_h + 14
        if self.get_y() + box_h > self.h - 25:
            self.add_page()
            y0 = self.get_y()
        self.rect(x0, y0, self.CONTENT_W, box_h, style="FD")
        self.set_xy(x0 + 4, y0 + 3)
        self.set_font("Sans", "B", 9)
        self.cell(0, 5, "NOTE", new_x="LMARGIN", new_y="NEXT")
        self.set_x(x0 + 4)
        self.set_font("Serif", "", 10)
        self.multi_cell(self.CONTENT_W - 8, line_h, text, align="L")
        self.set_y(y0 + box_h + 2)
        self.ln(2)

    def separator(self):
        self.ln(4)
        cx = self.PAGE_W / 2
        self.set_draw_color(180, 180, 180)
        self.line(cx - 20, self.get_y(), cx + 20, self.get_y())
        self.ln(6)


def build_manual():
    pdf = Manual()

    # ═══════════════════════════════════════════════════════════════════════
    # TITLE PAGE
    # ═══════════════════════════════════════════════════════════════════════
    pdf.title_page()

    # ═══════════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ═══════════════════════════════════════════════════════════════════════
    pdf.toc_page()
    toc = [
        (1, "1.  Preface"),
        (2, "     Motivation"),
        (2, "     Potential Uses"),
        (2, "     About This Manual"),
        (1, "2.  Understanding Hardlinks"),
        (2, "     What Are Hardlinks?"),
        (2, "     Why Hardlinks?"),
        (2, "     Constraints and Limitations"),
        (1, "3.  Installation"),
        (2, "     System Requirements"),
        (2, "     Running the Executable"),
        (2, "     Building from Source (Advanced)"),
        (1, "4.  Getting Started"),
        (2, "     Launching HardlinkManager.exe"),
        (2, "     The Main Window"),
        (2, "     Navigating the Interface"),
        (1, "5.  File Browser"),
        (2, "     Directory Tree"),
        (2, "     File List and Tabs"),
        (2, "     File Operations"),
        (1, "6.  Hardlink Operations"),
        (2, "     Creating a Hardlink"),
        (2, "     Viewing Hardlinks"),
        (2, "     Deleting a Hardlink"),
        (1, "7.  Mirror Groups"),
        (2, "     Concept Overview"),
        (2, "     Creating a Mirror Group"),
        (2, "     Managing Mirror Groups"),
        (2, "     Automatic Synchronization"),
        (2, "     Scanning for Existing Mirrors"),
        (1, "8.  Intersection Search"),
        (2, "     Running a Search"),
        (2, "     Interpreting Results"),
        (1, "9.  Keyboard Shortcuts & Context Menus"),
        (1, "10. Configuration and Data Storage"),
        (1, "11. Example Workflows"),
        (2, "     Scholarly Archive with Multilingual Names"),
        (2, "     Thematic Cross-Referencing"),
        (2, "     Periodical with Alternate Titles"),
        (1, "12. Troubleshooting"),
        (1, "13. Appendix: Technical Reference"),
    ]
    for level, text in toc:
        pdf.toc_entry(level, text)

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 1 \u2014 PREFACE
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Preface")

    pdf.section_title("Motivation")
    pdf.body(
        "Managing large collections of documents\u2014whether scholarly archives, research "
        "libraries, media collections, or institutional records\u2014presents a persistent "
        "organizational challenge. A single document often belongs logically in multiple "
        "locations: a paper on Byzantine Christology might be filed under theology, under "
        "Byzantine history, and under the name of its author. Traditional file management "
        "forces a choice: store the file in one location, or duplicate it across several."
    )
    pdf.body(
        "Duplication wastes disk space and creates a synchronization nightmare. Edit one "
        "copy and the others become stale. Delete one and you may forget the others exist. "
        "Symbolic links and shortcuts offer partial relief, but they break when the original "
        "is moved, and many applications do not handle them gracefully."
    )
    pdf.body(
        "Hardlinks solve these problems at the filesystem level. A hardlink is not a pointer "
        "to a file\u2014it is the file, sharing the same underlying data on disk. Multiple "
        "hardlinks to the same file occupy disk space only once, remain valid even if other "
        "links are renamed or moved within the same volume, and are transparent to every "
        "application. The file simply appears to exist, fully and independently, in every "
        "location where a hardlink has been placed."
    )
    pdf.body(
        "Hardlink Manager was created to make these powerful filesystem capabilities accessible "
        "through a graphical interface. Rather than requiring users to invoke command-line "
        "utilities (such as mklink on Windows or ln on Unix), the application provides an "
        "intuitive way to create, manage, and discover hardlinks across directories. Its Mirror "
        "Group system extends this further, enabling automatic synchronization of entire folder "
        "sets\u2014so that a file added to any one mirror automatically appears in all the others."
    )
    pdf.body(
        "The project originated from the needs of a scholarly archive organized across three "
        "complementary indexing schemes: a primary catalogue (organized by format, language, "
        "and period), an onomasticon (a name index with entries in multiple scripts and "
        "transliterations), and a categoricum (a thematic index for cross-referential "
        "research). Maintaining consistency across these interrelated structures by hand proved "
        "unsustainable. Hardlink Manager was designed to automate and simplify this work."
    )

    pdf.section_title("Potential Uses")
    pdf.body("Hardlink Manager is suited to any scenario in which the same files must be organized under "
             "multiple classification schemes simultaneously without duplication:")
    pdf.bullet(
        "Scholarly and Research Archives \u2014 Maintain documents under multiple organizational "
        "hierarchies (by author, by subject, by date, by language) with a single copy of each file."
    )
    pdf.bullet(
        "Multilingual Collections \u2014 Provide access to the same materials under names in "
        "different scripts or transliterations (Greek, Latin, Cyrillic, Arabic, etc.)."
    )
    pdf.bullet(
        "Media Libraries \u2014 Organize music, photographs, or video files by multiple "
        "criteria (artist, album, genre, year) without multiplying storage usage."
    )
    pdf.bullet(
        "Institutional Records Management \u2014 File documents under departmental, "
        "chronological, and project-based hierarchies simultaneously."
    )
    pdf.bullet(
        "Software Development \u2014 Share configuration files, assets, or test fixtures "
        "across multiple project directories on the same volume."
    )
    pdf.bullet(
        "Personal Knowledge Management \u2014 Organize notes, papers, and references under "
        "overlapping topic trees without worrying about which copy is the canonical one."
    )
    pdf.body(
        "The intersection search feature is particularly valuable for cross-referential "
        "research, enabling the discovery of documents that span multiple thematic categories."
    )

    pdf.section_title("About This Manual")
    pdf.body(
        "This manual covers setup, core concepts, and practical usage of "
        "HardlinkManager.exe version 0.2.0. It is organized to be read sequentially by "
        "new users or consulted by section as a reference. Chapter 2 introduces the concept "
        "of hardlinks for readers unfamiliar with them. Chapters 3\u20134 cover running the "
        "executable and first launch. Chapters 5\u20138 describe the application's features "
        "in detail. Chapters 9\u201310 cover shortcuts and configuration. Chapter 11 provides "
        "worked examples, and Chapters 12\u201313 address troubleshooting and technical details."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 2 \u2014 UNDERSTANDING HARDLINKS
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Understanding Hardlinks")

    pdf.section_title("What Are Hardlinks?")
    pdf.body(
        "Every file on a modern filesystem is identified internally by an inode (on Unix/macOS) "
        "or a file index number (on Windows NTFS). The inode stores the file's actual data "
        "location, size, permissions, and other metadata. What we usually think of as a "
        "\"filename\" is really a directory entry that maps a human-readable name to an inode."
    )
    pdf.body(
        "A hardlink is simply an additional directory entry pointing to the same inode. "
        "Because multiple directory entries can reference the same inode, the same file can "
        "appear in multiple directories under different names\u2014or even under the same name "
        "in different locations. The operating system tracks how many directory entries (links) "
        "reference each inode; this is the \"link count.\""
    )
    pdf.body(
        "When you delete a file, you are actually removing one directory entry. The underlying "
        "data is only freed when the link count drops to zero\u2014that is, when no remaining "
        "directory entries refer to that inode. This means you can safely delete a hardlink "
        "from one location without affecting the file's availability at other locations."
    )

    pdf.section_title("Why Hardlinks?")
    pdf.bullet("Storage efficiency: Multiple appearances of a file consume disk space only once.")
    pdf.bullet("Transparency: Applications see a normal file at each path; no special handling needed.")
    pdf.bullet("Resilience: Renaming or deleting one link does not invalidate others.")
    pdf.bullet("Automatic content sync: Editing the file through any link edits the same data.")
    pdf.bullet("No dangling references: Unlike symbolic links, hardlinks cannot become \"broken.\"")

    pdf.section_title("Constraints and Limitations")
    pdf.bullet("Same volume only: Hardlinks can only be created between files on the same disk "
               "partition or volume. Cross-drive hardlinks are not possible.")
    pdf.bullet("Files only: Directories cannot be hardlinked. Mirror Groups work around this by "
               "synchronizing individual files within directories.")
    pdf.bullet("NTFS required (Windows): Hardlinks require an NTFS-formatted volume. FAT32 and "
               "exFAT do not support them.")
    pdf.bullet("Permissions: On some systems, creating hardlinks may require elevated privileges.")
    pdf.note_box(
        "Hardlink Manager validates volume compatibility before creating links and will "
        "alert you if a cross-volume operation is attempted."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 3 \u2014 INSTALLATION
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Installation")

    pdf.section_title("System Requirements")
    pdf.bullet("Operating system: Windows 10 or later (NTFS filesystem required)")
    pdf.bullet("No Python installation or additional dependencies needed")
    pdf.bullet("The executable is fully self-contained and portable")
    pdf.note_box(
        "Hardlinks require an NTFS-formatted volume. Drives formatted as FAT32 or "
        "exFAT do not support hardlinks. Most modern Windows system drives use NTFS by default."
    )

    pdf.section_title("Running the Executable")
    pdf.body(
        "HardlinkManager.exe is a standalone, portable application that requires no "
        "installation. To get started:"
    )
    pdf.numbered_item(1, "Place HardlinkManager.exe in any convenient location on your computer "
                         "(e.g., your Desktop, a Tools folder, or a USB drive).")
    pdf.numbered_item(2, "Double-click HardlinkManager.exe to launch the application.")
    pdf.body(
        "No installer, no setup wizard, no configuration files to create. The application "
        "stores its data (mirror group registrations) in the standard Windows application "
        "data directory; see Chapter 10 for details."
    )
    pdf.note_box(
        "On first launch, Windows SmartScreen may display a warning because the executable "
        "is not digitally signed. Click \"More info\" and then \"Run anyway\" to proceed."
    )

    pdf.section_title("Building from Source (Advanced)")
    pdf.body(
        "For developers or users who wish to modify the application, HardlinkManager.exe "
        "can be rebuilt from source. This requires Python 3.7 or later and PyInstaller:"
    )
    pdf.code_block(
        "git clone https://github.com/asturrulumbo/\n"
        "    Hardlink-Based-File-Explorer.git\n"
        "cd Hardlink-Based-File-Explorer\n"
        "pip install -r requirements.txt\n"
        "python build.py              # Single-file executable\n"
        "python build.py --onedir     # Directory bundle (faster startup)"
    )
    pdf.body(
        "The output is placed in the dist/ directory."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 4 \u2014 GETTING STARTED
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Getting Started")

    pdf.section_title("Launching HardlinkManager.exe")
    pdf.body(
        "Double-click HardlinkManager.exe to launch the application. The main window will "
        "appear after a brief loading period. No command-line arguments are required."
    )
    pdf.body(
        "You may wish to create a shortcut on your Desktop or pin the application to your "
        "taskbar for quick access. Right-click the executable and select the appropriate "
        "option from the Windows context menu."
    )

    pdf.section_title("The Main Window")
    pdf.body(
        "The main window is divided into two primary areas:"
    )
    pdf.bullet("Left panel: A hierarchical directory tree for navigating your filesystem.")
    pdf.bullet(
        "Right panel: A tabbed notebook with three tabs \u2014 File Browser, Mirror Groups, "
        "and Intersection Search."
    )
    pdf.body(
        "The File Browser tab displays the contents of selected directories in a tabbed "
        "interface, allowing multiple folders to be open simultaneously. The Mirror Groups tab "
        "provides tools for creating and managing synchronized folder sets. The Intersection "
        "Search tab enables multi-folder searches for shared files."
    )

    pdf.section_title("Navigating the Interface")
    pdf.bullet("Click a folder in the left tree to expand it and view its subdirectories.")
    pdf.bullet("Double-click a folder to open it in a new tab in the File Browser.")
    pdf.bullet("Right-click files or folders to access context menus with hardlink operations.")
    pdf.bullet("Use File > Add Folder to Tree to add root directories to the navigation tree.")
    pdf.bullet("The status bar at the bottom displays metadata for the selected item.")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 5 \u2014 FILE BROWSER
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("File Browser")

    pdf.section_title("Directory Tree")
    pdf.body(
        "The left-hand directory tree provides a hierarchical view of your filesystem. "
        "Directories are loaded lazily\u2014their contents are fetched only when you expand "
        "them\u2014which keeps the interface responsive even for deeply nested structures."
    )
    pdf.body(
        "To add a new root folder to the tree, use File > Add Folder to Tree from the menu "
        "bar. Multiple root folders can be active simultaneously."
    )

    pdf.section_title("File List and Tabs")
    pdf.body(
        "When you open a directory, its contents are displayed in the right-hand panel as a "
        "table with the following columns:"
    )
    pdf.bullet("Name \u2014 The file or subdirectory name.")
    pdf.bullet("Size \u2014 The file size in a human-readable format.")
    pdf.bullet("Hardlink Count \u2014 The number of hardlinks to the same underlying data.")
    pdf.bullet("Inode \u2014 The filesystem inode (or file index number on Windows).")
    pdf.body(
        "Multiple directories can be open in separate tabs. Click a tab to switch between "
        "open directories. Tabs can be closed individually."
    )

    pdf.section_title("File Operations")
    pdf.body("Standard file operations are accessible through the context menu (right-click) or keyboard shortcuts:")
    pdf.bullet("Open \u2014 Open the selected file with the system's default application.")
    pdf.bullet("Open in Explorer \u2014 Reveal the file in the operating system's file manager.")
    pdf.bullet("Copy / Cut / Paste \u2014 Standard clipboard operations for files and folders.")
    pdf.bullet("Rename \u2014 Rename the selected file or folder (F2).")
    pdf.bullet("Delete \u2014 Delete the selected item (Delete key).")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 6 \u2014 HARDLINK OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Hardlink Operations")

    pdf.section_title("Creating a Hardlink")
    pdf.body(
        "To create a hardlink to an existing file:"
    )
    pdf.numbered_item(1, "Right-click the source file in the File Browser.")
    pdf.numbered_item(2, "Select \"Create Hardlink To...\" from the context menu.")
    pdf.numbered_item(3, "In the dialog, browse to and select the destination folder.")
    pdf.numbered_item(4, "Optionally, specify a custom name for the new link. If left blank, "
                         "the original filename is used.")
    pdf.numbered_item(5, "Click OK to create the hardlink.")
    pdf.body(
        "The new hardlink will appear in the destination folder. It references the same "
        "underlying data as the source file; edits to either are reflected in both."
    )
    pdf.note_box(
        "Both the source file and destination folder must reside on the same filesystem "
        "volume. If they do not, the application will display an error."
    )

    pdf.section_title("Viewing Hardlinks")
    pdf.body(
        "To view all hardlinks to a given file:"
    )
    pdf.numbered_item(1, "Right-click the file in the File Browser.")
    pdf.numbered_item(2, "Select \"View Hardlinks\" from the context menu.")
    pdf.body(
        "A dialog will display every path on the system that shares the same inode as the "
        "selected file. Each path listed is a hardlink to the same underlying data. The dialog "
        "also shows the inode number and total link count. Clicking a path in the list "
        "navigates to that location in the File Browser."
    )

    pdf.section_title("Deleting a Hardlink")
    pdf.body(
        "To delete a hardlink:"
    )
    pdf.numbered_item(1, "Right-click the file and select \"Delete\" or press the Delete key.")
    pdf.numbered_item(2, "A confirmation dialog will appear.")
    pdf.body(
        "If the file has a link count greater than one (i.e., other hardlinks exist), the "
        "dialog will inform you that only this directory entry will be removed\u2014the "
        "underlying data remains accessible through the other links. If this is the last "
        "remaining link, the dialog warns that the data will be permanently deleted."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 7 \u2014 MIRROR GROUPS
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Mirror Groups")

    pdf.section_title("Concept Overview")
    pdf.body(
        "A Mirror Group is a set of two or more directories that are treated as equivalent "
        "mirrors of each other. All directories in a mirror group maintain identical file "
        "contents through hardlinks. When a file is added to any directory in the group, "
        "hardlinks to that file are automatically created in every other directory in the "
        "group (if automatic synchronization is enabled)."
    )
    pdf.body(
        "Mirror groups are useful when a single logical entity\u2014a person, a periodical, "
        "a theme\u2014has multiple representations in your file hierarchy (e.g., the same "
        "author filed under names in different scripts)."
    )
    pdf.body(
        "Each directory in a mirror group is marked with a hidden .hardlink_mirror file, "
        "which allows the application to recognize mirror membership across sessions."
    )

    pdf.section_title("Creating a Mirror Group")
    pdf.body("There are two ways to create a mirror group:")
    pdf.subsection_title("Method 1: From the Mirror Groups Panel")
    pdf.numbered_item(1, "Switch to the Mirror Groups tab in the right panel.")
    pdf.numbered_item(2, "Click the \"New Group\" button.")
    pdf.numbered_item(3, "In the dialog, add two or more directories to the group.")
    pdf.numbered_item(4, "Assign a name to the group (or accept the auto-generated name).")
    pdf.numbered_item(5, "Click OK. The group will be created and an initial synchronization "
                         "will run to ensure all directories share the same files.")

    pdf.subsection_title("Method 2: From the Context Menu")
    pdf.numbered_item(1, "Right-click a folder in the File Browser or directory tree.")
    pdf.numbered_item(2, "Select \"Create Hardlink Mirror...\" from the context menu.")
    pdf.numbered_item(3, "The selected folder will be pre-populated; add additional folders.")
    pdf.numbered_item(4, "Confirm to create the group.")

    pdf.section_title("Managing Mirror Groups")
    pdf.body("The Mirror Groups panel lists all registered groups with the following information:")
    pdf.bullet("Group name")
    pdf.bullet("Number of directories in the group")
    pdf.bullet("Synchronization status (enabled or disabled)")
    pdf.body("From this panel, you can:")
    pdf.bullet("Edit a group \u2014 Add or remove directories, rename the group.")
    pdf.bullet("Delete a group \u2014 Remove the group registration. The directories and "
               "their files are not affected; only the mirror relationship is dissolved.")
    pdf.bullet("Sync Now \u2014 Manually trigger a full synchronization of all directories "
               "in the group, ensuring they all contain the same files.")
    pdf.bullet("Toggle Sync \u2014 Enable or disable automatic filesystem watching for the group.")

    pdf.section_title("Automatic Synchronization")
    pdf.body(
        "When automatic synchronization is enabled for a mirror group, the application uses "
        "a filesystem watcher (powered by the watchdog library) to monitor all directories "
        "in the group for new file additions."
    )
    pdf.body(
        "When a new file is detected in any watched directory, the system waits briefly "
        "(0.5 seconds by default) to allow the file write to complete, then creates hardlinks "
        "to that file in every other directory in the group. The relative path within the "
        "directory is preserved, so subdirectory structures are maintained."
    )
    pdf.note_box(
        "The filesystem watcher runs in a background thread and is designed to be "
        "resource-efficient through debouncing. It can be toggled on or off per group."
    )

    pdf.section_title("Scanning for Existing Mirrors")
    pdf.body(
        "If you have directories that are already mirrors of each other (created manually or "
        "by another tool), the application can discover them automatically:"
    )
    pdf.subsection_title("Content-Based Scanning")
    pdf.body(
        "Computes SHA-256 fingerprints of directory contents and groups directories with "
        "identical content signatures. This detects mirrors regardless of how they were created."
    )
    pdf.subsection_title("Hardlink-Based Scanning")
    pdf.body(
        "Scans for directories that share files with the same inode numbers. Directories "
        "sharing any hardlinked files are proposed as a mirror group. Uses a union-find "
        "algorithm to transitively connect related directories."
    )
    pdf.body(
        "Both scanning methods are accessible from the Mirror Groups panel via the \"Scan for "
        "Mirrors\" button. Scan results are presented for review before any groups are created."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 8 \u2014 INTERSECTION SEARCH
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Intersection Search")

    pdf.section_title("Running a Search")
    pdf.body(
        "The Intersection Search feature finds files that appear in all of a specified set "
        "of directories. This is particularly useful for discovering documents that span "
        "multiple organizational categories."
    )
    pdf.numbered_item(1, "Switch to the Intersection Search tab.")
    pdf.numbered_item(2, "Add two or more directories to the search set using the folder selector.")
    pdf.numbered_item(3, "Optionally, enter a filename pattern to filter results (case-insensitive "
                         "substring matching).")
    pdf.numbered_item(4, "Click Search.")

    pdf.section_title("Interpreting Results")
    pdf.body("Results are displayed in a table with the following columns:")
    pdf.bullet("Filename \u2014 The name of the file found in all specified directories.")
    pdf.bullet("Size \u2014 The file size.")
    pdf.bullet("Inode \u2014 The inode number confirming the files are hardlinked (same data).")
    pdf.bullet("Locations \u2014 The full paths where the file was found.")
    pdf.body(
        "The search works by comparing inode numbers across directories, so it correctly "
        "identifies hardlinked files even if they have been renamed in different locations."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 9 \u2014 KEYBOARD SHORTCUTS & CONTEXT MENUS
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Keyboard Shortcuts & Context Menus")

    pdf.body("The following keyboard shortcuts are available throughout the application:")
    pdf.ln(2)

    # Simple table
    pdf.set_font("Sans", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    col1_w = 50
    col2_w = 120
    pdf.cell(col1_w, 7, "  Shortcut", fill=True)
    pdf.cell(col2_w, 7, "  Action", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Serif", "", 10)
    shortcuts = [
        ("Ctrl+C", "Copy selected item"),
        ("Ctrl+X", "Cut selected item"),
        ("Ctrl+V", "Paste"),
        ("Delete", "Delete selected item"),
        ("F2", "Rename selected item"),
        ("Right-click", "Open context menu"),
    ]
    for key, action in shortcuts:
        pdf.cell(col1_w, 6.5, f"  {key}")
        pdf.cell(col2_w, 6.5, f"  {action}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.body("Context menus provide the following additional actions depending on context:")
    pdf.subsection_title("File Context Menu")
    pdf.bullet("Open / Open in Explorer")
    pdf.bullet("Copy / Cut / Paste")
    pdf.bullet("Create Hardlink To...")
    pdf.bullet("View Hardlinks")
    pdf.bullet("Rename / Delete")
    pdf.subsection_title("Folder Context Menu")
    pdf.bullet("Open Folder / Open in New Tab / Open in Explorer")
    pdf.bullet("Copy / Cut / Paste")
    pdf.bullet("Create Hardlink Mirror...")
    pdf.bullet("Add to Existing Mirror...")
    pdf.bullet("View Hardlink Mirrors")
    pdf.bullet("Rename / Delete")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 10 \u2014 CONFIGURATION AND DATA STORAGE
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Configuration and Data Storage")

    pdf.body(
        "HardlinkManager.exe stores its persistent data (mirror group registrations) in "
        "the standard Windows application data directory:"
    )
    pdf.code_block("%APPDATA%\\HardlinkManager\\")
    pdf.body(
        "On a typical Windows installation this resolves to a path like "
        "C:\\Users\\YourName\\AppData\\Roaming\\HardlinkManager\\."
    )

    pdf.body(
        "The primary data file is mirror_groups.json, which stores all mirror group definitions "
        "including group IDs, names, folder paths, synchronization settings, and timestamps. "
        "This file is read on startup and updated automatically whenever groups are modified."
    )
    pdf.body(
        "Each directory belonging to a mirror group also contains a hidden .hardlink_mirror "
        "marker file. These markers enable the application to discover mirror memberships "
        "during scanning operations."
    )
    pdf.note_box(
        "Deleting the mirror_groups.json file will reset all group registrations. The marker "
        "files in individual directories will allow groups to be rediscovered via the scanning "
        "feature."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 11 \u2014 EXAMPLE WORKFLOWS
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Example Workflows")

    pdf.section_title("Scholarly Archive with Multilingual Names")
    pdf.body_italic(
        "Scenario: You maintain an archive of patristic scholarship. Authors are known by "
        "names in multiple scripts, and you want each variant accessible as a folder name."
    )
    pdf.numbered_item(1, "Create folders in your Onomasticum directory for each name variant: "
                         "John_of_Damascus/, Yuhanna_ad-Dimashqi/, etc.")
    pdf.numbered_item(2, "Right-click any one of these folders and select \"Create Hardlink Mirror...\"")
    pdf.numbered_item(3, "Add all variant folders to the new mirror group.")
    pdf.numbered_item(4, "Add a PDF to any one folder. With synchronization enabled, hardlinks "
                         "automatically appear in all other variant folders.")
    pdf.numbered_item(5, "Use Intersection Search to find documents present across both the "
                         "Onomasticum name folders and thematic Categoricum folders.")

    pdf.section_title("Thematic Cross-Referencing")
    pdf.body_italic(
        "Scenario: You have a thematic index (Categoricum) with categories like "
        "Theology/Christology and Literature/Theological_Poetry. You want to find "
        "documents relevant to both themes."
    )
    pdf.numbered_item(1, "Manually hardlink relevant documents into each thematic folder using "
                         "\"Create Hardlink To...\" from the context menu.")
    pdf.numbered_item(2, "Open the Intersection Search tab.")
    pdf.numbered_item(3, "Add both Theology/Christology and Literature/Theological_Poetry to "
                         "the search set.")
    pdf.numbered_item(4, "Click Search. The results show all documents that appear in both "
                         "categories\u2014your cross-referential overlap.")

    pdf.section_title("Periodical with Alternate Titles")
    pdf.body_italic(
        "Scenario: A Greek periodical from the 1920s is catalogued under both its Greek "
        "title and a Latin transliteration."
    )
    pdf.numbered_item(1, "Create both title folders under the appropriate catalogue path.")
    pdf.numbered_item(2, "Create a mirror group containing both folders.")
    pdf.numbered_item(3, "Add issues to either folder; they are automatically mirrored to the other.")
    pdf.numbered_item(4, "Researchers searching by either title will find the same complete collection.")

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 12 \u2014 TROUBLESHOOTING
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Troubleshooting")

    pdf.subsection_title("\"Cannot create hardlink: files are on different volumes\"")
    pdf.body(
        "Hardlinks require both the source and destination to be on the same filesystem "
        "volume. Ensure both paths are on the same drive or partition. Use the operating "
        "system's disk management tools to verify volume assignments."
    )

    pdf.subsection_title("\"Permission denied\" when creating hardlinks")
    pdf.body(
        "Creating hardlinks may require administrative privileges on some Windows "
        "configurations. Right-click HardlinkManager.exe and select \"Run as administrator\" "
        "to launch with elevated permissions."
    )

    pdf.subsection_title("Mirror group synchronization not working")
    pdf.body(
        "Verify that automatic synchronization is enabled for the group (check the toggle "
        "in the Mirror Groups panel). Ensure HardlinkManager.exe is running\u2014the "
        "filesystem watcher only operates while the application is active. If issues "
        "persist, try a manual \"Sync Now\" to diagnose any underlying errors."
    )

    pdf.subsection_title("Files appear with hardlink count of 1")
    pdf.body(
        "A hardlink count of 1 means only one directory entry references this file\u2014it "
        "has no additional hardlinks. This is the default state for any newly created file."
    )

    pdf.subsection_title("Scanning does not find expected mirrors")
    pdf.body(
        "Content-based scanning requires directories to have identical contents. If files "
        "have diverged, the scan will not match them. Try hardlink-based scanning instead, "
        "which detects any shared inodes. Also ensure the directories being scanned are on "
        "the same volume."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # CHAPTER 13 \u2014 APPENDIX: TECHNICAL REFERENCE
    # ═══════════════════════════════════════════════════════════════════════
    pdf.chapter_title("Appendix: Technical Reference")

    pdf.section_title("Architecture Overview")
    pdf.body("Hardlink Manager is organized into three layers:")
    pdf.bullet("Core (hardlink_manager/core/) \u2014 Business logic for hardlink operations, "
               "mirror groups, synchronization, filesystem watching, and search.")
    pdf.bullet("UI (hardlink_manager/ui/) \u2014 The tkinter-based graphical interface, including "
               "the main window, file browser, mirror panel, search panel, and modal dialogs.")
    pdf.bullet("Utilities (hardlink_manager/utils/) \u2014 Cross-platform filesystem helpers for "
               "inode queries, volume validation, and filename sanitization.")

    pdf.section_title("Core Modules")
    pdf.subsection_title("hardlink_ops.py")
    pdf.body("Provides create_hardlink(), delete_hardlink(), and find_hardlinks() functions. "
             "Validates same-volume constraints before operations.")
    pdf.subsection_title("mirror_groups.py")
    pdf.body("Implements MirrorGroupRegistry for persistent group management. Includes both "
             "content-based (SHA-256 fingerprinting) and hardlink-based (union-find) mirror "
             "discovery algorithms.")
    pdf.subsection_title("sync.py")
    pdf.body("Handles file synchronization across mirror group directories. Preserves relative "
             "path structure and creates intermediate directories as needed.")
    pdf.subsection_title("watcher.py")
    pdf.body("Filesystem event monitoring using the watchdog library. Implements debounced, "
             "thread-safe watching with per-group toggle support.")
    pdf.subsection_title("search.py")
    pdf.body("Inode-based intersection search across multiple directories with optional "
             "filename pattern filtering.")

    pdf.section_title("Data Formats")
    pdf.subsection_title("mirror_groups.json")
    pdf.code_block(
        '{\n'
        '  "groups": [\n'
        '    {\n'
        '      "id": "uuid-string",\n'
        '      "name": "Group Name",\n'
        '      "folders": ["/path/a", "/path/b"],\n'
        '      "sync_enabled": true,\n'
        '      "created_at": "ISO-8601 timestamp",\n'
        '      "modified_at": "ISO-8601 timestamp"\n'
        '    }\n'
        '  ]\n'
        '}'
    )

    pdf.section_title("Cross-Platform Considerations")
    pdf.bullet("Windows: Uses os.stat().st_ino for file index numbers. Requires NTFS. "
               "Filename sanitization strips Windows-forbidden characters.")
    pdf.bullet("macOS: Standard POSIX inode handling via os.stat(). HFS+ and APFS supported.")
    pdf.bullet("Linux: Standard POSIX inode + device ID. Works with ext4, XFS, Btrfs, and "
               "other common filesystems.")

    pdf.separator()
    pdf.ln(4)
    pdf.set_font("Serif", "I", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5.5,
                   "HardlinkManager.exe \u2014 Version 0.2.0",
                   align="C")

    # ── Output ──────────────────────────────────────────────────────────────
    out_path = os.path.join(os.path.dirname(__file__), "Hardlink_Manager_Instruction_Manual.pdf")
    pdf.output(out_path)
    print(f"PDF written to: {out_path}")


if __name__ == "__main__":
    build_manual()
