# Unified Hardlink Manager System
## Comprehensive Project Specification

---

## System Overview

A Windows hardlink-based file indexing system built on a **single unified architecture** that supports flexible organizational schemas. The system is agnostic about how it's deployed — the same functionality applies everywhere.

The system is designed to manage scholarly archives organized by:
- **Cataloguing** — Primary archive with strict organizational hierarchy (format → language → time period)
- **Onomasticum** — Name index for equivalent entities across different scripts/transliterations
- **Categoricum** — Thematic index for cross-referential organization

However, the **underlying operations and capabilities are identical across all three**. Distinctions are organizational/semantic, not functional.

---

## Core Concepts

### Mirror Groups

A **mirror group** represents a single logical entity (a periodical, a historical figure, a thematic category, etc.) that exists in multiple physical folder locations under different names, all kept in sync.

**Key behaviors:**
- When a file is added to any folder in a mirror group, hardlinks are automatically created in all other folders
- When a file is deleted from any folder, the user is notified: "This file exists in [list of all folders in the mirror group]. Remove from which folders?"
- All folders in a mirror group maintain identical file contents (via hardlinks)
- Mirror groups are optional — folders can also exist independently without grouping

### Hardlinks

Hardlinks are references to the same underlying file data:
- Multiple hardlinks to one file means the file appears in multiple locations but occupies disk space only once
- Files with the same inode (Windows "file index number") are hardlinks to the same data
- Deleting one hardlink does not delete the data if other hardlinks exist

### Intersection Search

Multi-folder search that finds files appearing in multiple specified locations:
- User specifies 2+ folders (anywhere in the system)
- System returns files that appear in the intersection of those folders
- Works regardless of whether folders are in mirror groups or independent

---

## Archive Structures & Examples

### Cataloguing (Primary Archive)

**Hierarchical organization:**
```
Cataloguing/
├── [Format]/
│   ├── [Language]/
│   │   ├── [Time Period]/
│   │   │   └── [Files]
│   │   └── [Alphabetical for periodicals]/
│   │       └── [Files]
```

**Example use of mirror groups in Cataloguing:**
- A Greek periodical with both a Greek title and Latin transliteration:
  - `Cataloguing/Periodicals/Greek/1920s/Ἑλληνικά/` (mirror group member)
  - `Cataloguing/Periodicals/Greek/1920s/Hellenika/` (mirror group member)
  - Both folders are in the same mirror group; files added to either are hardlinked to the other

---

### Onomasticum (Name Index)

**Structure:**
```
Onomasticum/
├── [Entity Name - Script Variant 1]/
├── [Entity Name - Script Variant 2]/
├── [Entity Name - Script Variant 3]/
└── etc.
```

**Example:**
```
Onomasticum/
├── John_of_Damascus/          (English/Latin transliteration)
├── Иоанн_Дамаскин/            (Cyrillic)
├── Yuhanna_ad-Dimashqi/       (Arabic transliteration)
├── Ἰωάννης_ὁ_Δαμασκηνός/     (Greek)
```

**Mirror group use:**
- All four folders are in a single mirror group representing "John of Damascus"
- When a file about John is added to any variant folder, hardlinks automatically appear in all others
- User can access John's materials via any script/transliteration variant

---

### Categoricum (Thematic Index)

**Structure:**
```
Categoricum/
├── [Theme]/
│   ├── [Subtheme]/
│   │   └── [Files - hardlinks]
```

**Example:**
```
Categoricum/
├── Theology/
│   ├── Christology/
│   ├── Ecclesiology/
│   └── Eschatology/
├── History/
│   ├── Byzantine_Intellectual_History/
│   └── Medieval_Christianity/
├── Literature/
│   ├── Theological_Poetry/
│   └── Liturgical_Texts/
```

**How mirror groups can be used in Categoricum:**
- Typically, Categoricum folders are **independent** (no mirror groups)
- Files are manually hardlinked to relevant thematic folders
- But mirror groups *could* be created if thematic categories have alternate names/organizations

**Intersection search in Categoricum:**
- User searches: "Find files in BOTH Theology/Christology AND Literature/Theological_Poetry"
- System returns documents relevant to multiple research themes
- This works whether or not the folders are in mirror groups

---

## Core Unified Functionality

All folders and mirror groups use the same operations, regardless of archive type:

### Basic Operations
- **Create hardlinks** — User specifies source file and destination folder
- **Delete hardlinks** — Remove a hardlink from a folder (with deletion notification if in mirror group)
- **View hardlinks** — Show which files share the same inode
- **Browse folders** — Navigate and manage folder structure

### Mirror Group Operations
- **Create mirror groups** — Define multiple folders as equivalent representations of a single entity
- **Add folders to mirror groups** — Add existing folders to a group
- **Remove folders from mirror groups** — Remove folder from group
- **View mirror group contents** — See all folders in a group and their file inventory

### Automatic Synchronization (Optional per Mirror Group)
- **Filesystem watching** — Monitor folders in the group for additions
- **Automatic hardlink creation** — When file added to any folder in group, hardlinks created in all others
- **Deletion notifications** — When file deleted from any folder, notify user of all mirrors and prompt for deletion scope

### Search Operations
- **Multi-folder intersection search** — Find files appearing in 2+ specified folders
- **Filter by filename** — Restrict results by pattern matching
- **View inode information** — Display file index numbers and path details

---

## User Interface Requirements

### Main Window
- Tree view or sidebar showing the three archive sections (Cataloguing, Onomasticum, Categoricum)
- File browser panel showing folder contents
- Status bar showing relevant information

### Mirror Group Management Panel
- List of existing mirror groups
- Buttons to create/edit/delete mirror groups
- Dialog for specifying folders to group together
- Display current sync status

### Search/Intersection Panel
- Multi-folder selector for intersection search
- Display matching files with paths and inodes
- Filter/sort options

### Context Menu (Right-Click)
- "Create Hardlink To..." → select destination folder
- "View Hardlinks" → show all folders containing this hardlink
- "Delete Hardlink" → remove this hardlink
- "Add Folder to Mirror Group" → assign folder to a group (with notifications about sync)
- For mirror groups: "View Mirror Group Contents" → see all folders in the group

### Deletion Confirmation Dialog
- **For folders in a mirror group:** "This file exists in [Folder A, Folder B, Folder C]. Remove from all folders?" with Yes/No buttons
  - "Yes" removes the hardlink from all folders in the group
  - "No" cancels the deletion
- **For independent folders (not in mirror group):** Standard file deletion confirmation

---

## Technical Constraints & Considerations

### Windows Hardlinks
- **Directory Hardlinks:** Windows does not permit hardlinks to directories. Only files can be hardlinked.
  - Consequence: Mirror groups must manage individual file hardlinks, not directory hardlinks
  - When a folder is added to a mirror group, individual files within it get hardlinked to corresponding folders in other mirrors
  
- **Inode Equivalence:** Files with the same inode are hardlinks to the same underlying data
  - Windows calls this the "file index number" (can be queried via Win32 API)
  
- **Same-Volume Requirement:** Hardlinks only work on the same NTFS volume
  - Do not attempt to hardlink files across different drives
  
- **Permissions:** User must have appropriate filesystem permissions to create hardlinks

### Persistence
- Mirror group registry should be stored persistently (JSON file in app directory is acceptable)
- Format: List of groups, each containing folder paths and creation/modification timestamps

### Performance
- Filesystem watcher can be resource-intensive; consider debouncing
- Large folder scans (for intersection search) may take time; consider progress indication

---

## Development Phases

### Phase 1: Foundation (Manual Operations)
**Scope:**
- Manual hardlink creation/deletion/viewing
- Multi-folder intersection search
- Basic file/folder browser UI
- No filesystem watchers
- No mirror group state tracking

**Deliverable:**
- Working application for manual hardlink management and searching across any folders

---

### Phase 2: Mirror Group Management
**Scope:**
- Mirror group creation and management
- Filesystem watcher for automatic syncing (toggleable per group)
- Deletion notification system
- Mirror group registry (persistent storage)
- UI for managing groups

**Deliverable:**
- Complete system with optional automatic synchronization (works identically everywhere)

---

### Phase 3: Polish & Advanced Features
**Scope:**
- Enhanced filtering/sorting in search results
- Batch operations (create multiple hardlinks at once)
- Mirror group statistics and visualization
- Configuration options (debounce delays, watching behavior)

**Deliverable:**
- Production-ready hardlink manager with flexible configuration

---

## Example Workflows (Unified Functionality)

### Creating a Catalogued Item with Alternate Names

1. User navigates to `Cataloguing/Periodicals/Greek/1920s/`
2. Adds a PDF file: `Ἑλληνικά_1920.pdf`
3. Creates a mirror group containing:
   - `Cataloguing/Periodicals/Greek/1920s/Ἑλληνικά`
   - `Cataloguing/Periodicals/Greek/1920s/Hellenika`
4. System automatically hardlinks the PDF to both folders
5. Future additions to either folder are auto-mirrored (same functionality, same interface, anywhere)

### Creating an Onomasticum Entry

1. User creates mirror group in `Onomasticum/`:
   - `John_of_Damascus/`
   - `Иоанн_Дамаскин/`
   - `Ἰωάννης_ὁ_Δαμασκηνός/`
   - `Yuhanna_ad-Dimashqi/`
2. User adds PDF to `John_of_Damascus/`
3. System automatically creates hardlinks in all other variant folders
4. (Identical functionality to Cataloguing example)

### Thematic Cross-Referencing in Categoricum

1. User manually hardlinks relevant documents to `Categoricum/Theology/Christology/`
2. User manually hardlinks same documents to `Categoricum/Literature/Theological_Poetry/`
3. (Option A) These folders remain independent — no mirror group
4. (Option B) User creates mirror group if preferred for sync
5. User searches: "Find files in BOTH Theology/Christology AND Literature/Theological_Poetry"
6. System returns documents relevant to both research areas
7. (Same search functionality works anywhere in system)

### Ad-Hoc Thematic Organization

1. User discovers documents relevant to multiple themes
2. Creates temporary mirror groups or manual hardlinks
3. Uses intersection search to validate coverage
4. System applies same operations consistently across all use cases

---

## Notes for Development

- Start with Phase 1; it's genuinely simple and provides immediate value
- Phase 2 adds real power but requires filesystem watcher understanding
- Phase 3 is relatively straightforward once Phase 2 is complete
- Consider using C# WPF or WinForms for the UI (good integration with Windows APIs)
- Python with tkinter is an alternative if preferred
- Test thoroughly with the inode/file index number queries — this is the linchpin of the system
