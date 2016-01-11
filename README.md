# SQL*Plus plugin for Sublime Text 3

Ever been annoyed by Oracle SQL*Plus’s lack of text editing features? Love Sublime Text?
This plugin is for you.

# Features
* Both input and output are selectable and editable.
* Commands history.
* Auto-completion of script filenames in workdir.
* Syntax highlighting for SQL and PL/SQL included.
* One tab - one SQL*Plus subprocess. Auto-termination on tab close.
* Do whatever you would do in SQL*Plus without leaving Sublime Text window.

# Installation
* With [Package Control](http://wbond.net/sublime_packages/package_control): Run `Package Control: Install Package` command, find and install `SQLPlus` plugin.
* Manual: Clone this repo to your Packages folder.
* Edit `SQLPlus.sublime-settings` and set path to your SQL*Plus executeable and working directory.
* *(Optional)* In a new tab in Sublime Text type `prompt Hello World!` and hit `Ctrl+F8`

## How it works?
This plugin redirects input and output between Sublime Text and SQL*Plus.

# Usage
* `Ctrl+F8` - execute the selected text or current line (if nothing selected) in SQL\*Plus. In case of multiple selections only the first selection is sent to SQL*Plus.
* `Alt+Up` - replace selection with previous command in history
* `Alt+Down` - replace selection with next command in history

# Problems
* Tested only on Windows
