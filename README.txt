VibeWeather - Your Mood as a Weather Forecast

COMP9001 Final Project

This project is a simple mood journal application called VibeWeather. Users can write short English diary entries, and the program will automatically calculate three mood scores: stress, vitality, and calmness. Based on these scores, the program converts the user’s daily mood into different weather conditions such as Sunny, Rainy, Stormy, and more.

1. How to Run the Program

Please run the file below:

• main.py (GUI main program)

Optional files:

• cli.py: text-based menu version without GUI

• test_vibeweather.py: unit testing file (total 57 tests)

All Python files must be kept in the same folder to work correctly.

2. Important Notes for Tutors

• This project only uses Python built-in standard libraries. No external pip packages are installed.

• The main program (main.py) is a tkinter GUI application with canvas drawing and simple animations. It cannot run on Ed terminal, so please run it locally.

• No audio, video, or network functions are used in this project. The program works completely offline.

• cli.py and test_vibeweather.py do not use tkinter and can run normally on Ed.

3. Running Environment Requirements

• Python version: 3.10 or above (tested on Python 3.14)

• Must have tkinter installed (usually included with official Python installations)

You can test tkinter using:
python3 -m tkinter
4. Running Instructions

Open your terminal in the project folder and run:

GUI version (main program):
python3 main.py
Text menu version:
python3 cli.py
Unit tests:
python3 test_vibeweather.py
Expected output: Ran 57 tests ... OK

5. Data File Explanation

The program automatically creates a data folder to store user data after the first save.

Files inside the data folder:

• journal.json: stores all diary entries

• custom_lexicon.json: stores user-added custom mood words

• .bak files: automatic backup files

If the custom word file is missing, the program still runs normally with the default built-in mood word list. If any data file is corrupted, the program will show a warning and run safely in read-only mode.

6. Basic Program Usage Guide

1. Write a short diary entry and click Analyse & save. The program will generate mood scores and a corresponding weather result.

2. The scoring system considers sentence context, including words like but, although, not, very. The same words in different orders will produce different results.

3. Click Load demo week to load sample entries, which fills the history list, trend chart, and mood statistics.

4. Main functions:

◦ Keywords: add or delete custom mood words

◦ Re-score all: recalculate scores for all saved entries

◦ View / Delete: check or delete saved diary entries

◦ Newest / Intensity: change the sorting method of history records

7. Project File Structure

• main.py: GUI window and all button functions

• widgets.py: reusable GUI components and card layouts

• drawing.py: colour settings and weather drawing functions

• analysis.py: mood scoring logic and weather classification rules

• journal.py: entry structure, constants, and custom error classes

• storage.py: file reading, writing, and safe data saving logic

• cli.py: text-based program version

• test_vibeweather.py: unit tests for core functions