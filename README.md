# Cortex Personal Assistant

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Cortex is a voice-controlled personal assistant built with Python that can perform various tasks like setting reminders, managing to-do lists, searching the web, and more.

## Features

- **Voice Interaction**: Speak naturally to control the assistant
- **Task Management**: Create, update, and track tasks with due dates and priorities
- **Reminders**: Set reminders that trigger at specific times
- **Web Search**: Search Google, YouTube, and Maps with voice commands
- **Time/Date**: Get current time, date, and day information
- **Advice**: Get random pieces of advice
- **Customizable**: Adjust voice, name, and other preferences
- **Persistent Storage**: All data is saved between sessions

## Installation

### Prerequisites

- Python 3.10 or higher
- pip package manager

### Dependencies

Install required packages:

```bash
pip install SpeechRecognition pyttsx3 playsound3 gTTS
```

### Additional Setup

For speech recognition, you may need to install:

- **macOS**: `brew install portaudio`
- **Linux**: `sudo apt-get install python3-pyaudio`
- **Windows**: PyAudio should install automatically via pip

## Usage

### Starting the Assistant

Run the assistant with:

```bash
python cortex_assistant.py
```

### Basic Commands

Here are some example commands you can use:

- **Greeting**: "Hello", "Hey Cortex"
- **Time/Date**: "What time is it?", "What's the date today?"
- **Tasks**:
  - "Add task buy groceries due tomorrow at 5pm with high priority"
  - "Update task 1 status completed"
  - "Delete task 2"
  - "Show all tasks"
- **Reminders**: "Set a reminder to call mom at 18:30"
- **Search**:
  - "Search YouTube for Python tutorials"
  - "Google machine learning basics"
  - "Find directions to Central Park"
- **Advice**: "Give me some advice"
- **Exit**: "Goodbye", "Exit"

## Configuration

The assistant automatically creates a configuration directory at `~/.cortex_assistant` where it stores:

- User preferences
- Task lists
- Reminders
- Advice database

You can customize settings by editing the files in this directory or through voice commands.

## Troubleshooting

### Common Issues

1. **Microphone not working**:
   - Check your microphone settings
   - Ensure no other application is using the microphone

2. **Speech recognition errors**:
   - Speak clearly in a quiet environment
   - Check your internet connection (Google Speech Recognition requires internet)

3. **Text-to-speech issues**:
   - On Linux, ensure you have espeak installed
   - On Windows/Mac, ensure your system voices are properly configured

### Logs

The assistant creates a log file at `personal_assistant.log` which can help diagnose issues.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Disclaimer

This is a personal project intended for educational purposes. The developer makes no guarantees about the reliability or security of this software. Use at your own risk.
