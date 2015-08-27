# SQL*Plus plugin for Sublime Text

Ever been annoyed by Oracle SQL*Plus’s lack of text editing features? Love Sublime Text?
This plugin is for you.

# Installation
1. Clone this repo to your Packages folder.
2. Edit `SQLPlus.sublime-settings` and set path to your SQL*Plus executeable and working directory.
3. *(Optional)* In a new tab in Sublime Text type `prompt Hello World!` and hit `Ctrl+F8`

## How it works?
This plugin redirects input and output between Sublime Text and SQL*Plus.

# Usage
* `Ctrl+F8` - execute the selected text or current line (if nothing selected) in SQL\*Plus. In case of multiple selections only the first selection is sent to SQL*Plus.
* `Alt+Up` - replace selection with previous command in history
* `Alt+Down` - replace selection with next command in history

