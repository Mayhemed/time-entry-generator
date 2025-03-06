import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
import re
import uuid
import os
import json
import logging
import time

class BaseProcessor:
    def __init__(self):
        self.data = None
        
    def load_file(self, file_path: str) -> pd.DataFrame:
        """Load file into a pandas DataFrame"""
        return pd.read_csv(file_path, encoding='utf-8', low_memory=False)
    
    def clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare data"""
        # Remove any completely empty rows
        df = df.dropna(how='all')
        return df
    
    def normalize_dates(self, df: pd.DataFrame, date_column: str) -> pd.DataFrame:
        """Normalize date formats to ISO format"""
        if date_column in df.columns:
            try:
                df[date_column] = pd.to_datetime(df[date_column])
            except Exception as e:
                print(f"Error normalizing dates in column {date_column}: {e}")
        return df
    
    def process(self, file_path: str) -> List[Dict[str, Any]]:
        """Process the file and return standardized evidence items"""
        raise NotImplementedError("Subclasses must implement this method")


class EmailProcessor(BaseProcessor):
    def process(self, file_path: str) -> List[Dict[str, Any]]:
        """Process email CSV and return standardized evidence items"""
        # Load the file
        df = self.load_file(file_path)
        print("Email CSV shape:", df.shape)  # Debugging line

        # Clean data
        df = self.clean_data(df)
        
        # Normalize dates
        df = self.normalize_dates(df, 'Date')
        
        # Convert to standardized format
        evidence_items = []
        
        for _, row in df.iterrows():
            try:
                # Create unique ID if not present
                evidence_id = str(row.get('ID', uuid.uuid4()))
                
                # Extract email details
                evidence_item = {
                    'id': evidence_id,
                    'type': 'email',
                    'timestamp': row['Date'] if pd.notna(row.get('Date')) else None,
                    'subject': row.get('Subject', ''),
                    'body': row.get('Body', ''),
                    'from': row.get('From', ''),
                    'to': row.get('To', ''),
                    'has_attachment': row.get('Has_Non_Image_Attachment', False),
                    'attachment_names': row.get('Attachment_Names', ''),
                    'conversation_id': row.get('Conversation_ID', ''),
                    'is_response': row.get('Is_Response', False),
                    'in_reply_to': row.get('In_Reply_To', ''),
                    'references': row.get('References', ''),
                    'message_id': row.get('Message_ID', ''),
                    'raw_data': row.to_dict()
                }
                
                # Skip if missing critical fields
                if evidence_item['timestamp'] is None:
                    continue
                
                evidence_items.append(evidence_item)
            except Exception as e:
                print(f"Error processing email row: {e}")
                continue
        
        return evidence_items


class SMSProcessor(BaseProcessor):
    def process(self, file_path: str) -> List[Dict[str, Any]]:
        """Process SMS CSV and return standardized evidence items"""
        # Load the file
        df = self.load_file(file_path)
        print("SMS CSV shape:", df.shape)  # Debugging line

        # Clean data
        df = self.clean_data(df)
        
        # Normalize dates
        df = self.normalize_dates(df, 'Message Date')
        
        # Convert to standardized format
        evidence_items = []
        
        for _, row in df.iterrows():
            try:
                # Create unique ID
                evidence_id = str(uuid.uuid4())
                
                # Determine direction (incoming/outgoing)
                message_type = row.get('Type', '')
                direction = 'outgoing' if message_type.lower() == 'outgoing' else 'incoming'
                
                # Extract SMS details
                evidence_item = {
                    'id': evidence_id,
                    'type': 'sms',
                    'timestamp': row['Message Date'] if pd.notna(row.get('Message Date')) else None,
                    'text': row.get('Text', ''),
                    'chat_session': row.get('Chat Session', ''),
                    'direction': direction,
                    'sender_name': row.get('Sender Name', ''),
                    'has_attachment': bool(row.get('Attachment', '')),
                    'attachment_type': row.get('Attachment type', ''),
                    'delivered_date': row.get('Delivered Date', ''),
                    'read_date': row.get('Read Date', ''),
                    'raw_data': row.to_dict()
                }
                
                # Skip if missing critical fields
                if evidence_item['timestamp'] is None:
                    continue
                
                evidence_items.append(evidence_item)
            except Exception as e:
                print(f"Error processing SMS row: {e}")
                continue
        
        return evidence_items


class DocketProcessor(BaseProcessor):
    def process(self, file_path: str) -> List[Dict[str, Any]]:
        """Process docket CSV and return standardized evidence items"""
        # Load the file
        df = self.load_file(file_path)
        print("Docket CSV shape:", df.shape)  # Debugging line

        # Clean data
        df = self.clean_data(df)
        
        # Normalize dates
        df = self.normalize_dates(df, 'Event Date')
        
        # Convert to standardized format
        evidence_items = []
        
        for _, row in df.iterrows():
            try:
                # Create unique ID
                evidence_id = str(uuid.uuid4())
                
                # Extract docket details
                evidence_item = {
                    'id': evidence_id,
                    'type': 'docket',
                    'timestamp': row['Event Date'] if pd.notna(row.get('Event Date')) else None,
                    'event_type': row.get('Event Type', ''),
                    'memo': row.get('Memo', ''),
                    'filed_by': row.get('Filed By', ''),
                    'raw_data': row.to_dict()
                }
                
                # Skip if missing critical fields
                if evidence_item['timestamp'] is None:
                    continue
                
                evidence_items.append(evidence_item)
            except Exception as e:
                print(f"Error processing docket row: {e}")
                continue
        
        return evidence_items


class PhoneCallProcessor(BaseProcessor):
    def process(self, file_path: str) -> List[Dict[str, Any]]:
        """Process phone call CSV and return standardized evidence items"""
        # Load the file
        df = self.load_file(file_path)
        print("PhoneCall CSV shape:", df.shape)  # Debugging line

        # Clean data
        df = self.clean_data(df)
        
        # Normalize dates
        df = self.normalize_dates(df, 'Date')
        
        # Convert to standardized format
        evidence_items = []
        
        for _, row in df.iterrows():
            try:
                # Create unique ID
                evidence_id = str(uuid.uuid4())
                
                # Parse duration (e.g., "1:23" to minutes)
                duration_str = row.get('Duration', '0:00')
                duration_minutes = 0
                
                if isinstance(duration_str, str) and ':' in duration_str:
                    parts = duration_str.split(':')
                    if len(parts) == 2:
                        try:
                            duration_minutes = int(parts[0]) * 60 + int(parts[1])
                        except ValueError:
                            duration_minutes = 0
                
                # Extract call details
                evidence_item = {
                    'id': evidence_id,
                    'type': 'phone_call',
                    'timestamp': row['Date'] if pd.notna(row.get('Date')) else None,
                    'call_type': row.get('Call type', ''),
                    'duration_seconds': duration_minutes * 60,
                    'number': row.get('Number', ''),
                    'contact': row.get('Contact', ''),
                    'service': row.get('Service', ''),
                    'raw_data': row.to_dict()
                }
                
                # Skip if missing critical fields
                if evidence_item['timestamp'] is None:
                    continue
                
                evidence_items.append(evidence_item)
            except Exception as e:
                print(f"Error processing phone call row: {e}")
                continue
        
        return evidence_items


class TimeEntryProcessor(BaseProcessor):
    def process(self, file_path: str) -> List[Dict[str, Any]]:
        """Process time entry CSV and return standardized items"""
        # Load the file
        df = self.load_file(file_path)
        print("TimeEntry CSV shape:", df.shape)  # Debugging line

        # Clean data
        df = self.clean_data(df)
        
        # Normalize dates
        df = self.normalize_dates(df, 'Date')
        
        # Convert to standardized format
        time_entries = []
        
        for _, row in df.iterrows():
            try:
                # Create unique ID
                entry_id = str(row.get('ID', uuid.uuid4()))
                
                # Extract time entry details
                time_entry = {
                    'id': entry_id,
                    'type': 'time_entry',
                    'date': row['Date'] if pd.notna(row.get('Date')) else None,
                    'hours': float(row.get('Hours', 0)),
                    'activity_category': row.get('Activity category', ''),
                    'description': row.get('Description', ''),
                    'rate': float(row.get('Rate ($)', 0)),
                    'billable': float(row.get('Billable ($)', 0)),
                    'user': row.get('User', ''),
                    'billed': bool(row.get('Billed', False)),
                    'raw_data': row.to_dict()
                }
                
                # Skip if missing critical fields
                if time_entry['date'] is None:
                    continue
                
                time_entries.append(time_entry)
            except Exception as e:
                print(f"Error processing time entry row: {e}")
                continue
        
        return time_entries


class DebugLogger:
    """Logger for debugging time entry generation and AI interactions"""
    
    def __init__(self, enabled: bool = False):
        """Initialize the debug logger
        
        Args:
            enabled: Whether the logger is enabled
        """
        self.enabled = enabled
        self.logger = None
        self.log_file = None
        
        if enabled:
            self._setup_logger()
    
    def _setup_logger(self):
        """Set up the logger with file handler"""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Create a unique log file name based on timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = f"logs/time_entry_debug_{timestamp}.log"
        
        # Configure logger
        self.logger = logging.getLogger(f'time_entry_debug_{timestamp}')
        self.logger.setLevel(logging.DEBUG)
        
        # Create a file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        
        # Create a formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Log initial info
        self.info(f"==== Debug log started at {datetime.now()} ====")
        self.info(f"Log file: {self.log_file}")
    
    def log(self, message: str, level: str = 'info'):
        """Log a message at the specified level
        
        Args:
            message: The message to log
            level: The log level (debug, info, warning, error, critical)
        """
        # Always print to console
        print(message)
        
        if not self.enabled or not self.logger:
            return
            
        # Log to file
        if level == 'debug':
            self.logger.debug(message)
        elif level == 'info':
            self.logger.info(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'critical':
            self.logger.critical(message)
    
    def debug(self, message: str):
        """Log a debug message"""
        self.log(message, 'debug')
    
    def info(self, message: str):
        """Log an info message"""
        self.log(message, 'info')
    
    def warning(self, message: str):
        """Log a warning message"""
        self.log(message, 'warning')
    
    def error(self, message: str):
        """Log an error message"""
        self.log(message, 'error')

    def critical(self, message: str):
        """Log a critical message"""
        self.log(message, 'critical')
    
    def log_dict(self, data: Dict[str, Any], prefix: str = '', max_length: int = 1000):
        """Log a dictionary, potentially truncating long values
        
        Args:
            data: The dictionary to log
            prefix: Optional prefix for the log message
            max_length: Maximum length for string values before truncating
        """
        if not self.enabled or not self.logger:
            return
            
        self.info(f"{prefix}:")
        for key, value in data.items():
            if isinstance(value, str) and len(value) > max_length:
                self.info(f"  {key}: {value[:max_length]}... [truncated, total length: {len(value)}]")
            else:
                self.info(f"  {key}: {value}")

    def log_api_request(self, model: str, prompt: str, system_prompt: Optional[str] = None, 
                       temperature: float = 0.0, provider: str = 'openai'):
        """Log an API request to the LLM
        
        Args:
            model: The model being used
            prompt: The prompt being sent
            system_prompt: Optional system prompt
            temperature: The temperature setting
            provider: The API provider (e.g., 'openai', 'anthropic')
        """
        if not self.enabled or not self.logger:
            return
            
        self.info("=== API REQUEST ===")
        self.info(f"Provider: {provider}")
        self.info(f"Model: {model}")
        self.info(f"Temperature: {temperature}")
        
        if system_prompt:
            self.info("\nSystem Prompt:")
            with open(f"{self.log_file}.system_prompt.txt", 'w') as f:
                f.write(system_prompt)
            self.info(f"[System prompt written to {self.log_file}.system_prompt.txt]")
            self.info(f"System prompt length: {len(system_prompt)} characters")
            
        self.info("\nUser Prompt:")
        with open(f"{self.log_file}.user_prompt.txt", 'w') as f:
            f.write(prompt)
        self.info(f"[User prompt written to {self.log_file}.user_prompt.txt]")
        self.info(f"User prompt length: {len(prompt)} characters")

    def log_api_response(self, response: str):
        """Log an API response
        
        Args:
            response: The response text
        """
        if not self.enabled or not self.logger:
            return
            
        self.info("=== API RESPONSE ===")
        with open(f"{self.log_file}.response.txt", 'w') as f:
            f.write(response)
        self.info(f"[Response written to {self.log_file}.response.txt]")
        self.info(f"Response length: {len(response)} characters")
        self.info(f"Response preview: {response[:500]}... [truncated]")

    def log_evidence(self, evidence_items: list, max_items: int = 20):
        """Log evidence items
        
        Args:
            evidence_items: List of evidence items
            max_items: Maximum number of items to log
        """
        if not self.enabled or not self.logger:
            return
            
        self.info(f"=== EVIDENCE ITEMS (Total: {len(evidence_items)}) ===")
        
        # Save full evidence to file
        with open(f"{self.log_file}.evidence.json", 'w') as f:
            json.dump(evidence_items, f, indent=2, default=str)
        self.info(f"[Full evidence written to {self.log_file}.evidence.json]")
        
        # Log a summary
        evidence_by_type = {}
        for item in evidence_items:
            item_type = item.get('type', 'unknown')
            if item_type not in evidence_by_type:
                evidence_by_type[item_type] = 0
            evidence_by_type[item_type] += 1
        
        self.info("Evidence by type:")
        for item_type, count in evidence_by_type.items():
            self.info(f"  {item_type}: {count} items")
        
        # Log a sample of items
        sample_size = min(max_items, len(evidence_items))
        if sample_size > 0:
            self.info(f"\nSample of {sample_size} evidence items:")
            for i, item in enumerate(evidence_items[:sample_size]):
                item_type = item.get('type', 'unknown')
                timestamp = item.get('timestamp', 'unknown')
                if item_type == 'email':
                    self.info(f"  {i+1}. Email: From {item.get('from', 'unknown')} to {item.get('to', 'unknown')}")
                    self.info(f"     Subject: {item.get('subject', 'No subject')}")
                    self.info(f"     Date: {timestamp}")
                elif item_type == 'sms':
                    self.info(f"  {i+1}. SMS: {item.get('text', '')[:100]}...")
                    self.info(f"     Date: {timestamp}")
                elif item_type == 'phone_call':
                    self.info(f"  {i+1}. Phone Call: {item.get('contact', 'unknown')}")
                    self.info(f"     Duration: {item.get('duration_seconds', 0)} seconds")
                    self.info(f"     Date: {timestamp}")
                elif item_type == 'docket':
                    self.info(f"  {i+1}. Docket: {item.get('event_type', 'unknown')} - {item.get('memo', '')}")
                    self.info(f"     Date: {timestamp}")
                else:
                    self.info(f"  {i+1}. {item_type}: {item}")

    def log_time_entries(self, entries: list):
        """Log generated time entries
        
        Args:
            entries: List of time entries
        """
        if not self.enabled or not self.logger:
            return
            
        self.info(f"=== GENERATED TIME ENTRIES (Total: {len(entries)}) ===")
        
        # Save full entries to file
        with open(f"{self.log_file}.time_entries.json", 'w') as f:
            json.dump(entries, f, indent=2, default=str)
        self.info(f"[Full time entries written to {self.log_file}.time_entries.json]")
        
        # Log a summary of each entry
        for i, entry in enumerate(entries):
            self.info(f"  {i+1}. Date: {entry.get('date', 'unknown')}")
            self.info(f"     Hours: {entry.get('hours', entry.get('quantity', 0))}")
            self.info(f"     Activity: {entry.get('activity_description', entry.get('activity_category', 'unknown'))}")
            description = entry.get('note', entry.get('description', 'No description'))
            if len(description) > 100:
                description = description[:97] + "..."
            self.info(f"     Description: {description}")
            self.info("")

def get_debug_logger(debug_enabled: bool = False) -> DebugLogger:
    """Get a debug logger
    
    Args:
        debug_enabled: Whether to enable debugging
        
    Returns:
        A configured DebugLogger instance
    """
    return DebugLogger(enabled=debug_enabled)