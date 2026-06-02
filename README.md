# CodeHaven - Smart Tags Code Manager

A powerful, lightweight code snippet manager built with Python and Bottle. Organize, tag, execute, and manage your code snippets with an elegant web interface.

![CodeHaven Screenshot](./ch.jpg)

## Features

- **Smart Tags System** - Create unlimited custom color-coded tags, autocomplete suggestions, filter by tags
- **Categories** - Organize snippets into custom categories
- **ZIP File Attachments** - Attach and download ZIP files with your code snippets
- **Python Code Execution** - Run Python code directly from the browser with safety checks
- **Syntax Highlighting** - 7 themes including Monokai, Dracula, Nord, GitHub, VS2015, Atom One Dark
- **Backup & Restore** - Full database and ZIP backup with `.chb` format
- **Statistics Dashboard** - Visual charts for languages, categories, activity timeline
- **Dark/Light Mode** - Toggle between themes with persistence
- **Mobile Responsive** - Works on all screen sizes
- **Pro Editor** - Built-in ACE editor with font controls
- **Font Size Controls** - Adjust code display size

## Requirements

- Python 3.7+
- `bottle` - Web framework
- Standard library: `sqlite3`, `zipfile`, `shutil`, `subprocess`, `tempfile`, `uuid`, `json`

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/codehaven.git
cd codehaven

# Install dependencies
pip install bottle

# Run the application
python codehaven.py
```

The app will start at `http://localhost:8080`

## Usage

1. **Add Code** - Click "Add Code" to create new snippets with tags and optional ZIP attachments
2. **Organize** - Use categories and tags to keep everything organized
3. **Execute** - Run Python code directly (with 5-second timeout and security checks)
4. **Backup** - Regularly backup your data using the backup button
5. **Tags** - Manage tags from the sidebar or tag manager modal

## Database

CodeHaven uses SQLite (`codehaven.db`) with the following tables:
- `categories` - Code categories
- `codes` - Code snippets with metadata
- `tags` - Custom tags with colors
- `code_tags` - Many-to-many relationship

## File Structure

```
codehaven/
├── codehaven.py      # Main application
├── codehaven.db      # SQLite database (auto-created)
├── zipcode/          # ZIP attachments directory
├── backups/          # Backup files
└── execution_temp/   # Temporary execution files
```

## Security

- Python execution is sandboxed with 5-second timeout
- Dangerous imports (`os.system`, `subprocess`, `eval`, `exec`, etc.) are blocked
- Code runs in isolated temporary files

## Credits

- **highlight.js** - Syntax highlighting
- **Font Awesome** - Icons
- **Bottle Framework** - Python web framework
- **Chart.js** - Statistics charts
- **ACE Editor** - Pro code editor

## Author

Developed by **Husam Doughmosch**

- GitHub: [@Hdoughmosch](https://github.com/Hdoughmosch)
- LinkedIn: [Husam Doughmosch](https://www.linkedin.com/in/husam-doughmosch-085568407)
- Twitter/X: [@HDoughmosch](https://x.com/HDoughmosch)

---

2026 CodeHaven - Open Source Project
