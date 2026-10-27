VibeWeather - Your Mood as a Weather Forecast

COMP9001 Final Project

This project is a simple mood journal application called VibeWeather. Users can write short English diary entries, and the program will automatically calculate three mood scores: stress, vitality, and calmness. Based on these scores, the program converts the user’s daily mood into different weather conditions such as Sunny, Rainy, Stormy, and more.

1. How to Run the Program

Please run the file below:

(1) main.py (GUI main program)

Optional files:

(2) cli.py: text-based menu version without GUI

(3) test_vibeweather.py: unit testing file (total 57 tests)

All Python files must be kept in the same folder to work correctly.

2. Important Notes for Tutors

(1) This project only uses Python built-in standard libraries. No external pip packages are installed.

(2) The main program (main.py) is a tkinter GUI application with canvas drawing and simple animations. It cannot run on Ed terminal, so please run it locally.

(3) No audio, video, or network functions are used in this project. The program works completely offline.

(4) cli.py and test_vibeweather.py do not use tkinter and can run normally on Ed.

3. Running Environment Requirements

(1) Python version: 3.10 or above (tested on Python 3.14)

(2) Must have tkinter installed (usually included with official Python installations)

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

(1) journal.json: stores all diary entries

(2) custom_lexicon.json: stores user-added custom mood words

(3) .bak files: automatic backup files

If the custom word file is missing, the program still runs normally with the default built-in mood word list. If any data file is corrupted, the program will show a warning and run safely in read-only mode.

6. Basic Program Usage Guide

(1) Write a short diary entry and click Analyse & save. The program will generate mood scores and a corresponding weather result.

(2) The scoring system considers sentence context, including words like but, although, not, very. The same words in different orders will produce different results.

(3) Click Load demo week to load sample entries, which fills the history list, trend chart, and mood statistics.

(4) Main functions:

    ① Keywords: add or delete custom mood words

    ② Re-score all: recalculate scores for all saved entries

    ③ View / Delete: check or delete saved diary entries

    ④ Newest / Intensity: change the sorting method of history records

7. Project File Structure

(1) main.py: GUI window and all button functions

(2) widgets.py: reusable GUI components and card layouts

(3) drawing.py: colour settings and weather drawing functions

(4) analysis.py: mood scoring logic and weather classification rules

(5) journal.py: entry structure, constants, and custom error classes

(6) storage.py: file reading, writing, and safe data saving logic

(7) cli.py: text-based program version

(8) test_vibeweather.py: unit tests for core functions
