import speech_recognition as sr
import pyttsx3
import random
import playsound3
import webbrowser
import os
import re
import logging
import tempfile
import json
import datetime
import sys
from gtts import gTTS
from time import ctime
import threading

# Configure logging with rotating file handler
logging.basicConfig(
    filename='personal_assistant.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='a'
)

# Custom Exception classes
class PersonalAssistantError(Exception):
    """Base exception for Personal Assistant errors."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class ConfigurationError(PersonalAssistantError):
    """Exception raised for configuration errors."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class SpeechRecognitionError(PersonalAssistantError):
    """Exception raised for speech recognition errors."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

class StorageError(PersonalAssistantError):
    """Exception raised for storage-related errors."""
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

# Storage Manager class to handle all file operations
class StorageManager:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.path.join(os.path.expanduser('~'), '.cortex_assistant')
        self._ensure_data_directory()
        self.cache = {}
        
    def _ensure_data_directory(self):
        """Ensure the data directory exists."""
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
                logging.info(f"Created data directory at {self.data_dir}")
            except OSError as e:
                logging.error(f"Failed to create data directory: {e}")
                raise StorageError(f"Failed to create data directory: {e}")
    
    def get_file_path(self, filename):
        """Get the full path for a file."""
        return os.path.join(self.data_dir, filename)
    
    def save_data(self, filename, data):
        """Save data to a JSON file with error handling."""
        file_path = self.get_file_path(filename)
        try:
            # Write to a temporary file first, then move it
            temp_file = file_path + '.tmp'
            with open(temp_file, 'a') as f:
                json.dump(data, f, indent=4)
            # On Windows, we need to remove the destination file first
            if os.path.exists(file_path):
                os.remove(file_path)
            os.rename(temp_file, file_path)
            self.cache[filename] = data
            return True
        except (IOError, OSError) as e:
            logging.error(f"Error saving data to {filename}: {e}")
            raise StorageError(f"Error saving data: {e}")
    
    def load_data(self, filename, default=None):
        """Load data from a JSON file with caching and error handling."""
        if filename in self.cache:
            return self.cache[filename]
            
        file_path = self.get_file_path(filename)
        if not os.path.exists(file_path):
            logging.info(f"File {filename} not found, returning default value")
            return default if default is not None else {}
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                self.cache[filename] = data
                return data
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON from {filename}: {e}")
            return default if default is not None else {}
        except IOError as e:
            logging.error(f"IO Error reading {filename}: {e}")
            raise StorageError(f"Error reading data: {e}")

# VoiceEngine class to handle speech recognition and text-to-speech
class VoiceEngine:
    def __init__(self, tts_language='en', tts_voice='female'):
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.tts_language = tts_language
        self.tts_voice = tts_voice
        self._set_voice()
        
    def _set_voice(self):
        """Set the voice for text-to-speech."""
        try:
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if self.tts_voice.lower() in voice.name.lower():
                    self.engine.setProperty('voice', voice.id)
                    logging.info(f"Selected voice: {voice.name}")
                    return
            
            # Default to first female or male voice if preferred voice not found
            for voice in voices:
                if (self.tts_voice == 'female' and 'female' in voice.name.lower()) or \
                   (self.tts_voice == 'male' and 'male' in voice.name.lower()):
                    self.engine.setProperty('voice', voice.id)
                    logging.info(f"Selected fallback voice: {voice.name}")
                    return
                    
            logging.warning("Requested voice type not found. Using default voice.")
        except Exception as e:
            logging.error(f"Error setting voice: {e}")
            # Continue with default voice
    
    def listen(self, timeout=None, phrase_time_limit=None):
        """Record audio and return the transcribed text."""
        with sr.Microphone() as source:
            logging.info("Listening for audio...")
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                voice_data = self.recognizer.recognize_google(audio)
                logging.info(f"Recognized: {voice_data}")
                return voice_data.lower()
            except sr.UnknownValueError:
                logging.info("Speech not recognized")
                raise SpeechRecognitionError("Sorry, I didn't catch that.")
            except sr.RequestError as e:
                logging.error(f"Google Speech Recognition service error: {e}")
                raise SpeechRecognitionError("Sorry, my speech service is down.")
            except Exception as e:
                logging.error(f"Error in speech recognition: {e}")
                raise SpeechRecognitionError("An error occurred while listening.")
    
    def speak(self, message):
        """Speak the message using text-to-speech."""
        if not message:
            return
            
        try:
            # Try using gTTS first (better quality but requires internet)
            tts = gTTS(text=message, lang=self.tts_language)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                temp_path = temp_file.name
            
            tts.save(temp_path)
            playsound3.playsound(temp_path)
            logging.info(f"Assistant says (gTTS): {message}")
            os.remove(temp_path)
        except Exception as e:
            logging.error(f"Error in gTTS: {e}. Falling back to pyttsx3.")
            # Fallback to offline pyttsx3
            try:
                self.engine.say(message)
                self.engine.runAndWait()
                logging.info(f"Assistant says (pyttsx3): {message}")
            except Exception as e2:
                logging.error(f"Error in pyttsx3: {e2}")

# TaskManager class to handle task-related operations
class TaskManager:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.tasks_file = 'tasks.json'
        self.tasks = self._load_tasks()
        
    def _load_tasks(self):
        """Load tasks from storage."""
        return self.storage_manager.load_data(self.tasks_file, default=[])
    
    def _save_tasks(self):
        """Save tasks to storage."""
        return self.storage_manager.save_data(self.tasks_file, self.tasks)
    
    def add_task(self, description, due_date, priority):
        """Add a new task."""
        task = {
            'task': description,
            'due_date': due_date,
            'priority': priority,
            'status': 'pending',
            'created_at': datetime.datetime.now().isoformat()
        }
        self.tasks.append(task)
        self._save_tasks()
        return len(self.tasks) - 1  # Return the task ID
    
    def update_task(self, task_id, updates):
        """Update an existing task."""
        if not 0 <= task_id < len(self.tasks):
            raise ValueError(f"Task ID {task_id} not found.")
            
        task = self.tasks[task_id]
        for key, value in updates.items():
            if key in task:
                task[key] = value
                
        self.tasks[task_id] = task
        self._save_tasks()
        return task
    
    def delete_task(self, task_id):
        """Delete a task."""
        if not 0 <= task_id < len(self.tasks):
            raise ValueError(f"Task ID {task_id} not found.")
            
        deleted_task = self.tasks.pop(task_id)
        self._save_tasks()
        return deleted_task
    
    def search_tasks(self, keyword):
        """Search for tasks by keyword."""
        try:
            pattern = re.compile(keyword, re.IGNORECASE)
            return [(i, task) for i, task in enumerate(self.tasks) 
                   if 'task' in task and pattern.search(task['task'])]
        except re.error:
            # Handle invalid regex pattern
            return [(i, task) for i, task in enumerate(self.tasks) 
                   if 'task' in task and keyword.lower() in task['task'].lower()]
    
    def get_all_tasks(self):
        """Get all tasks."""
        return [(i, task) for i, task in enumerate(self.tasks)]
    
    def get_task(self, task_id):
        """Get a specific task."""
        if not 0 <= task_id < len(self.tasks):
            raise ValueError(f"Task ID {task_id} not found.")
        return self.tasks[task_id]

# ReminderManager class to handle reminder-related operations
class ReminderManager:
    def __init__(self, storage_manager, voice_engine):
        self.storage_manager = storage_manager
        self.voice_engine = voice_engine
        self.reminders_file = 'reminders.json'
        self.reminders = self._load_reminders()
        self.reminder_thread = None
        self.stop_event = threading.Event()
        
    def _load_reminders(self):
        """Load reminders from storage."""
        return self.storage_manager.load_data(self.reminders_file, default=[])
    
    def _save_reminders(self):
        """Save reminders to storage."""
        return self.storage_manager.save_data(self.reminders_file, self.reminders)
    
    def add_reminder(self, text, time_str):
        """Add a new reminder."""
        try:
            # Parse the time
            reminder_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            
            # Create the reminder
            now = datetime.datetime.now()
            reminder_datetime = datetime.datetime.combine(now.date(), reminder_time)
            
            # If the time has already passed today, set it for tomorrow
            if reminder_datetime < now:
                reminder_datetime += datetime.timedelta(days=1)
                
            reminder = {
                'text': text,
                'time': reminder_time.strftime("%H:%M:%S"),
                'created_at': now.isoformat(),
                'active': True
            }
            
            self.reminders.append(reminder)
            self._save_reminders()
            return reminder
        except ValueError:
            raise ValueError("Invalid time format. Please use HH:MM format.")
    
    def check_reminders(self):
        """Check for due reminders."""
        now = datetime.datetime.now()
        current_time = now.time()
        reminders_to_remove = []
        
        for reminder in self.reminders:
            if not reminder.get('active', True):
                continue
                
            reminder_time = datetime.datetime.strptime(reminder['time'], "%H:%M:%S").time()
            
            # Check if the reminder time is within the last minute
            time_diff = datetime.datetime.combine(datetime.date.today(), current_time) - \
                       datetime.datetime.combine(datetime.date.today(), reminder_time)
                       
            if abs(time_diff.total_seconds()) < 60:
                self.voice_engine.speak(f"Reminder: {reminder['text']}")
                reminder['active'] = False
                reminders_to_remove.append(reminder)
        
        # Remove processed reminders
        for reminder in reminders_to_remove:
            self.reminders.remove(reminder)
            
        self._save_reminders()
    
    def start_reminder_checker(self):
        """Start a thread to periodically check reminders."""
        def check_loop():
            while not self.stop_event.is_set():
                try:
                    self.check_reminders()
                except Exception as e:
                    logging.error(f"Error checking reminders: {e}")
                # Check every 30 seconds
                self.stop_event.wait(30)
        
        self.stop_event.clear()
        self.reminder_thread = threading.Thread(target=check_loop, daemon=True)
        self.reminder_thread.start()
    
    def stop_reminder_checker(self):
        """Stop the reminder checker thread."""
        if self.reminder_thread:
            self.stop_event.set()
            self.reminder_thread.join(timeout=1)

# NLPEngine class for natural language processing
class NLPEngine:
    def __init__(self):
        self.command_patterns = {
            'greeting': r'\b(?:hey|hi|hello)\b',
            'name_query': r'\b(?:what is your name|what\'s your name|tell me your name)\b',
            'name_update': r'\bmy name is\s+([\w\s]+)',
            'time_query': r'\b(?:what\'s the time|what is the time|time please|current time)\b',
            'date_query': r'\b(?:what\'s the date|what is the date|date please|current date)\b',
            'day_query': r'\b(?:what\'s the day|what is the day|day please|current day)\b',
            'search_youtube': r'\b(?:search|look up|find)\s+(?:on\s+)?youtube\s+(?:for|about\s+)?(.+)',
            'search_google': r'\b(?:search|look up|google)\s+(?!on\s+youtube)(?:for|about\s+)?(.+)',
            'search_maps': r'\b(?:find|locate|show|search)\s+(?:location|place|address|directions|map)\s+(?:for|to|of\s+)?(.+)',
            'weather_query': r'\b(?:weather|temperature|forecast)\s+(?:for|in\s+)?(.+)',
            'task_add': r'\b(?:add|create|new)\s+task\s+(.+)',
            'task_update': r'\b(?:update|modify|change|edit)\s+task\s+(\d+)\s+(.+)',
            'task_delete': r'\b(?:delete|remove)\s+task\s+(\d+)\b',
            'task_search': r'\b(?:search|find|look for)\s+task\s+(.+)',
            'task_view': r'\b(?:view|show|list|get)\s+(?:all\s+)?tasks\b',
            'advice_query': r'\b(?:give|tell|share)\s+(?:me\s+)?(?:some\s+)?advice\b',
            'reminder_add': r'\b(?:set|add|create)\s+(?:a\s+)?reminder\s+(?:for|to\s+)?(.+)\s+at\s+(\d{1,2}:\d{2})\b',
            'exit': r'\b(?:exit|quit|goodbye|bye|stop|end)\b'
        }
    
    def parse_command(self, text):
        """Parse user input using explicit if statements for each command."""
        if match := re.search(self.command_patterns['greeting'], text, re.IGNORECASE):
            return {'command': 'greeting', 'params': {}}

        if match := re.search(self.command_patterns['name_query'], text, re.IGNORECASE):
            return {'command': 'name_query', 'params': {}}

        if match := re.search(self.command_patterns['name_update'], text, re.IGNORECASE):
            return {'command': 'name_update', 'params': {'name': match.group(1).strip()}}

        if match := re.search(self.command_patterns['time_query'], text, re.IGNORECASE):
            return {'command': 'time_query', 'params': {}}
        
        if match := re.search(self.command_patterns['date_query'], text, re.IGNORECASE):
            return {'command': 'date_query', 'params': {}}
        
        if match := re.search(self.command_patterns['day_query'], text, re.IGNORECASE):
            return {'command': 'day_query', 'params': {}}

        if match := re.search(self.command_patterns['task_search'], text, re.IGNORECASE):
            return {'command': 'task_search', 'params': {'query': match.group(1).strip()}}

        if match := re.search(self.command_patterns['search_youtube'], text, re.IGNORECASE):
            return {'command': 'search_youtube', 'params': {'query': match.group(1).strip()}}

        if match := re.search(self.command_patterns['search_google'], text, re.IGNORECASE):
            return {'command': 'search_google', 'params': {'query': match.group(1).strip()}}

        if match := re.search(self.command_patterns['search_maps'], text, re.IGNORECASE):
            return {'command': 'search_maps', 'params': {'query': match.group(1).strip()}}

        if match := re.search(self.command_patterns['weather_query'], text, re.IGNORECASE):
            return {'command': 'weather_query', 'params': {'query': match.group(1).strip()}}

        if match := re.search(self.command_patterns['task_add'], text, re.IGNORECASE):
            return {'command': 'task_add', 'params': {'query': match.group(1).strip()}}

        if match := re.search(self.command_patterns['task_update'], text, re.IGNORECASE):
            return {'command': 'task_update', 'params': {'task_id': match.group(1), 'details': match.group(2).strip()}}

        if match := re.search(self.command_patterns['task_delete'], text, re.IGNORECASE):
            return {'command': 'task_delete', 'params': {'task_id': match.group(1)}}

        if match := re.search(self.command_patterns['task_view'], text, re.IGNORECASE):
            return {'command': 'task_view', 'params': {}}

        if match := re.search(self.command_patterns['advice_query'], text, re.IGNORECASE):
            return {'command': 'advice_query', 'params': {}}

        if match := re.search(self.command_patterns['reminder_add'], text, re.IGNORECASE):
            return {'command': 'reminder_add', 'params': {'text': match.group(1).strip(), 'time': match.group(2)}} 

        if match := re.search(self.command_patterns['exit'], text, re.IGNORECASE):
            return {'command': 'exit', 'params': {}}

        return {'command': 'unknown', 'params': {'text': text}}

    def extract_task_details(self, details_text):
        """Extract structured task details from text."""
        # Parse the task description, due date, time, and priority
        due_match = re.search(r'due\s+(?:on\s+)?(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{1,2}/\d{2})\s+(?:at\s+)?(\d{1,2}:\d{2}(?:\s*[ap]m)?)', details_text, re.IGNORECASE)
        priority_match = re.search(r'(?:with\s+)?priority\s+(low|medium|high)', details_text, re.IGNORECASE)
        
        # Extract details
        due_date = None
        due_time = None
        if due_match:
            date_str = due_match.group(1)
            time_str = due_match.group(2)
            
            # Parse different date formats
            try:
                if '-' in date_str:
                    due_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                elif len(date_str.split('/')[-1]) == 4:
                    due_date = datetime.datetime.strptime(date_str, "%m/%d/%Y").date()
                else:
                    due_date = datetime.datetime.strptime(date_str, "%m/%d/%y").date()
                    
                # Parse time
                if 'am' in time_str.lower() or 'pm' in time_str.lower():
                    due_time = datetime.datetime.strptime(time_str, "%I:%M%p").time()
                else:
                    due_time = datetime.datetime.strptime(time_str, "%H:%M").time()
            except ValueError:
                # If parsing fails, return None for these values
                pass
        
        # Set priority
        priority = priority_match.group(1).lower() if priority_match else "medium"
        
        # Find task description by removing date, time and priority parts
        description = details_text
        if due_match:
            description = description.replace(due_match.group(0), "")
        if priority_match:
            description = description.replace(priority_match.group(0), "")
        description = description.strip()
        
        # Combine date and time
        due_datetime = None
        if due_date and due_time:
            due_datetime = datetime.datetime.combine(due_date, due_time).isoformat()
        
        return {
            'description': description,
            'due_date': due_datetime,
            'priority': priority
        }

    def extract_task_updates(self, details_text):
        """Extract task update details from text."""
        updates = {}
        
        # Extract due date and time
        due_match = re.search(r'due\s+(?:on\s+)?(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}/\d{1,2}/\d{2})\s+(?:at\s+)?(\d{1,2}:\d{2}(?:\s*[ap]m)?)', details_text, re.IGNORECASE)
        if due_match:
            date_str = due_match.group(1)
            time_str = due_match.group(2)
            
            try:
                # Parse date
                if '-' in date_str:
                    due_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                elif len(date_str.split('/')[-1]) == 4:
                    due_date = datetime.datetime.strptime(date_str, "%m/%d/%Y").date()
                else:
                    due_date = datetime.datetime.strptime(date_str, "%m/%d/%y").date()
                    
                # Parse time
                if 'am' in time_str.lower() or 'pm' in time_str.lower():
                    due_time = datetime.datetime.strptime(time_str, "%I:%M%p").time()
                else:
                    due_time = datetime.datetime.strptime(time_str, "%H:%M").time()
                    
                # Combine date and time
                updates['due_date'] = datetime.datetime.combine(due_date, due_time).isoformat()
            except ValueError:
                pass
        
        # Extract priority
        priority_match = re.search(r'(?:with\s+)?priority\s+(low|medium|high)', details_text, re.IGNORECASE)
        if priority_match:
            updates['priority'] = priority_match.group(1).lower()
        
        # Extract status
        status_match = re.search(r'status\s+(completed|pending|in progress)', details_text, re.IGNORECASE)
        if status_match:
            updates['status'] = status_match.group(1).lower()
        
        return updates

# AdviceManager class for managing advice
class AdviceManager:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.advice_file = 'advice.json'
        self.advice_list = self._load_advice()
        
    def _load_advice(self):
        """Load advice from storage."""
        return self.storage_manager.load_data(self.advice_file, default=[])
    
    def get_random_advice(self):
        """Get a random piece of advice."""
        if not self.advice_list:
            return "I don't have any advice to offer at the moment."
        return random.choice(self.advice_list)
    
    def add_advice(self, advice):
        """Add a new piece of advice."""
        if advice not in self.advice_list:
            self.advice_list.append(advice)
            self.storage_manager.save_data(self.advice_file, self.advice_list)
            return True
        return False

# UserPreferences class to manage user settings
class UserPreferences:
    def __init__(self, storage_manager):
        self.storage_manager = storage_manager
        self.preferences_file = 'user_preferences.json'
        self.preferences = self._load_preferences()
        
    def _load_preferences(self):
        """Load user preferences from storage."""
        default_preferences = {
            'name': 'User',
            'voice_language': 'en',
            'voice_gender': 'female',
            'wake_word': 'hey cortex',
            'reminder_check_interval': 30,
            'timezone': 'local'
        }
        
        stored_prefs = self.storage_manager.load_data(self.preferences_file, default={})
        # Merge defaults with stored preferences
        for key, value in default_preferences.items():
            if key not in stored_prefs:
                stored_prefs[key] = value
                
        return stored_prefs
    
    def save_preferences(self):
        """Save user preferences to storage."""
        return self.storage_manager.save_data(self.preferences_file, self.preferences)
    
    def get_preference(self, key, default=None):
        """Get a specific preference."""
        return self.preferences.get(key, default)
    
    def set_preference(self, key, value):
        """Set a specific preference."""
        self.preferences[key] = value
        self.save_preferences()
        return value

# Main PersonalAssistant class that coordinates all components
class PersonalAssistant:
    def __init__(self, data_dir=None):
        # Initialize core components
        self.storage_manager = StorageManager(data_dir)
        self.user_preferences = UserPreferences(self.storage_manager)
        
        # Load voice preferences
        voice_language = self.user_preferences.get_preference('voice_language', 'en')
        voice_gender = self.user_preferences.get_preference('voice_gender', 'female')
        
        # Initialize voice engine with preferences
        self.voice_engine = VoiceEngine(tts_language=voice_language, tts_voice=voice_gender)
        
        # Initialize other components
        self.nlp_engine = NLPEngine()
        self.task_manager = TaskManager(self.storage_manager)
        self.reminder_manager = ReminderManager(self.storage_manager, self.voice_engine)
        self.advice_manager = AdviceManager(self.storage_manager)
        
        # State variables
        self.running = False
        self.waiting_for_response = False
        self.follow_up_context = None
    
    def _format_task_for_speech(self, task_id, task):
        """Format a task for speech output."""
        result = f"Task ID {task_id}: {task.get('task', 'No description')}"
        
        if 'due_date' in task and task['due_date']:
            try:
                due_date = datetime.datetime.fromisoformat(task['due_date'])
                result += f", Due: {due_date.strftime('%B %d at %I:%M %p')}"
            except (ValueError, TypeError):
                result += f", Due: {task.get('due_date', 'No due date')}"
                
        result += f", Priority: {task.get('priority', 'No priority')}"
        result += f", Status: {task.get('status', 'No status')}"
        
        return result
    
    def handle_command(self, command_data):
        """Handle a parsed command."""
        command = command_data['command']
        params = command_data['params']
        
        # Handle different commands
        if command == 'greeting':
            user_name = self.user_preferences.get_preference('name', 'User')
            greetings = [
                f"Hey {user_name}, how can I help you?", 
                f"Hello {user_name}!", 
                "I'm here to help. What do you need?", 
                "How can I assist you today?"
            ]
            self.voice_engine.speak(random.choice(greetings))
            
        elif command == 'name_query':
            user_name = self.user_preferences.get_preference('name', 'User')
            self.voice_engine.speak(f"My name is Cortex. You're {user_name}.")
            
        elif command == 'name_update':
            name = params.get('name', '')
            if name:
                self.user_preferences.set_preference('name', name)
                self.voice_engine.speak(f"Okay, I'll remember that your name is {name}.")
            
        elif command == 'time_query':
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            self.voice_engine.speak(f"The current time is {current_time}.")
        
        elif command == 'date_query':
            current_date = datetime.datetime.now().strftime("%B %d, %Y")
            self.voice_engine.speak(f"The current date is {current_date}.")

        elif command == 'day_query':
            current_day = datetime.datetime.now().strftime("%A")
            self.voice_engine.speak(f"The current day is {current_day}.")
            
        elif command == 'search_google':
            query = params.get('query', '')
            if query:
                url = f"https://google.com/search?q={query}"
                webbrowser.get().open(url)
                self.voice_engine.speak(f"Here is what I found for {query} on Google.")
            else:
                self.voice_engine.speak("What would you like me to search for?")
                
        elif command == 'search_youtube':
            query = params.get('query', '')
            if query:
                url = f"https://www.youtube.com/results?search_query={query}"
                webbrowser.get().open(url)
                self.voice_engine.speak(f"Here is what I found for {query} on YouTube.")
            else:
                self.voice_engine.speak("What would you like me to search for on YouTube?")
                
        elif command == 'search_maps':
            query = params.get('query', '')
            if query:
                url = f"https://google.com/maps/place/{query}"
                webbrowser.get().open(url)
                self.voice_engine.speak(f"Here is the location for {query} on Google Maps.")
            else:
                self.voice_engine.speak("What location would you like me to find?")
                
        elif command == 'weather_query':
            location = params.get('location', '')
            if location:
                url = f"https://google.com/search?q={location} weather"
                webbrowser.get().open(url)
                self.voice_engine.speak(f"Here is the weather for {location}.")
            else:
                self.voice_engine.speak("What location would you like the weather for?")
                
        elif command == 'task_add':
            details = params.get('details', '')
            if details:
                task_data = self.nlp_engine.extract_task_details(details)
                if task_data['description']:
                    try:
                        task_id = self.task_manager.add_task(
                            task_data['description'],
                            task_data['due_date'],
                            task_data['priority']
                        )
                        self.voice_engine.speak(f"Task added with ID {task_id}.")
                    except Exception as e:
                        logging.error(f"Error adding task: {e}")
                        self.voice_engine.speak("Sorry, I couldn't add that task.")
                else:
                    self.voice_engine.speak("I couldn't understand the task details. Please try again.")
        elif command == 'task_update':
            try:
                task_id = int(params.get('task_id', '0'))
                details = params.get('details', '')
                if details:
                    updates = self.nlp_engine.extract_task_updates(details)
                    if updates:
                        updated_task = self.task_manager.update_task(task_id, updates)
                        self.voice_engine.speak(f"Task {task_id} updated successfully.")
                    else:
                        self.voice_engine.speak("I couldn't understand the update details.")
                else:
                    self.voice_engine.speak("Please provide details for the task update.")
            except ValueError:
                self.voice_engine.speak("Please provide a valid task ID.")
            except Exception as e:
                logging.error(f"Error updating task: {e}")
                self.voice_engine.speak(f"Sorry, I couldn't update that task: {str(e)}")
                
        elif command == 'task_delete':
            try:
                task_id = int(params.get('task_id', '0'))
                self.task_manager.delete_task(task_id)
                self.voice_engine.speak(f"Task {task_id} deleted successfully.")
            except ValueError as e:
                self.voice_engine.speak(f"Error: {str(e)}")
            except Exception as e:
                logging.error(f"Error deleting task: {e}")
                self.voice_engine.speak("Sorry, I couldn't delete that task.")
                
        elif command == 'task_search':
            keyword = params.get('keyword', '')
            if keyword:
                try:
                    tasks = self.task_manager.search_tasks(keyword)
                    if tasks:
                        self.voice_engine.speak(f"Found {len(tasks)} tasks matching '{keyword}':")
                        for task_id, task in tasks[:3]:  # Limit to first 3 for speech
                            task_info = self._format_task_for_speech(task_id, task)
                            self.voice_engine.speak(task_info)
                        if len(tasks) > 3:
                            self.voice_engine.speak(f"And {len(tasks) - 3} more. Would you like to hear the rest?")
                            self.follow_up_context = {'action': 'continue_task_list', 'tasks': tasks, 'current_index': 3}
                    else:
                        self.voice_engine.speak(f"No tasks found matching '{keyword}'.")
                except Exception as e:
                    logging.error(f"Error searching tasks: {e}")
                    self.voice_engine.speak("Sorry, I encountered an error while searching for tasks.")
            else:
                self.voice_engine.speak("What keyword would you like to search for?")
                
        elif command == 'task_view':
            try:
                tasks = self.task_manager.get_all_tasks()
                if tasks:
                    self.voice_engine.speak(f"You have {len(tasks)} tasks:")
                    for task_id, task in tasks[:3]:  # Limit to first 3 for speech
                        task_info = self._format_task_for_speech(task_id, task)
                        self.voice_engine.speak(task_info)
                    if len(tasks) > 3:
                        self.voice_engine.speak(f"And {len(tasks) - 3} more. Would you like to hear the rest?")
                        self.follow_up_context = {'action': 'continue_task_list', 'tasks': tasks, 'current_index': 3}
                else:
                    self.voice_engine.speak("You don't have any tasks yet.")
            except Exception as e:
                logging.error(f"Error viewing tasks: {e}")
                self.voice_engine.speak("Sorry, I encountered an error while retrieving your tasks.")
                
        elif command == 'advice_query':
            advice = self.advice_manager.get_random_advice()
            self.voice_engine.speak(f"Here's some advice: {advice}")
            
        elif command == 'reminder_add':
            text = params.get('text', '')
            time_str = params.get('time', '')
            
            if text and time_str:
                try:
                    reminder = self.reminder_manager.add_reminder(text, time_str)
                    reminder_time = datetime.datetime.strptime(reminder['time'], "%H:%M:%S").strftime("%I:%M %p")
                    self.voice_engine.speak(f"Reminder set for {reminder_time}: {text}")
                except ValueError as e:
                    self.voice_engine.speak(f"Error: {str(e)}")
                except Exception as e:
                    logging.error(f"Error adding reminder: {e}")
                    self.voice_engine.speak("Sorry, I couldn't set that reminder.")
            else:
                self.voice_engine.speak("Please provide both reminder text and time.")
                
        elif command == 'exit':
            self.voice_engine.speak("Goodbye! Have a great day.")
            self.running = False
            
        elif command == 'unknown':
            text = params.get('text', '')
            self.voice_engine.speak("I'm not sure how to help with that. Could you try rephrasing?")
        
        return True

    def start(self):
        """Start the personal assistant."""
        self.running = True
        self.reminder_manager.start_reminder_checker()
        
        # Welcome message
        user_name = self.user_preferences.get_preference('name', 'User')
        self.voice_engine.speak(f"Hello {user_name}! I'm Cortex, your personal assistant. How can I help you today?")
        
        try:
            while self.running:
                try:
                    # Flag to indicate source of input (voice or manual)
                    input_source = 'voice'
                    
                    # Listen for wake word or direct command
                    user_data = self.voice_engine.listen()
                    
                    if not user_data:  # If voice input is not available, fallback to manual input
                        input_source = 'manual'
                        user_data = input("Prompt: ")

                    # Log or process where the input came from
                    logging.info(f"User input ({input_source}): {user_data}")

                    # Parse and handle the command
                    command_data = self.nlp_engine.parse_command(user_data)
                    self.handle_command(command_data)
                    
                    # Handle follow-up context if needed
                    if self.follow_up_context and 'action' in self.follow_up_context:
                        # Wait for user response
                        response = self.voice_engine.listen(timeout=5, phrase_time_limit=3)
                        
                        if 'action' in self.follow_up_context and self.follow_up_context['action'] == 'continue_task_list':
                            if any(word in response.lower() for word in ['yes', 'yeah', 'sure', 'okay']):
                                tasks = self.follow_up_context.get('tasks', [])
                                current_index = self.follow_up_context.get('current_index', 0)
                                
                                # Read the next batch of tasks
                                end_index = min(current_index + 3, len(tasks))
                                for task_id, task in tasks[current_index:end_index]:
                                    task_info = self._format_task_for_speech(task_id, task)
                                    self.voice_engine.speak(task_info)
                                
                                # Update context for possible continued listing
                                if end_index < len(tasks):
                                    self.voice_engine.speak(f"And {len(tasks) - end_index} more. Would you like to hear the rest?")
                                    self.follow_up_context['current_index'] = end_index
                                else:
                                    self.follow_up_context = None
                            else:
                                self.voice_engine.speak("Okay, let me know if you need anything else.")
                                self.follow_up_context = None
                
                except SpeechRecognitionError as e:
                    self.voice_engine.speak(str(e))
                except Exception as e:
                    logging.error(f"Error in main loop: {e}")
                    self.voice_engine.speak("Sorry, I encountered an error.")
        
        finally:
            # Clean up
            self.reminder_manager.stop_reminder_checker()
            logging.info("Personal assistant stopped")
    
    def stop(self):
        """Stop the personal assistant."""
        self.running = False
        self.reminder_manager.stop_reminder_checker()


# Example usage of the personal assistant
if __name__ == "__main__":
    try:
        # Create and start the personal assistant
        assistant = PersonalAssistant()
        assistant.start()
    except KeyboardInterrupt:
        print("Stopping by keyboard interrupt...")
        if 'assistant' in locals():
            assistant.stop()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        print(f"Error: {e}")
        sys.exit(1)
