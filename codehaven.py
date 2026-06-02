#!/usr/bin/env python3


import sys
import os

# CRITICAL FIX FOR PYINSTALLER - Makes subprocess work
if getattr(sys, 'freeze', False) or getattr(sys, 'frozen', False):
    # Running as compiled EXE
    import subprocess
    # Make sure temp directory exists
    if not os.path.exists('execution_temp'):
        os.makedirs('execution_temp')


import sqlite3
import zipfile

import shutil
import subprocess
import tempfile
import uuid
from bottle import route, run, request, response
import traceback
import json

# Database setup - Fixed (no DROP TABLE)
conn = sqlite3.connect('codehaven.db')  # Changed database name
c = conn.cursor()

# Only create tables if they don't exist
c.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        title TEXT,
        code TEXT,
        language TEXT,
        zip_filename TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    )
''')

# Create tags table for flexible tagging system
c.execute('''
    CREATE TABLE IF NOT EXISTS tags (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        color TEXT,
        usage_count INTEGER DEFAULT 0
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS code_tags (
        code_id INTEGER,
        tag_id INTEGER,
        FOREIGN KEY (code_id) REFERENCES codes(id) ON DELETE CASCADE,
        FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (code_id, tag_id)
    )
''')

# Insert default categories only if they don't exist
c.execute("INSERT OR IGNORE INTO categories (name) VALUES ('Python')")
c.execute("INSERT OR IGNORE INTO categories (name) VALUES ('JavaScript')")
c.execute("INSERT OR IGNORE INTO categories (name) VALUES ('Other')")

# Add zip_filename column if it doesn't exist (for existing databases)
try:
    c.execute("ALTER TABLE codes ADD COLUMN zip_filename TEXT")
except sqlite3.OperationalError:
    pass  # Column already exists

# Add created_at column if it doesn't exist
try:
    c.execute("ALTER TABLE codes ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
except sqlite3.OperationalError:
    pass  # Column already exists

# Add color column to tags if not exists
try:
    c.execute("ALTER TABLE tags ADD COLUMN color TEXT")
except sqlite3.OperationalError:
    pass

conn.commit()
conn.close()

print("CodeHaven database initialized successfully! (Existing data preserved)")

# Create zipcode directory if it doesn't exist
ZIP_DIR = 'zipcode'
if not os.path.exists(ZIP_DIR):
    os.makedirs(ZIP_DIR)
    print(f" Created directory: {ZIP_DIR}")

# Create backup directory
BACKUP_DIR = 'backups'
if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)
    print(f" Created backup directory: {BACKUP_DIR}")

# Safe execution directory
EXEC_DIR = 'execution_temp'
try:
    abs_exec_dir = os.path.abspath(EXEC_DIR)
    if not os.path.exists(abs_exec_dir):
        os.makedirs(abs_exec_dir)
        print(f" Created execution directory: {abs_exec_dir}")
    else:
        print(f" Execution directory exists: {abs_exec_dir}")
except Exception as e:
    print(f" Error creating execution directory: {e}")

@route('/')
def index():
    return '''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=yes">
<title>CodeHaven - Smart Tags Code Manager</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

<!-- Multiple Highlight.js Themes -->
<link id="highlight-theme" rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/default.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>

<!-- Additional Languages -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/sql.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/bash.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/json.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/html.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/languages/css.min.js"></script>

<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:10px;transition:all 0.3s}
.container{max-width:1400px;margin:0 auto;background:white;border-radius:10px;overflow:hidden;box-shadow:0 10px 40px rgba(0,0,0,0.1)}

/* Header */
.header{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:15px 20px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap}
.header h1{font-size:1.5em}
.header h1 i{font-size:1.2em;margin-right:10px}

/* Controls */
.controls{display:flex;gap:10px;flex-wrap:wrap}
.controls button{background:rgba(255,255,255,0.2);color:white;border:none;padding:8px 15px;border-radius:5px;cursor:pointer;transition:all 0.3s}
.controls button:hover{background:rgba(255,255,255,0.3);transform:translateY(-2px)}

/* Theme dropdown */
.theme-selector{padding:8px;border-radius:5px;border:none;background:white;color:#333;cursor:pointer}

/* Menu button */
.menu-btn{display:none;background:white;color:#667eea;border:none;padding:8px 15px;border-radius:5px;cursor:pointer}

/* Sidebar */
.sidebar{width:280px;background:#f8f9fa;padding:20px;float:left;min-height:600px;transition:all 0.3s;box-shadow:2px 0 5px rgba(0,0,0,0.05)}
.content{padding:20px;margin-left:280px;transition:all 0.3s}

/* Tags styling */
.tags-container{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.tag{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:0.85em;cursor:pointer;transition:all 0.2s}
.tag:hover{transform:translateY(-2px);box-shadow:0 2px 8px rgba(0,0,0,0.15)}
.tag i{font-size:0.9em}
.tag-filter{background:#e9ecef;color:#495057}
.tag-filter.active{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white}
.tag-input-container{position:relative}
.tag-input{width:100%;padding:10px;border:2px solid #e9ecef;border-radius:8px;font-size:14px}
.tag-suggestions{position:absolute;top:100%;left:0;right:0;background:white;border:1px solid #ddd;border-radius:8px;max-height:200px;overflow-y:auto;z-index:10000;display:none;box-shadow:0 4px 12px rgba(0,0,0,0.15)}
.tag-suggestion{padding:8px 12px;cursor:pointer;display:flex;justify-content:space-between;align-items:center}
.tag-suggestion:hover{background:#f0f0f0}
.tag-badge{display:inline-flex;align-items:center;gap:5px;padding:2px 8px;border-radius:15px;font-size:0.8em}
.selected-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.selected-tag{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;font-size:0.85em}
.selected-tag .remove-tag{cursor:pointer;margin-left:5px;opacity:0.7}
.selected-tag .remove-tag:hover{opacity:1}
.tag-manager-btn{background:#6c757d;color:white;padding:5px 10px;font-size:12px;margin-left:10px}
.tag-manager-btn:hover{background:#5a6268}
.popular-tags{display:flex;flex-wrap:wrap;gap:8px;margin-top:15px;padding:10px;background:#f8f9fa;border-radius:8px}
.popular-tags-label{font-size:0.8em;color:#6c757d;margin-right:5px}

/* Tag Manager Modal - FIXED higher z-index */
.tag-manager-modal .modal-content{max-width:600px}
.tag-list{max-height:400px;overflow-y:auto}
.tag-item{display:flex;justify-content:space-between;align-items:center;padding:10px;border-bottom:1px solid #e9ecef}
.tag-item-info{display:flex;align-items:center;gap:10px}
.tag-color-preview{width:30px;height:30px;border-radius:5px;cursor:pointer}
.tag-name{font-weight:bold}
.tag-count{color:#6c757d;font-size:0.85em}
.tag-actions button{background:none;border:none;cursor:pointer;margin-left:10px;padding:5px}
.tag-actions .edit-tag{color:#007bff}
.tag-actions .delete-tag{color:#dc3545}
.add-tag-form{display:flex;gap:10px;margin-bottom:20px;padding-bottom:20px;border-bottom:2px solid #e9ecef}
.color-picker{width:50px;height:40px;border:2px solid #e9ecef;border-radius:8px;cursor:pointer}

/* Category items */
.cat-item{padding:12px;margin:8px 0;cursor:pointer;background:white;border-radius:8px;display:flex;justify-content:space-between;align-items:center;transition:all 0.3s;box-shadow:0 1px 3px rgba(0,0,0,0.1)}
.cat-item:hover{transform:translateX(5px);box-shadow:0 3px 6px rgba(0,0,0,0.15)}
.cat-item.active{background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white}
.delete-cat{color:#dc3545;cursor:pointer;padding:0 5px;font-size:1.2em}
.delete-cat:hover{transform:scale(1.2);display:inline-block}

/* Code cards */
.card{background:white;border-radius:10px;margin-bottom:20px;overflow:hidden;box-shadow:0 2px 5px rgba(0,0,0,0.1);transition:all 0.3s}
.card:hover{box-shadow:0 5px 15px rgba(0,0,0,0.2);transform:translateY(-2px)}
.card-header{background:#f8f9fa;padding:15px;border-bottom:2px solid #e9ecef}
.card-title{font-size:1.2em;font-weight:bold;color:#333;margin-bottom:5px}
.card-meta{display:flex;gap:15px;font-size:0.85em;color:#6c757d;flex-wrap:wrap;align-items:center}
.card-meta i{margin-right:5px}
.card-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:5px}
.code-container{position:relative;background:#f8f9fa}
.code-container pre{margin:0;padding:20px;overflow-x:auto;font-size:14px;border-radius:0}
.copy-btn{position:absolute;top:10px;right:10px;background:rgba(0,0,0,0.7);color:white;border:none;padding:8px 12px;border-radius:5px;cursor:pointer;transition:all 0.3s;font-size:12px}
.copy-btn:hover{background:#28a745;transform:scale(1.05)}
.card-actions{padding:10px 15px;background:#f8f9fa;display:flex;gap:10px;border-top:1px solid #e9ecef}
.card-actions button{flex:1;padding:8px;border:none;border-radius:5px;cursor:pointer;transition:all 0.3s}
.edit-btn{background:#007bff;color:white}
.edit-btn:hover{background:#0056b3}
.delete-btn{background:#dc3545;color:white}
.delete-btn:hover{background:#c82333}
.download-zip-btn{background:#ff9800;color:white}
.download-zip-btn:hover{background:#f57c00}
.execute-btn{background:#4caf50;color:white}
.execute-btn:hover{background:#45a049}

/* Forms */
input,select,textarea{padding:10px;margin:5px 0;width:100%;border:2px solid #e9ecef;border-radius:8px;font-size:16px;transition:all 0.3s}
input:focus,select:focus,textarea:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,0.1)}
button{padding:10px 20px;margin:5px;cursor:pointer;border:none;border-radius:8px;font-size:14px;transition:all 0.3s}
button:active{transform:scale(0.98)}

/* Modal - FIXED z-index */
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.6);z-index:10000;overflow-y:auto}
.modal-content{background:white;width:90%;max-width:700px;margin:50px auto;padding:25px;border-radius:15px;animation:slideIn 0.3s;position:relative;z-index:10001}
@keyframes slideIn{from{transform:translateY(-50px);opacity:0}to{transform:translateY(0);opacity:1}}

/* Progress Modal */
.progress-modal .modal-content{max-width:500px}
.progress-bar-container{width:100%;background:#e9ecef;border-radius:10px;overflow:hidden;margin:20px 0}
.progress-bar{width:0%;height:30px;background:linear-gradient(90deg,#667eea 0%,#764ba2 100%);transition:width 0.3s;display:flex;align-items:center;justify-content:center;color:white;font-weight:bold}
.progress-status{text-align:center;margin-top:10px;color:#666}
.progress-details{font-size:12px;margin-top:5px}

/* Confirmation Modal */
.confirm-modal .modal-content{max-width:450px;text-align:center}
.confirm-modal .confirm-icon{font-size:64px;margin-bottom:20px}
.confirm-modal .confirm-icon.warning{color:#ff9800}
.confirm-modal .confirm-icon.danger{color:#dc3545}
.confirm-modal .confirm-icon.info{color:#2196f3}
.confirm-modal h3{font-size:24px;margin-bottom:15px}
.confirm-modal p{margin-bottom:25px;color:#666;line-height:1.5}
.confirm-buttons{display:flex;gap:15px;justify-content:center}
.confirm-buttons button{padding:10px 25px;margin:0;border-radius:8px;font-weight:bold}
.confirm-cancel{background:#6c757d;color:white}
.confirm-cancel:hover{background:#5a6268}
.confirm-ok{background:#dc3545;color:white}
.confirm-ok:hover{background:#c82333}
.confirm-ok.success{background:#28a745}
.confirm-ok.success:hover{background:#218838}

/* Execution Modal */
.execution-modal .modal-content{max-width:900px}
.execution-output{background:#1e1e1e;color:#fff;padding:20px;border-radius:8px;font-family:'Courier New',monospace;max-height:500px;overflow-y:auto;margin-top:15px}
.execution-output pre{margin:0;white-space:pre-wrap;word-wrap:break-word}
.execution-error{color:#ff6b6b}
.execution-success{color:#51cf66}
.execution-loading{text-align:center;padding:20px}

/* About Modal */
.about-modal .modal-content{max-width:600px}
.about-content{text-align:center;padding:20px}
.dev-info{margin:20px 0;padding:20px;background:linear-gradient(135deg,#667eea20 0%,#764ba220 100%);border-radius:10px}
.social-links{display:flex;gap:15px;justify-content:center;margin-top:20px;flex-wrap:wrap}
.social-btn{display:inline-flex;align-items:center;gap:10px;padding:12px 20px;border-radius:8px;text-decoration:none;color:white;transition:transform 0.3s}
.social-btn:hover{transform:translateY(-3px)}
.linkedin{background:#0077b5}
.twitter{background:#1da1f2}
.github{background:#333}
.credits{background:#f8f9fa;padding:15px;border-radius:8px;margin-top:20px;font-size:0.9em}
.credits a{color:#667eea;text-decoration:none}
.credits a:hover{text-decoration:underline}

/* Stats Dashboard */
.stats-dashboard{margin-top:20px;padding:15px;background:linear-gradient(135deg,#667eea20 0%,#764ba220 100%);border-radius:10px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:15px;margin-top:15px}
.stat-card{background:white;padding:15px;border-radius:8px;text-align:center;box-shadow:0 2px 5px rgba(0,0,0,0.1)}
.stat-card i{font-size:2em;color:#667eea;margin-bottom:10px}
.stat-number{font-size:1.8em;font-weight:bold;color:#333}
.stat-label{font-size:0.85em;color:#6c757d;margin-top:5px}
.charts-container{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px;margin-top:20px}
.chart-box{background:white;padding:15px;border-radius:8px;box-shadow:0 2px 5px rgba(0,0,0,0.1)}
.chart-box h4{margin-bottom:15px;color:#333}
canvas{max-height:300px}

/* Backup/Restore Buttons */
.backup-btn{background:#17a2b8;color:white}
.backup-btn:hover{background:#138496}
.restore-btn{background:#6c757d;color:white}
.restore-btn:hover{background:#5a6268}
.stats-btn{background:#ff6b6b;color:white}
.stats-btn:hover{background:#ff5252}

/* Pagination */
.pagination{display:flex;justify-content:center;flex-wrap:wrap;gap:10px;margin-top:30px}
.pagination button{padding:10px 20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border:none;border-radius:8px;cursor:pointer;transition:all 0.3s}
.pagination button:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 3px 10px rgba(0,0,0,0.2)}
.pagination button:disabled{opacity:0.5;cursor:not-allowed}
.pagination span{padding:10px 15px;background:#f8f9fa;border-radius:8px}

/* Stats */
.stats{margin-top:20px;padding:12px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;border-radius:8px;text-align:center;font-weight:bold}

/* Toast notification */
.toast{position:fixed;bottom:20px;right:20px;background:#28a745;color:white;padding:12px 20px;border-radius:8px;display:none;z-index:20000;animation:slideInRight 0.3s}
@keyframes slideInRight{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
.toast.error{background:#dc3545}
.toast.info{background:#17a2b8}
.toast.warning{background:#ffc107;color:#333}

/* Mobile responsive */
@media (max-width: 768px) {
    .menu-btn{display:block}
    .sidebar{display:none;width:100%;float:none;position:fixed;top:0;left:0;height:100%;z-index:9999;overflow-y:auto;box-shadow:2px 0 10px rgba(0,0,0,0.3)}
    .sidebar.show{display:block}
    .content{margin-left:0;padding:10px}
    .card-title{font-size:1em}
    .code-container pre{font-size:12px;padding:15px}
    .copy-btn{top:5px;right:5px;padding:5px 10px}
    .controls button{padding:6px 12px;font-size:12px}
}

/* Dark theme */
body.dark-theme{background:#1a1a1a}
body.dark-theme .container{background:#2d2d2d}
body.dark-theme .sidebar{background:#1e1e1e}
body.dark-theme .cat-item{background:#333;color:#ddd}
body.dark-theme .card{background:#333}
body.dark-theme .card-header{background:#2d2d2d;border-bottom-color:#444}
body.dark-theme .card-title{color:#fff}
body.dark-theme .card-meta{color:#aaa}
body.dark-theme .card-actions{background:#2d2d2d;border-top-color:#444}
body.dark-theme input,body.dark-theme select,body.dark-theme textarea{background:#333;color:#fff;border-color:#555}
body.dark-theme .modal-content{background:#2d2d2d;color:#fff}
body.dark-theme .execution-output{background:#000}
body.dark-theme .credits{background:#333;color:#fff}
body.dark-theme .progress-bar-container{background:#444}
body.dark-theme .confirm-modal p{color:#aaa}
body.dark-theme .stat-card{background:#2d2d2d;color:#fff}
body.dark-theme .stat-number{color:#fff}
body.dark-theme .chart-box{background:#2d2d2d}
body.dark-theme .chart-box h4{color:#fff}
body.dark-theme .tag{background:#444;color:#fff}
body.dark-theme .popular-tags{background:#333}
body.dark-theme .tag-suggestions{background:#2d2d2d;border-color:#555}
body.dark-theme .tag-suggestion:hover{background:#444}

/* Language badges (kept for compatibility) */
.lang-badge{display:inline-block;padding:3px 8px;background:#e9ecef;border-radius:5px;font-size:0.75em;font-weight:bold}
.lang-badge.python{background:#3776AB;color:white}
.lang-badge.javascript{background:#F7DF1E;color:#333}
.lang-badge.html{background:#E34F26;color:white}
.lang-badge.sql{background:#4479A1;color:white}
.lang-badge.bash{background:#4EAA25;color:white}

/* ZIP file styling */
.zip-info{background:#e3f2fd;padding:8px;border-radius:5px;margin-top:5px;font-size:0.85em}
.zip-info i{color:#ff9800;margin-right:5px}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1><i class="fas fa-tags"></i> CodeHaven - Smart Tags</h1>
<div class="controls">
<select id="themeSelector" class="theme-selector">
<option value="default"> Default Theme</option>
<option value="github"> GitHub</option>
<option value="monokai"> Monokai</option>
<option value="atom-one-dark"> Atom One Dark</option>
<option value="vs2015"> VS2015</option>
<option value="dracula"> Dracula</option>
<option value="nord"> Nord</option>
</select>
<button id="fontPlus"><i class="fas fa-plus"></i> A+</button>
<button id="fontMinus"><i class="fas fa-minus"></i> A-</button>
<button id="themeBtn"><i class="fas fa-moon"></i> Dark</button>
<button id="statsBtn" class="stats-btn"><i class="fas fa-chart-bar"></i> Stats</button>
<button id="backupBtn" class="backup-btn"><i class="fas fa-database"></i> Backup</button>
<button id="restoreBtn" class="restore-btn"><i class="fas fa-upload"></i> Restore</button>
<button id="aboutBtn"><i class="fas fa-info-circle"></i> About</button>
<button id="menuBtn" class="menu-btn"><i class="fas fa-bars"></i> Menu</button>
</div>
</div>

<div class="sidebar" id="sidebar">
<h3><i class="fas fa-folder"></i> Categories</h3>
<div id="categories"></div>
<input type="text" id="newCat" placeholder="New category name">
<button id="addCatBtn"><i class="fas fa-plus"></i> Add Category</button>

<h3 style="margin-top:20px"><i class="fas fa-tags"></i> Popular Tags</h3>
<div id="popularTags" class="popular-tags"></div>

<!-- Manage Tags Button in Sidebar -->
<button id="manageTagsSidebarBtn" style="margin-top:15px;width:100%;background:#6c757d;color:white"><i class="fas fa-cog"></i> Manage All Tags</button>

<div id="stats" class="stats"></div>
</div>

<div class="content">
<div style="margin-bottom:20px">
<div class="search-bar" style="display:flex;gap:10px;flex-wrap:wrap">
<input type="text" id="search" placeholder=" Search codes by title, content, or tags..." style="flex:1">
<button id="addCodeBtn" style="background:#28a745;color:white"><i class="fas fa-plus"></i> Add Code</button>
</div>
<div id="tagFilters" class="tags-container" style="margin-top:10px"></div>
</div>
<div id="codes"></div>
<div id="pagination"></div>
</div>
</div>

<!-- Tag Manager Modal -->
<div id="tagManagerModal" class="modal tag-manager-modal">
<div class="modal-content">
<h2><i class="fas fa-tags"></i> Manage Tags</h2>
<div class="add-tag-form">
<input type="text" id="newTagName" placeholder="New tag name (e.g., React, Django, API)" style="flex:1">
<input type="color" id="newTagColor" class="color-picker" value="#667eea">
<button id="addTagBtn" style="background:#28a745;color:white"><i class="fas fa-plus"></i> Add</button>
</div>
<div id="tagList" class="tag-list"></div>
<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
<button id="closeTagManagerBtn" style="background:#6c757d;color:white"><i class="fas fa-times"></i> Close</button>
</div>
</div>
</div>

<!-- Statistics Dashboard Modal -->
<div id="statsModal" class="modal">
<div class="modal-content" style="max-width:900px">
<h2><i class="fas fa-chart-line"></i> CodeHaven Statistics Dashboard</h2>
<div id="statsDashboard" class="stats-dashboard">
<div class="stats-grid" id="statsGrid"></div>
<div class="charts-container">
<div class="chart-box">
<h4><i class="fas fa-chart-pie"></i> Codes by Language</h4>
<canvas id="langChart"></canvas>
</div>
<div class="chart-box">
<h4><i class="fas fa-chart-bar"></i> Top Categories</h4>
<canvas id="categoryChart"></canvas>
</div>
</div>
<div class="charts-container">
<div class="chart-box">
<h4><i class="fas fa-chart-line"></i> Activity Timeline</h4>
<canvas id="timelineChart"></canvas>
</div>
<div class="chart-box">
<h4><i class="fas fa-chart-donut"></i> ZIP Attachments</h4>
<canvas id="zipChart"></canvas>
</div>
</div>
</div>
<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
<button id="closeStatsBtn" style="background:#667eea;color:white"><i class="fas fa-times"></i> Close</button>
</div>
</div>
</div>

<div id="modal" class="modal">
<div class="modal-content">
<h2 id="modalTitle"><i class="fas fa-code"></i> Add Code Snippet</h2>
<input type="hidden" id="codeId">
<select id="catSelect">
<option value=""> Select Category</option>
</select>
<input type="text" id="title" placeholder="Code title...">
<select id="language">
<option value="python"> Python  (Executable)</option>
<option value="not-python"> Not Python  (No Execution)</option>
</select>

<!-- Smart Tags Input -->
<div class="tag-input-container">
<label style="display:block;margin-bottom:5px;font-weight:bold"><i class="fas fa-tags"></i> Tags (press Enter or comma to add)</label>
<input type="text" id="tagInput" class="tag-input" placeholder="Type tag name and press Enter...">
<div id="tagSuggestions" class="tag-suggestions"></div>
<div id="selectedTags" class="selected-tags"></div>
<!-- Manage Tags button removed from here -->
</div>

<textarea id="codeContent" rows="8" placeholder="Paste your code here..."></textarea>

<!-- ZIP File Upload Section -->
<div style="margin-top:15px;padding:10px;background:#f8f9fa;border-radius:8px;">
<label style="display:block;margin-bottom:5px;font-weight:bold"><i class="fas fa-file-archive"></i> Attach ZIP File (Optional)</label>
<input type="file" id="zipFile" accept=".zip" style="margin-bottom:5px">
<small style="color:#6c757d">Upload a ZIP file to associate with this code snippet</small>
<div id="currentZipInfo" style="display:none;margin-top:5px;padding:5px;background:#e3f2fd;border-radius:5px">
<i class="fas fa-paperclip"></i> Current: <span id="currentZipName"></span>
<button type="button" id="removeZipBtn" style="background:#dc3545;color:white;padding:2px 8px;font-size:12px;margin-left:10px">Remove</button>
</div>
</div>

<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:15px">
<button id="cancelBtn" style="background:#6c757d;color:white">Cancel</button>
<button id="saveBtn" style="background:#28a745;color:white"><i class="fas fa-save"></i> Save</button>
</div>
</div>
</div>

<!-- Progress Modal for Backup/Restore -->
<div id="progressModal" class="modal progress-modal">
<div class="modal-content">
<h2 id="progressTitle"><i class="fas fa-spinner fa-spin"></i> Processing...</h2>
<div class="progress-bar-container">
<div id="progressBar" class="progress-bar">0%</div>
</div>
<div id="progressStatus" class="progress-status">Initializing...</div>
<div id="progressDetails" class="progress-details"></div>
<div style="display:flex;gap:10px;justify-content:center;margin-top:20px">
<button id="closeProgressBtn" style="background:#6c757d;color:white;display:none"><i class="fas fa-times"></i> Close</button>
</div>
</div>
</div>

<!-- Confirmation Modal -->
<div id="confirmModal" class="modal confirm-modal">
<div class="modal-content">
<div class="confirm-icon" id="confirmIcon"><i class="fas fa-exclamation-triangle"></i></div>
<h3 id="confirmTitle">Confirm Action</h3>
<p id="confirmMessage">Are you sure you want to proceed?</p>
<div class="confirm-buttons">
<button id="confirmCancelBtn" class="confirm-cancel"><i class="fas fa-times"></i> Cancel</button>
<button id="confirmOkBtn" class="confirm-ok"><i class="fas fa-check"></i> Confirm</button>
</div>
</div>
</div>

<!-- Execution Result Modal -->
<div id="executionModal" class="modal execution-modal">
<div class="modal-content">
<h2><i class="fas fa-play-circle"></i> Code Execution Result</h2>
<div id="executionOutput" class="execution-output">
<div class="execution-loading">
<i class="fas fa-spinner fa-spin"></i> Executing code...
</div>
</div>
<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:15px">
<button id="closeExecBtn" style="background:#6c757d;color:white"><i class="fas fa-times"></i> Close</button>
</div>
</div>
</div>

<!-- About Modal -->
<div id="aboutModal" class="modal about-modal">
<div class="modal-content">
<h2><i class="fas fa-heart"></i> About CodeHaven</h2>
<div class="about-content">
<div class="dev-info">
<i class="fas fa-code" style="font-size:48px;color:#667eea"></i>
<h3>Developed by <strong style="color:#667eea">Husam Doughmosch</strong></h3>
<p>Passionate Developer & Code Enthusiast</p>
<div class="social-links">
<a href="https://github.com/Hdoughmosch" target="_blank" class="social-btn github">
<i class="fab fa-github"></i> GitHub
</a>
<a href="https://www.linkedin.com/in/husam-doughmosch-085568407" target="_blank" class="social-btn linkedin">
<i class="fab fa-linkedin"></i> LinkedIn
</a>
<a href="https://x.com/HDoughmosch" target="_blank" class="social-btn twitter">
<i class="fab fa-twitter"></i> Twitter/X
</a>
</div>
</div>
<div class="credits">
<p><i class="fas fa-copyright"></i> 2026 CodeHaven - Open Source Project</p>
<p><strong>Open Source Credits:</strong></p>
<p> <strong>highlight.js</strong> - Syntax highlighting library<br>
 <strong>Font Awesome</strong> - Icons<br>
 <strong>Bottle Framework</strong> - Python Web Framework<br>
 <strong>SQLite</strong> - Database Engine<br>
 <strong>Chart.js</strong> - Statistics Charts</p>
</div>
</div>
<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:15px">
<button id="closeAboutBtn" style="background:#667eea;color:white"><i class="fas fa-times"></i> Close</button>
</div>
</div>
</div>

<div id="toast" class="toast"></div>

<script>
let currentCat = 'all';
let currentTag = null;
let currentPage = 1;
let fontSize = 14;
let pendingConfirmAction = null;
let langChart, categoryChart, timelineChart, zipChart;
let allTags = [];
let selectedTagIds = [];

// DOM elements
const fontPlus = document.getElementById('fontPlus');
const fontMinus = document.getElementById('fontMinus');
const themeBtn = document.getElementById('themeBtn');
const themeSelector = document.getElementById('themeSelector');
const aboutBtn = document.getElementById('aboutBtn');
const backupBtn = document.getElementById('backupBtn');
const restoreBtn = document.getElementById('restoreBtn');
const statsBtn = document.getElementById('statsBtn');
const menuBtn = document.getElementById('menuBtn');
const sidebar = document.getElementById('sidebar');
const addCatBtn = document.getElementById('addCatBtn');
const addCodeBtn = document.getElementById('addCodeBtn');
const saveBtn = document.getElementById('saveBtn');
const cancelBtn = document.getElementById('cancelBtn');
const searchInput = document.getElementById('search');
const zipFileInput = document.getElementById('zipFile');
const removeZipBtn = document.getElementById('removeZipBtn');
const currentZipInfo = document.getElementById('currentZipInfo');
const currentZipName = document.getElementById('currentZipName');
const executionModal = document.getElementById('executionModal');
const executionOutput = document.getElementById('executionOutput');
const closeExecBtn = document.getElementById('closeExecBtn');
const aboutModal = document.getElementById('aboutModal');
const closeAboutBtn = document.getElementById('closeAboutBtn');
const statsModal = document.getElementById('statsModal');
const closeStatsBtn = document.getElementById('closeStatsBtn');
const tagManagerModal = document.getElementById('tagManagerModal');
const closeTagManagerBtn = document.getElementById('closeTagManagerBtn');
const manageTagsSidebarBtn = document.getElementById('manageTagsSidebarBtn');
const addTagBtn = document.getElementById('addTagBtn');
const newTagName = document.getElementById('newTagName');
const newTagColor = document.getElementById('newTagColor');
const tagInput = document.getElementById('tagInput');
const tagSuggestions = document.getElementById('tagSuggestions');
const selectedTagsDiv = document.getElementById('selectedTags');
const confirmModal = document.getElementById('confirmModal');
const confirmCancelBtn = document.getElementById('confirmCancelBtn');
const confirmOkBtn = document.getElementById('confirmOkBtn');
const confirmIcon = document.getElementById('confirmIcon');
const confirmTitle = document.getElementById('confirmTitle');
const confirmMessage = document.getElementById('confirmMessage');
const progressModal = document.getElementById('progressModal');
const progressBar = document.getElementById('progressBar');
const progressStatus = document.getElementById('progressStatus');
const progressDetails = document.getElementById('progressDetails');
const progressTitle = document.getElementById('progressTitle');
const closeProgressBtn = document.getElementById('closeProgressBtn');

let currentZipFilename = null;

// Syntax highlighting themes
const themes = {
    'default': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/default.min.css',
    'github': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github.min.css',
    'monokai': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/monokai.min.css',
    'atom-one-dark': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/atom-one-dark.min.css',
    'vs2015': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/vs2015.min.css',
    'dracula': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/dracula.min.css',
    'nord': 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/nord.min.css'
};

// Load all tags
async function loadTags() {
    try {
        let res = await fetch('/api/tags');
        let data = await res.json();
        allTags = data.tags;
        return allTags;
    } catch(e) {
        console.error('Error loading tags:', e);
        return [];
    }
}

// Load popular tags for sidebar
async function loadPopularTags() {
    try {
        let res = await fetch('/api/tags/popular');
        let data = await res.json();
        let html = '';
        for(let tag of data.tags) {
            let color = tag.color || '#667eea';
            html += `<div class="tag tag-filter" data-tag-id="${tag.id}" style="background:${color};color:white;cursor:pointer">
                <i class="fas fa-tag"></i> ${escapeHtml(tag.name)} (${tag.usage_count})
            </div>`;
        }
        document.getElementById('popularTags').innerHTML = html || '<div style="color:#999">No tags yet. Add some!</div>';
        
        document.querySelectorAll('#popularTags .tag').forEach(el => {
            el.onclick = () => filterByTag(el.dataset.tagId);
        });
    } catch(e) { console.error(e); }
}

// Filter by tag
function filterByTag(tagId) {
    currentTag = currentTag === tagId ? null : tagId;
    currentPage = 1;
    loadTagFilters();
    loadCodes();
}

// Load tag filter chips
async function loadTagFilters() {
    try {
        let res = await fetch('/api/tags');
        let data = await res.json();
        let html = '<div class="tag tag-filter ' + (!currentTag ? 'active' : '') + '" data-tag-id="all"><i class="fas fa-list"></i> All Tags</div>';
        for(let tag of data.tags) {
            let active = currentTag == tag.id ? 'active' : '';
            let color = tag.color || '#667eea';
            html += `<div class="tag tag-filter ${active}" data-tag-id="${tag.id}" style="background:${color};color:white;cursor:pointer">
                <i class="fas fa-tag"></i> ${escapeHtml(tag.name)}
            </div>`;
        }
        document.getElementById('tagFilters').innerHTML = html;
        
        document.querySelectorAll('#tagFilters .tag').forEach(el => {
            el.onclick = () => {
                if(el.dataset.tagId === 'all') {
                    currentTag = null;
                } else {
                    filterByTag(el.dataset.tagId);
                }
                loadTagFilters();
                loadCodes();
            };
        });
    } catch(e) { console.error(e); }
}

// Update selected tags display
function updateSelectedTagsDisplay() {
    let html = '';
    for(let tagId of selectedTagIds) {
        let tag = allTags.find(t => t.id == tagId);
        if(tag) {
            let color = tag.color || '#667eea';
            html += `<div class="selected-tag" style="background:${color};color:white">
                <i class="fas fa-tag"></i> ${escapeHtml(tag.name)}
                <span class="remove-tag" data-id="${tag.id}"><i class="fas fa-times-circle"></i></span>
            </div>`;
        }
    }
    selectedTagsDiv.innerHTML = html;
    
    document.querySelectorAll('.remove-tag').forEach(el => {
        el.onclick = () => {
            let id = parseInt(el.dataset.id);
            selectedTagIds = selectedTagIds.filter(tid => tid !== id);
            updateSelectedTagsDisplay();
        };
    });
}

// Tag input with autocomplete
tagInput.oninput = async () => {
    let query = tagInput.value.toLowerCase().trim();
    if(query.length === 0) {
        tagSuggestions.style.display = 'none';
        return;
    }
    
    let suggestions = allTags.filter(tag => 
        tag.name.toLowerCase().includes(query) && !selectedTagIds.includes(tag.id)
    ).slice(0, 5);
    
    if(suggestions.length === 0) {
        tagSuggestions.style.display = 'none';
        return;
    }
    
    let html = '';
    for(let tag of suggestions) {
        let color = tag.color || '#667eea';
        html += `<div class="tag-suggestion" data-id="${tag.id}" data-name="${escapeHtml(tag.name)}" style="border-left:3px solid ${color}">
            <span><i class="fas fa-tag"></i> ${escapeHtml(tag.name)}</span>
            <span style="font-size:0.8em;color:#888">${tag.usage_count} uses</span>
        </div>`;
    }
    tagSuggestions.innerHTML = html;
    tagSuggestions.style.display = 'block';
    
    document.querySelectorAll('.tag-suggestion').forEach(el => {
        el.onclick = () => {
            let id = parseInt(el.dataset.id);
            if(!selectedTagIds.includes(id)) {
                selectedTagIds.push(id);
                updateSelectedTagsDisplay();
            }
            tagInput.value = '';
            tagSuggestions.style.display = 'none';
        };
    });
};

// Add new tag from input
tagInput.onkeypress = async (e) => {
    if(e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        let tagName = tagInput.value.trim();
        if(tagName && tagName !== ',') {
            let existingTag = allTags.find(t => t.name.toLowerCase() === tagName.toLowerCase());
            if(existingTag) {
                if(!selectedTagIds.includes(existingTag.id)) {
                    selectedTagIds.push(existingTag.id);
                    updateSelectedTagsDisplay();
                }
            } else {
                let res = await fetch('/api/tags', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: tagName, color: '#667eea'})
                });
                let newTag = await res.json();
                if(newTag.id) {
                    await loadTags();
                    allTags = await loadTags();
                    selectedTagIds.push(newTag.id);
                    updateSelectedTagsDisplay();
                    showToast(`Tag "${tagName}" created!`, 'success');
                }
            }
            tagInput.value = '';
            tagSuggestions.style.display = 'none';
        }
    }
};

tagInput.onblur = () => {
    setTimeout(() => { tagSuggestions.style.display = 'none'; }, 200);
};

// Manage tags from sidebar button
manageTagsSidebarBtn.onclick = async () => {
    await loadTagList();
    tagManagerModal.style.display = 'block';
};

closeTagManagerBtn.onclick = () => {
    tagManagerModal.style.display = 'none';
};

// Load tag list for management
async function loadTagList() {
    let tags = await loadTags();
    let html = '';
    for(let tag of tags) {
        let color = tag.color || '#667eea';
        html += `
            <div class="tag-item" data-id="${tag.id}">
                <div class="tag-item-info">
                    <div class="tag-color-preview" style="background:${color}" onclick="changeTagColor(${tag.id})"></div>
                    <div>
                        <div class="tag-name">${escapeHtml(tag.name)}</div>
                        <div class="tag-count">Used ${tag.usage_count} times</div>
                    </div>
                </div>
                <div class="tag-actions">
                    <button class="edit-tag" onclick="editTagName(${tag.id}, '${escapeHtml(tag.name)}')"><i class="fas fa-edit"></i></button>
                    <button class="delete-tag" onclick="deleteTag(${tag.id})"><i class="fas fa-trash"></i></button>
                </div>
            </div>
        `;
    }
    document.getElementById('tagList').innerHTML = html || '<div style="text-align:center;padding:20px">No tags yet. Create your first tag!</div>';
}

// Add new tag from manager
addTagBtn.onclick = async () => {
    let name = newTagName.value.trim();
    let color = newTagColor.value;
    if(!name) {
        showToast('Please enter a tag name', 'error');
        return;
    }
    
    let res = await fetch('/api/tags', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name: name, color: color})
    });
    
    if(res.ok) {
        newTagName.value = '';
        await loadTagList();
        await loadTags();
        await loadPopularTags();
        await loadTagFilters();
        showToast(`Tag "${name}" created!`, 'success');
    } else {
        let error = await res.json();
        showToast(error.error || 'Failed to create tag', 'error');
    }
};

// Edit tag name
window.editTagName = async (id, currentName) => {
    let newName = prompt('Enter new tag name:', currentName);
    if(newName && newName !== currentName) {
        let res = await fetch(`/api/tags/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: newName})
        });
        if(res.ok) {
            await loadTagList();
            await loadTags();
            await loadPopularTags();
            await loadTagFilters();
            showToast('Tag updated!', 'success');
        }
    }
};

// Change tag color
window.changeTagColor = async (id) => {
    let color = prompt('Enter hex color code (e.g., #ff0000):', '#667eea');
    if(color) {
        let res = await fetch(`/api/tags/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({color: color})
        });
        if(res.ok) {
            await loadTagList();
            await loadTags();
            await loadTagFilters();
            showToast('Tag color updated!', 'success');
        }
    }
};

// Delete tag
window.deleteTag = async (id) => {
    const confirmed = await showConfirm({
        title: 'Delete Tag',
        message: 'Are you sure you want to delete this tag? It will be removed from all code snippets.',
        type: 'danger',
        confirmText: 'Delete Tag',
        cancelText: 'Cancel'
    });
    
    if(confirmed) {
        let res = await fetch(`/api/tags/${id}`, {method: 'DELETE'});
        if(res.ok) {
            await loadTagList();
            await loadTags();
            await loadPopularTags();
            await loadTagFilters();
            selectedTagIds = selectedTagIds.filter(tid => tid !== id);
            updateSelectedTagsDisplay();
            showToast('Tag deleted!', 'success');
        }
    }
};

function updateProgress(percent, status, details = '') {
    progressBar.style.width = percent + '%';
    progressBar.textContent = Math.round(percent) + '%';
    progressStatus.textContent = status;
    if (details) progressDetails.textContent = details;
}

async function loadStatistics() {
    try {
        let res = await fetch('/api/statistics');
        let stats = await res.json();
        
        let statsHtml = `
            <div class="stat-card">
                <i class="fas fa-code"></i>
                <div class="stat-number">${stats.total_codes}</div>
                <div class="stat-label">Total Code Snippets</div>
            </div>
            <div class="stat-card">
                <i class="fas fa-folder"></i>
                <div class="stat-number">${stats.total_categories}</div>
                <div class="stat-label">Categories</div>
            </div>
            <div class="stat-card">
                <i class="fas fa-tags"></i>
                <div class="stat-number">${stats.total_tags || 0}</div>
                <div class="stat-label">Total Tags</div>
            </div>
            <div class="stat-card">
                <i class="fas fa-file-archive"></i>
                <div class="stat-number">${stats.total_zip_files}</div>
                <div class="stat-label">ZIP Attachments</div>
            </div>
            <div class="stat-card">
                <i class="fas fa-star"></i>
                <div class="stat-number">${stats.most_popular_tag || 'N/A'}</div>
                <div class="stat-label">Most Popular Tag</div>
            </div>
            <div class="stat-card">
                <i class="fas fa-calendar"></i>
                <div class="stat-number">${stats.codes_this_week || 0}</div>
                <div class="stat-label">Added This Week</div>
            </div>
        `;
        document.getElementById('statsGrid').innerHTML = statsHtml;
        
        if (langChart) langChart.destroy();
        if (categoryChart) categoryChart.destroy();
        if (timelineChart) timelineChart.destroy();
        if (zipChart) zipChart.destroy();
        
        const langCtx = document.getElementById('langChart').getContext('2d');
        langChart = new Chart(langCtx, {
            type: 'pie',
            data: {
                labels: stats.language_distribution.map(l => l.language),
                datasets: [{
                    data: stats.language_distribution.map(l => l.count),
                    backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#FF6384', '#C9CBCF']
                }]
            },
            options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom' } } }
        });
        
        const catCtx = document.getElementById('categoryChart').getContext('2d');
        categoryChart = new Chart(catCtx, {
            type: 'bar',
            data: {
                labels: stats.category_distribution.map(c => c.name),
                datasets: [{ label: 'Number of Codes', data: stats.category_distribution.map(c => c.count), backgroundColor: '#667eea', borderColor: '#764ba2', borderWidth: 1 }]
            },
            options: { responsive: true, maintainAspectRatio: true, scales: { y: { beginAtZero: true, title: { display: true, text: 'Code Count' } } } }
        });
        
        const timelineCtx = document.getElementById('timelineChart').getContext('2d');
        timelineChart = new Chart(timelineCtx, {
            type: 'line',
            data: {
                labels: stats.timeline.map(t => t.date),
                datasets: [{ label: 'Codes Added', data: stats.timeline.map(t => t.count), borderColor: '#ff6b6b', backgroundColor: 'rgba(255, 107, 107, 0.1)', tension: 0.4, fill: true }]
            },
            options: { responsive: true, maintainAspectRatio: true, scales: { y: { beginAtZero: true, title: { display: true, text: 'Codes Added' } } } }
        });
        
        const zipCtx = document.getElementById('zipChart').getContext('2d');
        zipChart = new Chart(zipCtx, {
            type: 'doughnut',
            data: {
                labels: ['With ZIP Files', 'Without ZIP Files'],
                datasets: [{ data: [stats.zip_attachments, stats.total_codes - stats.zip_attachments], backgroundColor: ['#4caf50', '#ff9800'] }]
            },
            options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom' } } }
        });
        
    } catch (error) {
        console.error('Error loading statistics:', error);
        showToast('Failed to load statistics', 'error');
    }
}

statsBtn.onclick = async () => {
    statsModal.style.display = 'block';
    await loadStatistics();
};

closeStatsBtn.onclick = () => { statsModal.style.display = 'none'; };

async function performBackup() {
    progressModal.style.display = 'block';
    progressTitle.innerHTML = '<i class="fas fa-database"></i> Creating Backup...';
    updateProgress(0, 'Initializing backup...');
    
    try {
        updateProgress(10, 'Preparing database backup...');
        let res = await fetch('/api/backup');
        if (!res.ok) throw new Error('Backup failed');
        updateProgress(50, 'Compressing files...');
        let blob = await res.blob();
        updateProgress(80, 'Saving backup file...');
        let url = window.URL.createObjectURL(blob);
        let a = document.createElement('a');
        a.href = url;
        let timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        a.download = `codehaven_backup_${timestamp}.chb`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        updateProgress(100, 'Backup completed successfully!');
        progressTitle.innerHTML = '<i class="fas fa-check-circle"></i> Backup Complete!';
        setTimeout(() => { progressModal.style.display = 'none'; showToast('Backup created successfully!', 'success'); }, 1500);
    } catch (error) {
        console.error('Backup error:', error);
        progressModal.style.display = 'none';
        showToast('Backup failed: ' + error.message, 'error');
    }
}

async function performRestore() {
    let fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.chb';
    fileInput.onchange = async (e) => {
        let file = e.target.files[0];
        if (!file) return;
        const confirmed = await showConfirm({
            title: 'Restore Data',
            message: ' WARNING: This will replace ALL current data. This action cannot be undone. Are you sure?',
            type: 'danger', confirmText: 'Yes, Restore', cancelText: 'Cancel'
        });
        if (!confirmed) return;
        progressModal.style.display = 'block';
        progressTitle.innerHTML = '<i class="fas fa-upload"></i> Restoring Backup...';
        updateProgress(0, 'Preparing restore...');
        try {
            let formData = new FormData();
            formData.append('backup_file', file);
            updateProgress(20, 'Uploading backup file...');
            let res = await fetch('/api/restore', { method: 'POST', body: formData });
            updateProgress(70, 'Restoring data...');
            let result = await res.json();
            if (result.success) {
                updateProgress(100, 'Restore completed successfully!');
                progressTitle.innerHTML = '<i class="fas fa-check-circle"></i> Restore Complete!';
                setTimeout(() => { progressModal.style.display = 'none'; showToast('Data restored! Refreshing...', 'success'); setTimeout(() => location.reload(), 1500); }, 1500);
            } else {
                throw new Error(result.error || 'Restore failed');
            }
        } catch (error) {
            console.error('Restore error:', error);
            progressModal.style.display = 'none';
            showToast('Restore failed: ' + error.message, 'error');
        }
    };
    fileInput.click();
}

backupBtn.onclick = async () => {
    const confirmed = await showConfirm({
        title: 'Create Backup',
        message: 'Create a complete backup of all your codes, categories, tags, and ZIP files.',
        type: 'info', confirmText: 'Create Backup', cancelText: 'Cancel'
    });
    if (confirmed) await performBackup();
};

restoreBtn.onclick = async () => { await performRestore(); };

function showConfirm(options) {
    return new Promise((resolve) => {
        const type = options.type || 'warning';
        const iconMap = { warning: '<i class="fas fa-exclamation-triangle"></i>', danger: '<i class="fas fa-trash-alt"></i>', info: '<i class="fas fa-info-circle"></i>', question: '<i class="fas fa-question-circle"></i>' };
        const iconColorMap = { warning: 'warning', danger: 'danger', info: 'info', question: 'info' };
        confirmIcon.innerHTML = iconMap[type] || iconMap.warning;
        confirmIcon.className = `confirm-icon ${iconColorMap[type] || 'warning'}`;
        confirmTitle.textContent = options.title || 'Confirm Action';
        confirmMessage.textContent = options.message || 'Are you sure you want to proceed?';
        if (type === 'danger') {
            confirmOkBtn.className = 'confirm-ok';
            confirmOkBtn.innerHTML = '<i class="fas fa-trash"></i> ' + (options.confirmText || 'Delete');
        } else {
            confirmOkBtn.className = 'confirm-ok success';
            confirmOkBtn.innerHTML = '<i class="fas fa-check"></i> ' + (options.confirmText || 'Confirm');
        }
        confirmCancelBtn.innerHTML = '<i class="fas fa-times"></i> ' + (options.cancelText || 'Cancel');
        confirmModal.style.display = 'block';
        const onConfirm = () => { cleanup(); resolve(true); };
        const onCancel = () => { cleanup(); resolve(false); };
        const onBackgroundClick = (e) => { if (e.target === confirmModal) { cleanup(); resolve(false); } };
        const cleanup = () => {
            confirmOkBtn.removeEventListener('click', onConfirm);
            confirmCancelBtn.removeEventListener('click', onCancel);
            confirmModal.removeEventListener('click', onBackgroundClick);
            confirmModal.style.display = 'none';
        };
        confirmOkBtn.addEventListener('click', onConfirm);
        confirmCancelBtn.addEventListener('click', onCancel);
        confirmModal.addEventListener('click', onBackgroundClick);
    });
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.className = 'toast ' + type;
    const icon = type === 'success' ? '' : (type === 'error' ? '' : '');
    toast.innerHTML = `${icon} ${message}`;
    toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; toast.className = 'toast'; }, 3000);
}

themeSelector.onchange = () => {
    const theme = themeSelector.value;
    document.getElementById('highlight-theme').href = themes[theme];
    localStorage.setItem('highlight-theme', theme);
    showToast(`Theme changed to ${theme}`, 'info');
};

if(localStorage.getItem('highlight-theme')) {
    const savedTheme = localStorage.getItem('highlight-theme');
    themeSelector.value = savedTheme;
    document.getElementById('highlight-theme').href = themes[savedTheme];
}

fontPlus.onclick = () => changeFont(2);
fontMinus.onclick = () => changeFont(-2);
function changeFont(delta) { fontSize = Math.max(10, Math.min(24, fontSize + delta)); document.body.style.fontSize = fontSize + 'px'; showToast(`Font size: ${fontSize}px`, 'info'); }

themeBtn.onclick = () => { document.body.classList.toggle('dark-theme'); const isDark = document.body.classList.contains('dark-theme'); localStorage.setItem('dark-mode', isDark); showToast(isDark ? 'Dark mode enabled' : 'Light mode enabled', 'info'); };
if(localStorage.getItem('dark-mode') === 'true') document.body.classList.add('dark-theme');

aboutBtn.onclick = () => { aboutModal.style.display = 'block'; };
closeAboutBtn.onclick = () => { aboutModal.style.display = 'none'; };
closeProgressBtn.onclick = () => { progressModal.style.display = 'none'; };
menuBtn.onclick = () => sidebar.classList.toggle('show');
document.addEventListener('click', (e) => { if(window.innerWidth <= 768 && !sidebar.contains(e.target) && !menuBtn.contains(e.target)) sidebar.classList.remove('show'); });

async function executeCode(codeId) {
    executionModal.style.display = 'block';
    executionOutput.innerHTML = '<div class="execution-loading"><i class="fas fa-spinner fa-spin"></i> Executing Python code...</div>';
    try {
        let res = await fetch('/api/codes/' + codeId + '/execute', {method:'POST'});
        let result = await res.json();
        if(result.success) {
            let outputHtml = '<div class="execution-success"><i class="fas fa-check-circle"></i> <strong>Execution completed!</strong></div>';
            if(result.stdout) outputHtml += '<div style="margin-top:15px"><strong> Output:</strong><pre>' + escapeHtml(result.stdout) + '</pre></div>';
            if(result.stderr) outputHtml += '<div style="margin-top:15px" class="execution-error"><strong> Errors/Warnings:</strong><pre>' + escapeHtml(result.stderr) + '</pre></div>';
            if(result.execution_time) outputHtml += '<div style="margin-top:10px;font-size:0.85em;color:#888"><i class="fas fa-clock"></i> Execution time: ' + result.execution_time + '</div>';
            executionOutput.innerHTML = outputHtml;
        } else {
            executionOutput.innerHTML = '<div class="execution-error"><i class="fas fa-exclamation-triangle"></i> <strong>Execution failed:</strong><pre>' + escapeHtml(result.error) + '</pre></div>';
        }
    } catch(e) { executionOutput.innerHTML = '<div class="execution-error"><i class="fas fa-exclamation-triangle"></i> Error: ' + escapeHtml(e.message) + '</div>'; }
}

closeExecBtn.onclick = () => { executionModal.style.display = 'none'; };

async function loadCategories() {
    try {
        let res = await fetch('/api/categories');
        let data = await res.json();
        let html = '';
        let allClass = currentCat === 'all' ? 'active' : '';
        html += '<div class="cat-item ' + allClass + '" data-cat="all"><span><i class="fas fa-database"></i> All Categories</span><span></span></div>';
        for(let cat of data.categories) {
            let catClass = currentCat == cat.id ? 'active' : '';
            html += '<div class="cat-item ' + catClass + '" data-cat="' + cat.id + '">';
            html += '<span><i class="fas fa-tag"></i> ' + escapeHtml(cat.name) + '</span>';
            html += '<span class="delete-cat" data-id="' + cat.id + '"><i class="fas fa-trash"></i></span></div>';
        }
        document.getElementById('categories').innerHTML = html;
        let opts = '<option value=""> Select Category</option>';
        for(let cat of data.categories) opts += '<option value="' + cat.id + '">' + escapeHtml(cat.name) + '</option>';
        document.getElementById('catSelect').innerHTML = opts;
        document.querySelectorAll('.cat-item').forEach(el => {
            el.onclick = (e) => {
                if(e.target.classList.contains('delete-cat') || e.target.parentElement.classList.contains('delete-cat')) return;
                filterCategory(el.dataset.cat);
                if(window.innerWidth <= 768) sidebar.classList.remove('show');
            };
        });
        document.querySelectorAll('.delete-cat').forEach(el => {
            el.onclick = (e) => { e.stopPropagation(); deleteCategory(el.dataset.id); };
        });
    } catch(e) { console.error(e); }
}

async function loadCodes() {
    try {
        let url = '/api/codes?page=' + currentPage + '&search=' + encodeURIComponent(searchInput.value) + '&cat=' + currentCat;
        if(currentTag) url += '&tag=' + currentTag;
        let res = await fetch(url);
        let data = await res.json();
        if(!data.codes) return;
        
        let html = '';
        for(let code of data.codes) {
            let langClass = code.language.toLowerCase();
            let date = code.created_at ? new Date(code.created_at).toLocaleDateString() : 'Unknown';
            html += '<div class="card">';
            html += '<div class="card-header">';
            html += '<div class="card-title"><i class="fas fa-code"></i> ' + escapeHtml(code.title) + '</div>';
            html += '<div class="card-meta">';
            html += '<span><i class="fas fa-folder"></i> ' + escapeHtml(code.category_name) + '</span>';
            html += '<span><i class="fas fa-tag"></i> <span class="lang-badge ' + langClass + '">' + code.language.toUpperCase() + '</span></span>';
            html += '<span><i class="fas fa-calendar-alt"></i> ' + date + '</span>';
            if(code.zip_filename) {
                html += '<span class="zip-info"><i class="fas fa-file-archive"></i> ZIP: ' + escapeHtml(code.zip_filename) + '</span>';
            }
            html += '</div>';
            if(code.tags && code.tags.length > 0) {
                html += '<div class="card-tags">';
                for(let tag of code.tags) {
                    let color = tag.color || '#667eea';
                    html += `<span class="tag" style="background:${color};color:white;cursor:pointer" data-tag-id="${tag.id}"><i class="fas fa-tag"></i> ${escapeHtml(tag.name)}</span>`;
                }
                html += '</div>';
            }
            html += '</div>';
            html += '<div class="code-container">';
            html += '<pre><code class="language-' + code.language + '">' + escapeHtml(code.code) + '</code></pre>';
            html += '<button class="copy-btn" data-id="' + code.id + '"><i class="fas fa-copy"></i> Copy Code</button>';
            html += '</div>';
            html += '<div class="card-actions">';
            html += '<button class="edit-btn" data-id="' + code.id + '"><i class="fas fa-edit"></i> Edit</button>';
            html += '<button class="delete-btn" data-id="' + code.id + '"><i class="fas fa-trash"></i> Delete</button>';
            if(code.language.toLowerCase() === 'python') {
                html += '<button class="execute-btn" data-id="' + code.id + '"><i class="fas fa-play"></i> Execute</button>';
            }
            if(code.zip_filename) {
                html += '<button class="download-zip-btn" data-id="' + code.id + '"><i class="fas fa-download"></i> Download ZIP</button>';
            }
            html += '</div></div>';
        }
        document.getElementById('codes').innerHTML = html || '<div style="text-align:center;padding:50px"><i class="fas fa-inbox" style="font-size:48px;color:#ddd"></i><p>No codes found. Click "Add Code" to get started!</p></div>';
        document.getElementById('stats').innerHTML = '<i class="fas fa-database"></i> Total: ' + (data.total || 0) + ' snippets';
        
        document.querySelectorAll('pre code').forEach(block => hljs.highlightElement(block));
        document.querySelectorAll('.copy-btn').forEach(btn => btn.onclick = () => copyCode(btn.dataset.id));
        document.querySelectorAll('.edit-btn').forEach(btn => btn.onclick = () => editCode(btn.dataset.id));
        document.querySelectorAll('.delete-btn').forEach(btn => btn.onclick = () => deleteCode(btn.dataset.id));
        document.querySelectorAll('.execute-btn').forEach(btn => btn.onclick = () => executeCode(btn.dataset.id));
        document.querySelectorAll('.download-zip-btn').forEach(btn => btn.onclick = () => downloadZip(btn.dataset.id));
        document.querySelectorAll('.card-tags .tag').forEach(el => { el.onclick = (e) => { e.stopPropagation(); filterByTag(el.dataset.tagId); }; });
        
        let paginationHtml = '<div class="pagination"><button onclick="changePage(1)" ' + (currentPage === 1 ? 'disabled' : '') + '><i class="fas fa-angle-double-left"></i> First</button>';
        paginationHtml += '<button onclick="changePage(' + (currentPage-1) + ')" ' + (currentPage === 1 ? 'disabled' : '') + '><i class="fas fa-angle-left"></i> Previous</button>';
        paginationHtml += '<span>Page ' + currentPage + ' of ' + data.total_pages + '</span>';
        paginationHtml += '<button onclick="changePage(' + (currentPage+1) + ')" ' + (currentPage === data.total_pages ? 'disabled' : '') + '>Next <i class="fas fa-angle-right"></i></button>';
        paginationHtml += '<button onclick="changePage(' + data.total_pages + ')" ' + (currentPage === data.total_pages ? 'disabled' : '') + '>Last <i class="fas fa-angle-double-right"></i></button></div>';
        document.getElementById('pagination').innerHTML = paginationHtml;
    } catch(e) { console.error(e); }
}

addCatBtn.onclick = async () => {
    let name = document.getElementById('newCat').value.trim();
    if(!name) { showToast('Please enter category name', 'error'); return; }
    let fd = new FormData(); fd.append('name', name);
    await fetch('/api/categories', {method:'POST', body:fd});
    document.getElementById('newCat').value = '';
    loadCategories();
    showToast('Category added successfully!');
};

async function deleteCategory(id) {
    const confirmed = await showConfirm({
        title: 'Delete Category', message: 'Delete this category? All codes will be moved to "Other".',
        type: 'danger', confirmText: 'Delete Category', cancelText: 'Cancel'
    });
    if(confirmed) {
        await fetch('/api/categories/' + id, {method:'DELETE'});
        if(currentCat == id) filterCategory('all');
        loadCategories();
        loadCodes();
        showToast('Category deleted successfully');
    }
}

addCodeBtn.onclick = () => {
    document.getElementById('modal').style.display = 'block';
    document.getElementById('modalTitle').innerHTML = '<i class="fas fa-plus"></i> Add Code Snippet';
    document.getElementById('codeId').value = '';
    document.getElementById('title').value = '';
    document.getElementById('codeContent').value = '';
    document.getElementById('catSelect').value = '';
    document.getElementById('language').value = 'python';
    selectedTagIds = [];
    updateSelectedTagsDisplay();
    tagInput.value = '';
    zipFileInput.value = '';
    currentZipFilename = null;
    currentZipInfo.style.display = 'none';
};

cancelBtn.onclick = () => document.getElementById('modal').style.display = 'none';
window.onclick = (e) => { 
    if(e.target === document.getElementById('modal')) document.getElementById('modal').style.display = 'none';
    if(e.target === executionModal) executionModal.style.display = 'none';
    if(e.target === aboutModal) aboutModal.style.display = 'none';
    if(e.target === statsModal) statsModal.style.display = 'none';
    if(e.target === tagManagerModal) tagManagerModal.style.display = 'none';
    if(e.target === confirmModal) confirmModal.style.display = 'none';
    if(e.target === progressModal) progressModal.style.display = 'none';
};

removeZipBtn.onclick = () => { currentZipFilename = null; zipFileInput.value = ''; currentZipInfo.style.display = 'none'; };

saveBtn.onclick = async () => {
    let id = document.getElementById('codeId').value;
    let formData = new FormData();
    formData.append('category_id', document.getElementById('catSelect').value);
    formData.append('title', document.getElementById('title').value.trim());
    formData.append('code', document.getElementById('codeContent').value);
    formData.append('language', document.getElementById('language').value);
    formData.append('tags', JSON.stringify(selectedTagIds));
    
    if(zipFileInput.files.length > 0) formData.append('zip_file', zipFileInput.files[0]);
    if(currentZipFilename === null && id) formData.append('remove_zip', 'true');
    
    if(!formData.get('category_id') || !formData.get('title') || !formData.get('code')) {
        showToast('Please fill all fields', 'error');
        return;
    }
    
    let url = id ? '/api/codes/' + id : '/api/codes';
    let method = id ? 'PUT' : 'POST';
    
    let res = await fetch(url, {method:method, body:formData});
    if(res.ok) {
        document.getElementById('modal').style.display = 'none';
        loadCodes();
        loadPopularTags();
        showToast(id ? 'Code updated successfully!' : 'Code added successfully!');
    } else {
        let error = await res.json();
        showToast('Error saving code: ' + (error.error || 'Unknown error'), 'error');
    }
};

async function editCode(id) {
    let res = await fetch('/api/codes/' + id);
    let code = await res.json();
    if(code) {
        document.getElementById('modalTitle').innerHTML = '<i class="fas fa-edit"></i> Edit Code Snippet';
        document.getElementById('codeId').value = code.id;
        document.getElementById('catSelect').value = code.category_id;
        document.getElementById('title').value = code.title;
        document.getElementById('language').value = code.language;
        document.getElementById('codeContent').value = code.code;
        selectedTagIds = code.tags ? code.tags.map(t => t.id) : [];
        updateSelectedTagsDisplay();
        currentZipFilename = code.zip_filename;
        if(code.zip_filename) { currentZipName.textContent = code.zip_filename; currentZipInfo.style.display = 'block'; }
        else { currentZipInfo.style.display = 'none'; }
        zipFileInput.value = '';
        document.getElementById('modal').style.display = 'block';
    }
}

async function deleteCode(id) {
    const confirmed = await showConfirm({
        title: 'Delete Code Snippet', message: 'Delete this code snippet? This action cannot be undone.',
        type: 'danger', confirmText: 'Delete Code', cancelText: 'Cancel'
    });
    if(confirmed) {
        await fetch('/api/codes/' + id, {method:'DELETE'});
        loadCodes();
        loadPopularTags();
        showToast('Code deleted successfully');
    }
}

async function copyCode(id) {
    let res = await fetch('/api/codes/' + id);
    let code = await res.json();
    if(code) { await navigator.clipboard.writeText(code.code); showToast(' Code copied to clipboard!'); }
}

function downloadZip(id) { window.location.href = '/api/codes/' + id + '/download'; }
function filterCategory(id) { currentCat = id; currentPage = 1; loadCategories(); loadCodes(); }
searchInput.onkeyup = () => { currentPage = 1; loadCodes(); };
function changePage(page) { currentPage = page; loadCodes(); }
function escapeHtml(str) { if(!str) return ''; return str.replace(/[&<>]/g, function(m) { if(m === '&') return '&amp;'; if(m === '<') return '&lt;'; if(m === '>') return '&gt;'; return m; }); }

// Initialize
loadCategories();
loadCodes();
loadTags();
loadPopularTags();
loadTagFilters();
</script>






<script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.23.4/ace.js"></script>
<script>
// SUPER SIMPLE PRO EDITOR WITH FONT CONTROLS - WORKING!
(function(){
    let active = false;
    let editor = null;
    let currentFont = 13;
    
    function addButton() {
        let ta = document.getElementById('codeContent');
        if(!ta || document.getElementById('superBtn')) return;
        
        let container = document.createElement('div');
        container.style.cssText = 'display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center;';
        
        let btn = document.createElement('button');
        btn.id = 'superBtn';
        btn.textContent = ' Pro Editor';
        btn.style.cssText = 'background:#667eea;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:14px;';
        
        let fontMinus = document.createElement('button');
        fontMinus.textContent = 'A-';
        fontMinus.style.cssText = 'background:#ff9800;color:white;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;font-size:14px;display:none;';
        
        let fontPlus = document.createElement('button');
        fontPlus.textContent = 'A+';
        fontPlus.style.cssText = 'background:#ff9800;color:white;border:none;padding:8px 12px;border-radius:6px;cursor:pointer;font-size:14px;display:none;';
        
        let fontDisplay = document.createElement('span');
        fontDisplay.style.cssText = 'font-size:12px;color:#666;display:none;';
        
        container.appendChild(btn);
        container.appendChild(fontMinus);
        container.appendChild(fontPlus);
        container.appendChild(fontDisplay);
        ta.parentNode.insertBefore(container, ta);
        
        function updateFont() {
            if(editor && active) {
                editor.setFontSize(currentFont);
                fontDisplay.textContent = currentFont + 'px';
            }
        }
        
        fontPlus.onclick = () => {
            if(editor && active) {
                currentFont = Math.min(36, currentFont + 2);
                updateFont();
            }
        };
        
        fontMinus.onclick = () => {
            if(editor && active) {
                currentFont = Math.max(10, currentFont - 2);
                updateFont();
            }
        };
        
        btn.onclick = () => {
            if(!active) {
                let code = ta.value;
                ta.style.display = 'none';
                
                let box = document.createElement('div');
                box.id = 'superBox';
                box.style.cssText = 'border:2px solid #667eea;border-radius:8px;margin-top:10px;';
                box.innerHTML = `
                    <div style="padding:10px;background:#f8f9fa;border-radius:8px 8px 0 0;">
                        <button id="copySuper" style="background:#28a745;color:white;border:none;padding:4px 12px;border-radius:4px;cursor:pointer;"> Copy</button>
                        <span id="statSuper" style="float:right;font-size:12px;color:#666;">0 chars</span>
                    </div>
                    <div id="aceSuper" style="height:350px;"></div>
                `;
                ta.parentNode.insertBefore(box, ta.nextSibling);
                
                editor = ace.edit('aceSuper');
                editor.setTheme('ace/theme/monokai');
                editor.session.setMode('ace/mode/python');
                editor.setValue(code, -1);
                editor.setOptions({
                    fontSize: currentFont + 'px',
                    enableBasicAutocompletion: true,
                    tabSize: 4
                });
                
                editor.session.on('change', () => {
                    let c = editor.getValue();
                    document.getElementById('statSuper').innerHTML = c.length + ' chars';
                    ta.value = c;
                });
                
                document.getElementById('copySuper').onclick = () => {
                    navigator.clipboard.writeText(editor.getValue());
                    let copyBtn = document.getElementById('copySuper');
                    copyBtn.innerHTML = ' Copied!';
                    setTimeout(() => { copyBtn.innerHTML = ' Copy'; }, 1500);
                };
                
                fontMinus.style.display = 'inline-block';
                fontPlus.style.display = 'inline-block';
                fontDisplay.style.display = 'inline-block';
                fontDisplay.textContent = currentFont + 'px';
                btn.textContent = ' Normal Editor';
                btn.style.background = '#6c757d';
                active = true;
            } else {
                if(editor) ta.value = editor.getValue();
                let box = document.getElementById('superBox');
                if(box) box.remove();
                ta.style.display = 'block';
                fontMinus.style.display = 'none';
                fontPlus.style.display = 'none';
                fontDisplay.style.display = 'none';
                btn.textContent = ' Pro Editor';
                btn.style.background = '#667eea';
                active = false;
                editor = null;
            }
        };
    }
    
    let modal = document.getElementById('modal');
    if(modal) {
        new MutationObserver(() => {
            if(modal.style.display === 'block') setTimeout(addButton, 100);
        }).observe(modal, {attributes: true});
    }
    
    let add = document.getElementById('addCodeBtn');
    if(add) {
        let old = add.onclick;
        add.onclick = () => { if(old) old(); setTimeout(addButton, 200); };
    }
    
    let oldEdit = window.editCode;
    if(oldEdit) {
        window.editCode = (id) => { oldEdit(id); setTimeout(addButton, 200); };
    }
})();
</script>







</body>
</html>
'''

# API Routes 
@route('/api/tags')
def get_tags():
    try:
        conn = sqlite3.connect('codehaven.db')
        conn.row_factory = sqlite3.Row
        tags = conn.execute('SELECT * FROM tags ORDER BY name').fetchall()
        conn.close()
        return {'tags': [dict(t) for t in tags]}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/tags/popular')
def get_popular_tags():
    try:
        conn = sqlite3.connect('codehaven.db')
        conn.row_factory = sqlite3.Row
        tags = conn.execute('''
            SELECT t.*, COUNT(ct.tag_id) as usage_count 
            FROM tags t
            LEFT JOIN code_tags ct ON t.id = ct.tag_id
            GROUP BY t.id
            ORDER BY usage_count DESC
            LIMIT 10
        ''').fetchall()
        conn.close()
        return {'tags': [dict(t) for t in tags]}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/tags', method='POST')
def add_tag():
    try:
        data = json.loads(request.body.read().decode('utf-8'))
        name = data.get('name')
        color = data.get('color', '#667eea')
        
        if not name:
            response.status = 400
            return {'error': 'Tag name required'}
        
        conn = sqlite3.connect('codehaven.db')
        conn.execute('INSERT INTO tags (name, color) VALUES (?, ?)', (name, color))
        tag_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.commit()
        conn.close()
        
        return {'id': tag_id, 'name': name, 'color': color}
    except sqlite3.IntegrityError:
        response.status = 400
        return {'error': 'Tag already exists'}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/tags/<id:int>', method='PUT')
def update_tag(id):
    try:
        data = json.loads(request.body.read().decode('utf-8'))
        name = data.get('name')
        color = data.get('color')
        
        conn = sqlite3.connect('codehaven.db')
        if name:
            conn.execute('UPDATE tags SET name = ? WHERE id = ?', (name, id))
        if color:
            conn.execute('UPDATE tags SET color = ? WHERE id = ?', (color, id))
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/tags/<id:int>', method='DELETE')
def delete_tag(id):
    try:
        conn = sqlite3.connect('codehaven.db')
        conn.execute('DELETE FROM tags WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/categories')
def get_categories():
    try:
        conn = sqlite3.connect('codehaven.db')
        conn.row_factory = sqlite3.Row
        cats = conn.execute('SELECT * FROM categories ORDER BY name').fetchall()
        conn.close()
        return {'categories': [dict(c) for c in cats]}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/categories', method='POST')
def add_category():
    try:
        name = request.forms.get('name')
        if name:
            conn = sqlite3.connect('codehaven.db')
            conn.execute('INSERT INTO categories (name) VALUES (?)', (name,))
            conn.commit()
            conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/categories/<id:int>', method='DELETE')
def delete_category(id):
    try:
        conn = sqlite3.connect('codehaven.db')
        other = conn.execute("SELECT id FROM categories WHERE name = 'Other' LIMIT 1").fetchone()
        if other:
            conn.execute('UPDATE codes SET category_id = ? WHERE category_id = ?', (other[0], id))
        conn.execute('DELETE FROM categories WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/statistics')
def get_statistics():
    try:
        conn = sqlite3.connect('codehaven.db')
        conn.row_factory = sqlite3.Row
        
        total_codes = conn.execute('SELECT COUNT(*) as count FROM codes').fetchone()[0]
        total_categories = conn.execute('SELECT COUNT(*) as count FROM categories').fetchone()[0]
        total_tags = conn.execute('SELECT COUNT(*) as count FROM tags').fetchone()[0]
        total_zip = conn.execute('SELECT COUNT(*) as count FROM codes WHERE zip_filename IS NOT NULL').fetchone()[0]
        
        lang_dist = conn.execute('SELECT language, COUNT(*) as count FROM codes GROUP BY language ORDER BY count DESC').fetchall()
        cat_dist = conn.execute('SELECT c.name, COUNT(co.id) as count FROM categories c LEFT JOIN codes co ON c.id = co.category_id GROUP BY c.id ORDER BY count DESC').fetchall()
        timeline = conn.execute('SELECT date(created_at) as date, COUNT(*) as count FROM codes WHERE created_at >= date("now", "-7 days") GROUP BY date(created_at) ORDER BY date ASC').fetchall()
        
        most_popular_tag = conn.execute('''
            SELECT t.name, COUNT(ct.tag_id) as count 
            FROM tags t
            LEFT JOIN code_tags ct ON t.id = ct.tag_id
            GROUP BY t.id
            ORDER BY count DESC
            LIMIT 1
        ''').fetchone()
        
        codes_week = conn.execute('SELECT COUNT(*) as count FROM codes WHERE created_at >= date("now", "weekday 0", "-7 days")').fetchone()[0]
        
        conn.close()
        
        return {
            'total_codes': total_codes,
            'total_categories': total_categories,
            'total_tags': total_tags,
            'total_zip_files': total_zip,
            'language_distribution': [{'language': l[0], 'count': l[1]} for l in lang_dist],
            'category_distribution': [{'name': c[0], 'count': c[1]} for c in cat_dist],
            'timeline': [{'date': t[0], 'count': t[1]} for t in timeline],
            'most_popular_tag': most_popular_tag[0] if most_popular_tag else 'N/A',
            'codes_this_week': codes_week,
            'zip_attachments': total_zip
        }
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/backup', method='GET')
def create_backup():
    try:
        import tempfile
        import datetime
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_file = os.path.join(BACKUP_DIR, f'temp_backup_{uuid.uuid4().hex[:8]}.chb')
            db_backup = os.path.join(temp_dir, 'codehaven.db')
            shutil.copy2('codehaven.db', db_backup)
            
            zip_backup = os.path.join(temp_dir, 'zipcode')
            if os.path.exists(ZIP_DIR):
                shutil.copytree(ZIP_DIR, zip_backup)
            
            metadata = {'version': '1.0', 'created_at': datetime.datetime.now().isoformat(), 'database': 'codehaven.db', 'zip_count': len(os.listdir(ZIP_DIR)) if os.path.exists(ZIP_DIR) else 0}
            with open(os.path.join(temp_dir, 'metadata.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            with open(backup_file, 'rb') as f:
                backup_data = f.read()
            os.remove(backup_file)
            
            response.headers['Content-Type'] = 'application/octet-stream'
            response.headers['Content-Disposition'] = f'attachment; filename="codehaven_backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.chb"'
            return backup_data
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/restore', method='POST')
def restore_backup():
    try:
        import tempfile
        backup_file = request.files.get('backup_file')
        if not backup_file:
            response.status = 400
            return {'error': 'No backup file provided'}
        
        temp_backup = os.path.join(BACKUP_DIR, f'restore_temp_{uuid.uuid4().hex[:8]}.chb')
        backup_file.save(temp_backup)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(temp_backup, 'r') as zipf:
                zipf.extractall(temp_dir)
            
            metadata_path = os.path.join(temp_dir, 'metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
            
            conn = sqlite3.connect('codehaven.db')
            conn.close()
            
            current_backup = os.path.join(BACKUP_DIR, f'pre_restore_backup_{uuid.uuid4().hex[:8]}.chb')
            with zipfile.ZipFile(current_backup, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write('codehaven.db', 'codehaven.db')
                if os.path.exists(ZIP_DIR):
                    for root, dirs, files in os.walk(ZIP_DIR):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, os.path.dirname(ZIP_DIR))
                            zipf.write(file_path, arcname)
            
            db_restore = os.path.join(temp_dir, 'codehaven.db')
            if os.path.exists(db_restore):
                shutil.copy2(db_restore, 'codehaven.db')
            
            zip_restore = os.path.join(temp_dir, 'zipcode')
            if os.path.exists(zip_restore):
                if os.path.exists(ZIP_DIR):
                    shutil.rmtree(ZIP_DIR)
                shutil.copytree(zip_restore, ZIP_DIR)
            elif not os.path.exists(ZIP_DIR):
                os.makedirs(ZIP_DIR)
            
            os.remove(temp_backup)
            return {'success': True, 'message': 'Restore completed successfully'}
    except Exception as e:
        response.status = 500
        return {'error': str(e), 'success': False}

@route('/api/codes')
def get_codes():
    try:
        page = int(request.query.get('page', 1))
        per_page = 5
        search = request.query.get('search', '')
        cat = request.query.get('cat', 'all')
        tag_id = request.query.get('tag')
        offset = (page - 1) * per_page
        
        conn = sqlite3.connect('codehaven.db')
        conn.row_factory = sqlite3.Row
        
        if tag_id:
            query = '''
                SELECT DISTINCT c.*, cat.name as category_name 
                FROM codes c 
                JOIN categories cat ON c.category_id = cat.id
                JOIN code_tags ct ON c.id = ct.code_id
                WHERE ct.tag_id = ?
            '''
            params = [tag_id]
            if search:
                query += ' AND (c.title LIKE ? OR c.code LIKE ?)'
                params.extend([f'%{search}%', f'%{search}%'])
            if cat != 'all':
                query += ' AND c.category_id = ?'
                params.append(cat)
            query += ' ORDER BY c.id DESC LIMIT ? OFFSET ?'
            params.extend([per_page, offset])
            codes = conn.execute(query, params).fetchall()
            
            count_query = 'SELECT COUNT(DISTINCT c.id) as total FROM codes c JOIN code_tags ct ON c.id = ct.code_id WHERE ct.tag_id = ?'
            count_params = [tag_id]
            if search:
                count_query += ' AND (c.title LIKE ? OR c.code LIKE ?)'
                count_params.extend([f'%{search}%', f'%{search}%'])
            if cat != 'all':
                count_query += ' AND c.category_id = ?'
                count_params.append(cat)
            total = conn.execute(count_query, count_params).fetchone()[0]
        else:
            query = 'SELECT c.*, cat.name as category_name FROM codes c JOIN categories cat ON c.category_id = cat.id WHERE 1=1'
            params = []
            if search:
                query += ' AND (c.title LIKE ? OR c.code LIKE ?)'
                params.extend([f'%{search}%', f'%{search}%'])
            if cat != 'all':
                query += ' AND c.category_id = ?'
                params.append(cat)
            query += ' ORDER BY c.id DESC LIMIT ? OFFSET ?'
            params.extend([per_page, offset])
            codes = conn.execute(query, params).fetchall()
            
            count_query = 'SELECT COUNT(*) as total FROM codes c WHERE 1=1'
            count_params = []
            if search:
                count_query += ' AND (c.title LIKE ? OR c.code LIKE ?)'
                count_params.extend([f'%{search}%', f'%{search}%'])
            if cat != 'all':
                count_query += ' AND c.category_id = ?'
                count_params.append(cat)
            total = conn.execute(count_query, count_params).fetchone()[0]
        
        result_codes = []
        for code in codes:
            code_dict = dict(code)
            tags = conn.execute('''
                SELECT t.* FROM tags t
                JOIN code_tags ct ON t.id = ct.tag_id
                WHERE ct.code_id = ?
            ''', (code['id'],)).fetchall()
            code_dict['tags'] = [dict(tag) for tag in tags]
            result_codes.append(code_dict)
        
        conn.close()
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        return {'codes': result_codes, 'total': total, 'total_pages': total_pages}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/codes/<id:int>')
def get_code(id):
    try:
        conn = sqlite3.connect('codehaven.db')
        conn.row_factory = sqlite3.Row
        code = conn.execute('SELECT * FROM codes WHERE id = ?', (id,)).fetchone()
        if code:
            code_dict = dict(code)
            tags = conn.execute('''
                SELECT t.* FROM tags t
                JOIN code_tags ct ON t.id = ct.tag_id
                WHERE ct.code_id = ?
            ''', (id,)).fetchall()
            code_dict['tags'] = [dict(tag) for tag in tags]
            conn.close()
            return code_dict
        conn.close()
        response.status = 404
        return {'error': 'Code not found'}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/codes/<id:int>/execute', method='POST')
def execute_code(id):
    try:
        conn = sqlite3.connect('codehaven.db')
        code_data = conn.execute('SELECT code, language FROM codes WHERE id = ?', (id,)).fetchone()
        conn.close()
        
        if not code_data:
            return {'success': False, 'error': 'Code not found'}
        
        code, language = code_data
        
        if language.lower() != 'python':
            return {'success': False, 'error': 'Only Python code can be executed'}
        
        # Security checks
        dangerous_imports = ['os.system', 'subprocess', 'eval(', 'exec(', '__import__', 'open(', 'file(']
        code_lower = code.lower()
        for dangerous in dangerous_imports:
            if dangerous in code_lower:
                return {'success': False, 'error': f'Security: "{dangerous}" not allowed'}
        
        # Create temp file in execution_temp folder
        import tempfile
        import subprocess
        import time
        import uuid
        
        exec_dir = os.path.abspath('execution_temp')
        if not os.path.exists(exec_dir):
            os.makedirs(exec_dir)
        
        temp_file = os.path.join(exec_dir, f'code_{uuid.uuid4().hex[:8]}.py')
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(code)
            
            start_time = time.time()
            
            # CRITICAL: Find Python executable
            import sys
            if getattr(sys, 'frozen', False):
                # For EXE - use system Python
                import shutil
                python_cmd = shutil.which('python') or shutil.which('python3') or 'python'
            else:
                # For script
                python_cmd = sys.executable
            
            result = subprocess.run(
                [python_cmd, temp_file],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=exec_dir
            )
            
            execution_time = round(time.time() - start_time, 3)
            
            return {
                'success': True,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'execution_time': f'{execution_time} seconds'
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Execution timeout (5 seconds)'}
        except FileNotFoundError:
            return {'success': False, 'error': 'Python not found! Please install Python on this computer.'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
                
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/codes', method='POST')
def add_code():
    try:
        category_id = request.forms.get('category_id')
        title = request.forms.get('title')
        code = request.forms.get('code')
        language = request.forms.get('language', 'text')
        tags_json = request.forms.get('tags', '[]')
        tags = json.loads(tags_json)
        zip_filename = None
        
        zip_file = request.files.get('zip_file')
        if zip_file and zip_file.filename.endswith('.zip'):
            import time
            timestamp = int(time.time())
            zip_filename = f"{timestamp}_{zip_file.filename}"
            zip_path = os.path.join(ZIP_DIR, zip_filename)
            zip_file.save(zip_path)
        
        conn = sqlite3.connect('codehaven.db')
        cursor = conn.execute('INSERT INTO codes (category_id, title, code, language, zip_filename, created_at) VALUES (?, ?, ?, ?, ?, datetime("now"))',
                     (category_id, title, code, language, zip_filename))
        code_id = cursor.lastrowid
        
        for tag_id in tags:
            conn.execute('INSERT OR IGNORE INTO code_tags (code_id, tag_id) VALUES (?, ?)', (code_id, tag_id))
            conn.execute('UPDATE tags SET usage_count = usage_count + 1 WHERE id = ?', (tag_id,))
        
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/codes/<id:int>', method='PUT')
def update_code(id):
    try:
        category_id = request.forms.get('category_id')
        title = request.forms.get('title')
        code = request.forms.get('code')
        language = request.forms.get('language', 'text')
        tags_json = request.forms.get('tags', '[]')
        tags = json.loads(tags_json)
        remove_zip = request.forms.get('remove_zip') == 'true'
        
        conn = sqlite3.connect('codehaven.db')
        
        current = conn.execute('SELECT zip_filename FROM codes WHERE id = ?', (id,)).fetchone()
        current_zip = current[0] if current else None
        zip_filename = current_zip
        
        zip_file = request.files.get('zip_file')
        if zip_file and zip_file.filename.endswith('.zip'):
            if current_zip:
                old_zip_path = os.path.join(ZIP_DIR, current_zip)
                if os.path.exists(old_zip_path):
                    os.remove(old_zip_path)
            import time
            timestamp = int(time.time())
            zip_filename = f"{timestamp}_{zip_file.filename}"
            zip_path = os.path.join(ZIP_DIR, zip_filename)
            zip_file.save(zip_path)
        elif remove_zip and current_zip:
            zip_path = os.path.join(ZIP_DIR, current_zip)
            if os.path.exists(zip_path):
                os.remove(zip_path)
            zip_filename = None
        
        conn.execute('UPDATE codes SET category_id=?, title=?, code=?, language=?, zip_filename=? WHERE id=?',
                     (category_id, title, code, language, zip_filename, id))
        
        conn.execute('DELETE FROM code_tags WHERE code_id = ?', (id,))
        for tag_id in tags:
            conn.execute('INSERT OR IGNORE INTO code_tags (code_id, tag_id) VALUES (?, ?)', (id, tag_id))
        
        conn.execute('UPDATE tags SET usage_count = (SELECT COUNT(*) FROM code_tags WHERE tag_id = tags.id)')
        
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/codes/<id:int>/download')
def download_zip(id):
    try:
        conn = sqlite3.connect('codehaven.db')
        code = conn.execute('SELECT zip_filename FROM codes WHERE id = ?', (id,)).fetchone()
        conn.close()
        if code and code[0]:
            zip_path = os.path.join(ZIP_DIR, code[0])
            if os.path.exists(zip_path):
                response.headers['Content-Type'] = 'application/zip'
                response.headers['Content-Disposition'] = f'attachment; filename="{code[0]}"'
                with open(zip_path, 'rb') as f:
                    return f.read()
        response.status = 404
        return {'error': 'ZIP file not found'}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

@route('/api/codes/<id:int>', method='DELETE')
def delete_code(id):
    try:
        conn = sqlite3.connect('codehaven.db')
        code = conn.execute('SELECT zip_filename FROM codes WHERE id = ?', (id,)).fetchone()
        if code and code[0]:
            zip_path = os.path.join(ZIP_DIR, code[0])
            if os.path.exists(zip_path):
                os.remove(zip_path)
        conn.execute('DELETE FROM codes WHERE id = ?', (id,))
        conn.execute('UPDATE tags SET usage_count = (SELECT COUNT(*) FROM code_tags WHERE tag_id = tags.id)')
        conn.commit()
        conn.close()
        return {'success': True}
    except Exception as e:
        response.status = 500
        return {'error': str(e)}

if __name__ == '__main__':
    print('\n' + '='*50)
    print(' CodeHaven - Smart Tags Edition!')
    print('='*50)
    print(' Opening Chrome automatically...')
    print(' http://localhost:8080')
    print(' ALL FEATURES PRESERVED:')
    print('    Categories System')
    print('    ZIP File Attachments')
    print('    Python Code Execution')
    print('    Syntax Highlighting (7 themes)')
    print('    Backup & Restore')
    print('    Statistics Dashboard')
    print('    Dark/Light Mode')
    print('    Mobile Responsive')
    print('')
    print(' NEW: Smart Tags System!')
    print('   - Create unlimited custom tags')
    print('   - Color-coded tags')
    print('   - Autocomplete suggestions')
    print('   - Filter by tags')
    print('   - Popular tags in sidebar')
    print('   - Tag manager with edit/delete')
    print('')
    print('='*50)
    
   
    run(host='0.0.0.0', port=8080, debug=True, reloader=True)