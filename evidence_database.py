import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import uuid
from collections import defaultdict

def serialize_timestamps(obj):
    """Recursively convert Pandas Timestamps or datetime objects to ISO strings."""
    if isinstance(obj, pd.Timestamp):
        return obj.to_pydatetime().isoformat()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_timestamps(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_timestamps(item) for item in obj]
    else:
        return obj
    
class EvidenceDatabase:
    """Database class for storing and retrieving evidence items"""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._initialize_tables()
    
    def _initialize_tables(self):
        """Initialize database tables"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_analysis_logs (
            id TEXT PRIMARY KEY,
            prompt TEXT,
            result TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create tables for AI suggestions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_relationship_suggestions (
            id TEXT PRIMARY KEY,
            evidence_id_1 TEXT NOT NULL,
            evidence_id_2 TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            confidence REAL,
            description TEXT,
            applied BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_time_entry_suggestions (
            id TEXT PRIMARY KEY,
            data JSON NOT NULL,
            applied BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        # Create uploads table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY,
            file_name TEXT NOT NULL,
            file_type TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            record_count INTEGER,
            file_path TEXT
        )
        ''')
        
        # Create evidence table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            timestamp TIMESTAMP,
            data JSON NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create time_entries table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_entries (
            id TEXT PRIMARY KEY,
            date TIMESTAMP NOT NULL,
            hours REAL NOT NULL,
            activity_category TEXT,
            description TEXT,
            user TEXT,
            rate REAL,
            billable REAL,
            data JSON NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create evidence_relationships table for linking related items
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence_relationships (
            id TEXT PRIMARY KEY,
            evidence_id_1 TEXT NOT NULL,
            evidence_id_2 TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            confidence REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id_1) REFERENCES evidence (id),
            FOREIGN KEY (evidence_id_2) REFERENCES evidence (id)
        )
        ''')
        
        # Create evidence_time_entry_links table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence_time_entry_links (
            id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            time_entry_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id) REFERENCES evidence (id),
            FOREIGN KEY (time_entry_id) REFERENCES time_entries (id)
        )
        ''')
        
        # Create case_context table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS case_context (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            parties JSON,
            data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create projects table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            data JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create evidence_project_links table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence_project_links (
            id TEXT PRIMARY KEY,
            evidence_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (evidence_id) REFERENCES evidence (id),
            FOREIGN KEY (project_id) REFERENCES projects (id)
        )
        ''')
       
        # Create project_backups table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS project_backups (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create backup_case_context table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS backup_case_context (
            id TEXT PRIMARY KEY,
            backup_id TEXT NOT NULL,
            context_data JSON NOT NULL,
            FOREIGN KEY (backup_id) REFERENCES project_backups (id)
        )
        ''')
         # Create tables for AI suggestions
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_relationship_suggestions (
            id TEXT PRIMARY KEY,
            evidence_id_1 TEXT NOT NULL,
            evidence_id_2 TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            confidence REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_time_entry_suggestions (
            id TEXT PRIMARY KEY,
            data JSON NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Add archived column to uploads table if it doesn't exist
        cursor.execute("PRAGMA table_info(uploads)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'archived' not in column_names:
            cursor.execute('ALTER TABLE uploads ADD COLUMN archived BOOLEAN DEFAULT 0')
        
        # Create indices for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence (type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_evidence_timestamp ON evidence (timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_time_entries_date ON time_entries (date)')
        
        self.conn.commit()
    

    def insert_evidence_items(self, items: List[Dict[str, Any]]) -> int:
        """Insert multiple evidence items into the database"""
        cursor = self.conn.cursor()
        count = 0

        for item in items:
            try:
                item_id = item.get('id', str(uuid.uuid4()))
                item_type = item.get('type', 'unknown')
                timestamp = item.get('timestamp')

                # Convert timestamp if it's a string
                if isinstance(timestamp, str):
                    try:
                        timestamp = pd.to_datetime(timestamp)
                    except Exception as e:
                        print(f"Error converting timestamp string: {e}")
                        timestamp = None

                if pd.notnull(timestamp):
                    if isinstance(timestamp, pd.Timestamp):
                        timestamp = timestamp.to_pydatetime().isoformat()
                    elif isinstance(timestamp, datetime):
                        timestamp = timestamp.isoformat()
                else:
                    timestamp = None

                # Update the top-level timestamp field
                item['timestamp'] = timestamp

                # Recursively convert Timestamps within the item dictionary
                serializable_item = serialize_timestamps(item)
                data_json = json.dumps(serializable_item)

                cursor.execute(
                    'INSERT OR REPLACE INTO evidence (id, type, timestamp, data) VALUES (?, ?, ?, ?)',
                    (item_id, item_type, timestamp, data_json)
                )
                count += 1
            except Exception as e:
                print(f"Error inserting evidence item: {e}")
                continue

        self.conn.commit()
        return count

    def insert_time_entries(self, entries: List[Dict[str, Any]]) -> int:
        """Insert multiple time entries into the database with unified field structure"""
        cursor = self.conn.cursor()
        count = 0
        
        for entry in entries:
            try:
                # Standardize the entry structure for database storage
                entry_id = entry.get('id', str(uuid.uuid4()))
                
                # Normalize date format
                date = entry.get('date')
                if isinstance(date, str):
                    # Remove time component if present
                    if 'T' in date:
                        date = date.split('T')[0]
                
                # Get all the required fields with proper fallbacks
                hours = float(entry.get('quantity', entry.get('hours', 0)))
                activity_category = entry.get('type', entry.get('activity_category', ''))
                description = entry.get('activity_description', entry.get('description', ''))
                user = entry.get('activity_user', entry.get('user', 'Attorney'))
                rate = float(entry.get('rate', 250.0))
                billable = float(entry.get('price', hours * rate))
                non_billable = float(entry.get('non_billable', 0.0))
                matter = entry.get('matter', 'Default Matter')
                note = entry.get('note', '')
                
                # Ensure note is a string
                if isinstance(note, list):
                    note = '; '.join(note)
                
                # Create a standardized dictionary representation
                data = {
                    'id': entry_id,
                    'date': date,
                    'hours': hours,
                    'quantity': hours,  # Store both for compatibility
                    'activity_category': activity_category,
                    'type': activity_category,  # Store both for compatibility
                    'description': description,
                    'activity_description': description,  # Store both for compatibility
                    'user': user,
                    'activity_user': user,  # Store both for compatibility
                    'rate': rate,
                    'billable': billable,
                    'price': billable,  # Store both for compatibility
                    'non_billable': non_billable,
                    'matter': matter,
                    'note': note,
                    'generated': entry.get('generated', True)
                }
                
                # Store the entire entry as JSON
                data_json = json.dumps(data)
                
                # Check if this entry already exists
                cursor.execute('SELECT id FROM time_entries WHERE id = ?', (entry_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing entry
                    cursor.execute(
                        '''UPDATE time_entries SET 
                        date = ?, hours = ?, activity_category = ?, description = ?, 
                        user = ?, rate = ?, billable = ?, data = ? 
                        WHERE id = ?''',
                        (date, hours, activity_category, description, user, rate, billable, data_json, entry_id)
                    )
                else:
                    # Insert new entry
                    cursor.execute(
                        '''INSERT INTO time_entries 
                        (id, date, hours, activity_category, description, user, rate, billable, data) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (entry_id, date, hours, activity_category, description, user, rate, billable, data_json)
                    )
                
                count += 1
            except Exception as e:
                print(f"Error inserting time entry: {str(e)}")
                print(f"Problematic entry: {entry}")
                continue
        
        self.conn.commit()
        return count
    
    def link_evidence_to_time_entry(self, evidence_id: str, time_entry_id: str) -> str:
        """Create a link between evidence and time entry"""
        cursor = self.conn.cursor()
        link_id = str(uuid.uuid4())
        
        cursor.execute(
            'INSERT INTO evidence_time_entry_links (id, evidence_id, time_entry_id) VALUES (?, ?, ?)',
            (link_id, evidence_id, time_entry_id)
        )
        self.conn.commit()
        return link_id
    
    def link_related_evidence(self, evidence_id_1: str, evidence_id_2: str, 
                             relationship_type: str, confidence: float = 1.0) -> str:
        """Create a relationship between two evidence items"""
        cursor = self.conn.cursor()
        relationship_id = str(uuid.uuid4())
        
        cursor.execute(
            '''INSERT INTO evidence_relationships 
            (id, evidence_id_1, evidence_id_2, relationship_type, confidence) 
            VALUES (?, ?, ?, ?, ?)''',
            (relationship_id, evidence_id_1, evidence_id_2, relationship_type, confidence)
        )
        self.conn.commit()
        return relationship_id
    
    def set_case_context(self, name: str, description: str = "", 
                        parties: Optional[List[Dict]] = None, data: Optional[Dict] = None) -> str:
        """Set the case context information"""
        cursor = self.conn.cursor()
        context_id = str(uuid.uuid4())
        
        parties_json = json.dumps(parties or [])
        data_json = json.dumps(data or {})
        
        cursor.execute(
            '''INSERT INTO case_context 
            (id, name, description, parties, data) 
            VALUES (?, ?, ?, ?, ?)''',
            (context_id, name, description, parties_json, data_json)
        )
        self.conn.commit()
        return context_id
    
    def create_project(self, name: str, description: str = "", 
                      start_date: Optional[Union[str, datetime]] = None, 
                      end_date: Optional[Union[str, datetime]] = None, 
                      data: Optional[Dict] = None) -> str:
        """Create a new project"""
        cursor = self.conn.cursor()
        project_id = str(uuid.uuid4())
        
        # Convert dates to ISO format if they're datetimes
        if isinstance(start_date, datetime):
            start_date = start_date.isoformat()
        if isinstance(end_date, datetime):
            end_date = end_date.isoformat()
        
        data_json = json.dumps(data or {})
        
        cursor.execute(
            '''INSERT INTO projects 
            (id, name, description, start_date, end_date, data) 
            VALUES (?, ?, ?, ?, ?, ?)''',
            (project_id, name, description, start_date, end_date, data_json)
        )
        self.conn.commit()
        return project_id
    
    def link_evidence_to_project(self, evidence_id: str, project_id: str) -> str:
        """Link evidence to a project"""
        cursor = self.conn.cursor()
        link_id = str(uuid.uuid4())
        
        cursor.execute(
            'INSERT INTO evidence_project_links (id, evidence_id, project_id) VALUES (?, ?, ?)',
            (link_id, evidence_id, project_id)
        )
        self.conn.commit()
        return link_id
    
    def query_evidence(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query evidence items with filters"""
        cursor = self.conn.cursor()
        query = 'SELECT id, type, timestamp, data FROM evidence'
        params = []
        
        if filters:
            where_clauses = []
            
            if 'type' in filters:
                where_clauses.append('type = ?')
                params.append(filters['type'])
                
            if 'start_date' in filters and 'end_date' in filters:
                where_clauses.append('timestamp >= ? AND timestamp <= ?')
                params.append(filters['start_date'])
                params.append(filters['end_date'])
            elif 'start_date' in filters:
                where_clauses.append('timestamp >= ?')
                params.append(filters['start_date'])
            elif 'end_date' in filters:
                where_clauses.append('timestamp <= ?')
                params.append(filters['end_date'])
            
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
        
        query += ' ORDER BY timestamp ASC'
        
        cursor.execute(query, params)
        result = []
        
        for row in cursor.fetchall():
            data = json.loads(row['data'])
            result.append(data)
        
        return result
    
    def query_time_entries(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Query time entries with filters and ensure consistent field structure"""
        cursor = self.conn.cursor()
        query = 'SELECT id, date, hours, activity_category, description, user, rate, billable, data FROM time_entries'
        params = []
        
        if filters:
            where_clauses = []
            
            if 'activity_category' in filters:
                where_clauses.append('activity_category = ?')
                params.append(filters['activity_category'])
            
            if 'type' in filters and 'activity_category' not in filters:
                where_clauses.append('activity_category = ?')
                params.append(filters['type'])
                
            if 'user' in filters:
                where_clauses.append('user = ?')
                params.append(filters['user'])
            
            if 'activity_user' in filters and 'user' not in filters:
                where_clauses.append('user = ?')
                params.append(filters['activity_user'])
                
            if 'start_date' in filters and 'end_date' in filters:
                where_clauses.append('date >= ? AND date <= ?')
                params.append(filters['start_date'])
                params.append(filters['end_date'])
            elif 'start_date' in filters:
                where_clauses.append('date >= ?')
                params.append(filters['start_date'])
            elif 'end_date' in filters:
                where_clauses.append('date <= ?')
                params.append(filters['end_date'])
            
            if where_clauses:
                query += ' WHERE ' + ' AND '.join(where_clauses)
        
        query += ' ORDER BY date ASC'
        
        cursor.execute(query, params)
        result = []
        
        for row in cursor.fetchall():
            # Load the full data from JSON
            data = json.loads(row['data'])
            
            # Ensure all standard fields are available (whether from old or new format)
            # This allows template access via either naming convention
            standardized_entry = {
                'id': data.get('id', row['id']),
                'date': data.get('date', row['date']),
                'hours': data.get('hours', row['hours']),
                'quantity': data.get('quantity', row['hours']),
                'activity_category': data.get('activity_category', row['activity_category']),
                'type': data.get('type', row['activity_category']),
                'description': data.get('description', row['description']),
                'activity_description': data.get('activity_description', row['description']),
                'user': data.get('user', row['user']),
                'activity_user': data.get('activity_user', row['user']),
                'rate': data.get('rate', row['rate']),
                'billable': data.get('billable', row['billable']),
                'price': data.get('price', row['billable']),
                'note': data.get('note', ''),
                'matter': data.get('matter', 'Default Matter'),
                'non_billable': data.get('non_billable', 0.0),
                'generated': data.get('generated', True)
            }
            
            result.append(standardized_entry)
        
        return result
    
    def get_evidence_by_id(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific evidence item by ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT data FROM evidence WHERE id = ?', (evidence_id,))
        row = cursor.fetchone()
        
        if row:
            return json.loads(row['data'])
        return None
    
    def get_time_entry_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific time entry by ID with consistent field naming"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, date, hours, activity_category, description, user, rate, billable, data FROM time_entries WHERE id = ?', (entry_id,))
        row = cursor.fetchone()
        
        if row:
            # Load the full data from JSON
            try:
                data = json.loads(row['data'])
            except (json.JSONDecodeError, TypeError):
                # Fall back to basic data if JSON parse fails
                data = {}
            
            # Create a standardized entry with both old and new field names
            standardized_entry = {
                'id': data.get('id', row['id']),
                'date': data.get('date', row['date']),
                'hours': data.get('hours', row['hours']),
                'quantity': data.get('quantity', row['hours']),
                'activity_category': data.get('activity_category', row['activity_category']),
                'type': data.get('type', row['activity_category']),
                'description': data.get('description', row['description']),
                'activity_description': data.get('activity_description', row['description']),
                'user': data.get('user', row['user']),
                'activity_user': data.get('activity_user', row['user']),
                'rate': data.get('rate', row['rate']),
                'billable': data.get('billable', row['billable']),
                'price': data.get('price', row['billable']),
                'note': data.get('note', ''),
                'matter': data.get('matter', 'Default Matter'),
                'non_billable': data.get('non_billable', 0.0),
                'generated': data.get('generated', True)
            }
            
            return standardized_entry
        
        return None
    
    def get_related_evidence(self, evidence_id: str) -> List[Dict[str, Any]]:
        """Get all evidence items related to the given evidence ID"""
        cursor = self.conn.cursor()
        query = '''
        SELECT e.data 
        FROM evidence e
        JOIN evidence_relationships r ON e.id = r.evidence_id_2
        WHERE r.evidence_id_1 = ?
        UNION
        SELECT e.data 
        FROM evidence e
        JOIN evidence_relationships r ON e.id = r.evidence_id_1
        WHERE r.evidence_id_2 = ?
        '''
        
        cursor.execute(query, (evidence_id, evidence_id))
        result = []
        
        for row in cursor.fetchall():
            data = json.loads(row['data'])
            result.append(data)
        
        return result
    
    def get_evidence_for_time_entry(self, time_entry_id: str) -> List[Dict[str, Any]]:
        """Get all evidence items linked to a time entry"""
        cursor = self.conn.cursor()
        query = '''
        SELECT e.data 
        FROM evidence e
        JOIN evidence_time_entry_links l ON e.id = l.evidence_id
        WHERE l.time_entry_id = ?
        '''
        
        cursor.execute(query, (time_entry_id,))
        result = []
        
        for row in cursor.fetchall():
            data = json.loads(row['data'])
            result.append(data)
        
        return result
    
    def get_time_entries_for_evidence(self, evidence_id: str) -> List[Dict[str, Any]]:
        """Get all time entries linked to evidence"""
        cursor = self.conn.cursor()
        query = '''
        SELECT t.data 
        FROM time_entries t
        JOIN evidence_time_entry_links l ON t.id = l.time_entry_id
        WHERE l.evidence_id = ?
        '''
        
        cursor.execute(query, (evidence_id,))
        result = []
        
        for row in cursor.fetchall():
            data = json.loads(row['data'])
            result.append(data)
        
        return result
    
    def get_case_context(self) -> Optional[Dict[str, Any]]:
        """Get the case context information"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM case_context ORDER BY created_at DESC LIMIT 1')
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['parties'] = json.loads(result['parties'])
            result['data'] = json.loads(result['data'])
            return result
        return None
    
    def get_projects(self) -> List[Dict[str, Any]]:
        """Get all projects"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM projects ORDER BY start_date ASC')
        result = []
        
        for row in cursor.fetchall():
            project = dict(row)
            project['data'] = json.loads(project['data'])
            result.append(project)
        
        return result
    
    def get_evidence_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all evidence items linked to a project"""
        cursor = self.conn.cursor()
        query = '''
        SELECT e.data 
        FROM evidence e
        JOIN evidence_project_links l ON e.id = l.evidence_id
        WHERE l.project_id = ?
        ORDER BY e.timestamp ASC
        '''
        
        cursor.execute(query, (project_id,))
        result = []
        
        for row in cursor.fetchall():
            data = json.loads(row['data'])
            result.append(data)
        
        return result
    
    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()


class TimelineConstructor:
    """Constructs a timeline from evidence items and identifies relationships"""
    
    def __init__(self, evidence_db: EvidenceDatabase):
        self.evidence_db = evidence_db
    
    def build_timeline(self, start_date: Optional[Union[str, datetime]] = None, 
                      end_date: Optional[Union[str, datetime]] = None) -> List[Dict[str, Any]]:
        """Build a timeline of all evidence within the date range"""
        filters = {}
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        # Get all evidence
        evidence_items = self.evidence_db.query_evidence(filters)
        
        # Sort by timestamp
        timeline = sorted(evidence_items, key=lambda x: x.get('timestamp', ''))
        
        return timeline
    
    def identify_relationships(self, confidence_threshold: float = 0.7) -> int:
        """
        Identify relationships between evidence items and store them in the database
        Returns the number of relationships identified
        """
        # Get all evidence items
        all_evidence = self.evidence_db.query_evidence()
        relationship_count = 0
        
        # Create mappings for faster lookups
        email_by_message_id = {}
        email_by_subject = defaultdict(list)
        sms_by_session = defaultdict(list)
        
        # Build mappings
        for item in all_evidence:
            if item['type'] == 'email':
                if 'message_id' in item and item['message_id']:
                    email_by_message_id[item['message_id']] = item
                if 'subject' in item and item['subject']:
                    # Normalize subject by removing Re:, Fwd:, etc.
                    normalized_subject = self._normalize_email_subject(item['subject'])
                    email_by_subject[normalized_subject].append(item)
            elif item['type'] == 'sms':
                if 'chat_session' in item and item['chat_session']:
                    sms_by_session[item['chat_session']].append(item)
        
        # Find email reply chains using In-Reply-To and References
        for item in all_evidence:
            if item['type'] == 'email':
                # Link by In-Reply-To
                if 'in_reply_to' in item and item['in_reply_to']:
                    in_reply_to = item['in_reply_to']
                    if in_reply_to in email_by_message_id:
                        parent_email = email_by_message_id[in_reply_to]
                        self.evidence_db.link_related_evidence(
                            parent_email['id'], item['id'], 'reply_to', 1.0)
                        relationship_count += 1
                
                # Link by References
                if 'references' in item and item['references']:
                    references = item['references']
                    # Often references is a space-separated list of message IDs
                    if isinstance(references, str):
                        ref_ids = references.split()
                        for ref_id in ref_ids:
                            if ref_id in email_by_message_id:
                                ref_email = email_by_message_id[ref_id]
                                self.evidence_db.link_related_evidence(
                                    ref_email['id'], item['id'], 'reference', 0.9)
                                relationship_count += 1
                
                # Link by conversation_id
                if 'conversation_id' in item and item['conversation_id']:
                    for other in all_evidence:
                        if (other['id'] != item['id'] and 
                            other['type'] == 'email' and 
                            'conversation_id' in other and 
                            other['conversation_id'] == item['conversation_id']):
                            self.evidence_db.link_related_evidence(
                                item['id'], other['id'], 'conversation', 0.9)
                            relationship_count += 1
                
                # Link by subject (less confident)
                if 'subject' in item and item['subject']:
                    normalized_subject = self._normalize_email_subject(item['subject'])
                    subject_matches = email_by_subject[normalized_subject]
                    for other in subject_matches:
                        if other['id'] != item['id']:
                            # Calculate timestamp difference to avoid linking distant emails
                            time_diff = self._calculate_time_difference(item, other)
                            # Only link if within 7 days
                            if time_diff is not None and time_diff < 7:
                                confidence = max(0.5, 1.0 - (time_diff / 7))
                                if confidence >= confidence_threshold:
                                    self.evidence_db.link_related_evidence(
                                        item['id'], other['id'], 'subject', confidence)
                                    relationship_count += 1
        
        # Link SMS messages within the same chat session
        for session, messages in sms_by_session.items():
            sorted_messages = sorted(messages, key=lambda x: x.get('timestamp', ''))
            for i in range(len(sorted_messages) - 1):
                current = sorted_messages[i]
                next_msg = sorted_messages[i + 1]
                # Link sequential messages in the same session
                self.evidence_db.link_related_evidence(
                    current['id'], next_msg['id'], 'chat_sequence', 1.0)
                relationship_count += 1
        
        # Link phone calls to emails/SMS that happened shortly after
        for item in all_evidence:
            if item['type'] == 'phone_call':
                call_time = self._parse_timestamp(item.get('timestamp'))
                if call_time:
                    # Look for emails or SMS within 30 minutes after the call
                    for other in all_evidence:
                        if other['type'] in ['email', 'sms']:
                            other_time = self._parse_timestamp(other.get('timestamp'))
                            if other_time and call_time < other_time:
                                # Calculate minutes difference
                                diff_minutes = (other_time - call_time).total_seconds() / 60
                                if diff_minutes <= 30:
                                    # Higher confidence for closer timing
                                    confidence = 1.0 - (diff_minutes / 30)
                                    if confidence >= confidence_threshold:
                                        self.evidence_db.link_related_evidence(
                                            item['id'], other['id'], 'call_followed_by', confidence)
                                        relationship_count += 1
        
        # Link evidence items by text content similarity (more advanced)
        # This would use NLP techniques to identify related items based on content
        # implementation would depend on NLP libraries available
        
        return relationship_count
    
    def associate_evidence_with_docket_events(self) -> int:
        """
        Associate evidence items with docket events based on timing and content
        Returns the number of associations created
        """
        # Get all docket events
        docket_events = self.evidence_db.query_evidence({'type': 'docket'})
        all_evidence = self.evidence_db.query_evidence()
        
        # Filter out non-docket evidence
        other_evidence = [e for e in all_evidence if e['type'] != 'docket']
        association_count = 0
        
        for docket in docket_events:
            docket_time = self._parse_timestamp(docket.get('timestamp'))
            if not docket_time:
                continue
            
            # Find evidence items in a relevant time window (3 days before and 1 day after)
            three_days_before = docket_time - timedelta(days=3)
            one_day_after = docket_time + timedelta(days=1)
            
            related_items = []
            for evidence in other_evidence:
                evidence_time = self._parse_timestamp(evidence.get('timestamp'))
                if not evidence_time:
                    continue
                
                if three_days_before <= evidence_time <= one_day_after:
                    # Check for content relevance
                    relevance_score = self._calculate_relevance(docket, evidence)
                    if relevance_score >= 0.6:  # Threshold for relevance
                        related_items.append((evidence, relevance_score))
            
            # Link the most relevant items to the docket event
            for evidence, score in sorted(related_items, key=lambda x: x[1], reverse=True):
                self.evidence_db.link_related_evidence(
                    docket['id'], evidence['id'], 'related_to_docket', score)
                association_count += 1
        
        return association_count
    
    def suggest_projects(self) -> List[Dict[str, Any]]:
        """
        Analyze evidence items and suggest potential projects
        Returns a list of suggested projects with evidence IDs
        """
        # Get all docket events
        docket_events = self.evidence_db.query_evidence({'type': 'docket'})
        
        # Group docket events by type/category
        docket_groups = defaultdict(list)
        
        for docket in docket_events:
            event_type = docket.get('event_type', '')
            # Clean up and standardize the event type
            clean_type = event_type.strip().lower()
            docket_groups[clean_type].append(docket)
        
        # Identify key project categories
        project_categories = {
            'motion': ['motion', 'opposition', 'reply'],
            'discovery': ['discovery', 'deposition', 'request', 'production'],
            'hearing': ['hearing', 'trial', 'conference'],
            'filing': ['complaint', 'answer', 'petition']
        }
        
        # Group dockets into potential projects
        suggested_projects = []
        
        for category, keywords in project_categories.items():
            # Find all dockets related to this category
            category_dockets = []
            for key, dockets in docket_groups.items():
                if any(keyword in key for keyword in keywords):
                    category_dockets.extend(dockets)
            
            if category_dockets:
                # Sort by timestamp
                sorted_dockets = sorted(category_dockets, key=lambda x: self._parse_timestamp(x.get('timestamp')) or datetime.min)
                
                # Create a project suggestion
                project = {
                    'name': f"{category.capitalize()} Project",
                    'description': f"Automatically identified {category} activities",
                    'start_date': sorted_dockets[0].get('timestamp'),
                    'end_date': sorted_dockets[-1].get('timestamp'),
                    'evidence_ids': [d['id'] for d in sorted_dockets]
                }
                
                suggested_projects.append(project)
        
        # Also identify projects based on email subject clustering
        all_emails = self.evidence_db.query_evidence({'type': 'email'})
        
        # Group emails by subject
        subject_groups = defaultdict(list)
        for email in all_emails:
            if 'subject' in email and email['subject']:
                normalized_subject = self._normalize_email_subject(email['subject'])
                subject_groups[normalized_subject].append(email)
        
        # Find subject groups with significant activity
        for subject, emails in subject_groups.items():
            if len(emails) >= 5:  # Threshold for significant email thread
                # Sort by timestamp
                sorted_emails = sorted(emails, key=lambda x: self._parse_timestamp(x.get('timestamp')) or datetime.min)
                
                # Create a project suggestion
                project = {
                    'name': f"Email Thread: {subject[:30]}...",
                    'description': f"Automatically identified email thread with {len(emails)} messages",
                    'start_date': sorted_emails[0].get('timestamp'),
                    'end_date': sorted_emails[-1].get('timestamp'),
                    'evidence_ids': [e['id'] for e in sorted_emails]
                }
                
                suggested_projects.append(project)
        
        return suggested_projects
    
    def _normalize_email_subject(self, subject: str) -> str:
        """Normalize email subject by removing prefixes like Re:, Fwd:, etc."""
        if not subject:
            return ""
        
        # Remove common prefixes
        prefixes = ['re:', 'fwd:', 'fw:', 'response:']
        normalized = subject.lower()
        
        for prefix in prefixes:
            while normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        return normalized
    
    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse a timestamp string into a datetime object"""
        if not timestamp_str:
            return None
        
        try:
            return pd.to_datetime(timestamp_str)
        except:
            return None
    
    def _calculate_time_difference(self, item1: Dict[str, Any], item2: Dict[str, Any]) -> Optional[float]:
        """Calculate the time difference between two evidence items in days"""
        time1 = self._parse_timestamp(item1.get('timestamp'))
        time2 = self._parse_timestamp(item2.get('timestamp'))
        
        if time1 and time2:
            return abs((time1 - time2).total_seconds()) / (24 * 3600)  # Convert to days
        return None
    
    def _calculate_relevance(self, docket: Dict[str, Any], evidence: Dict[str, Any]) -> float:
        """
        Calculate relevance score between a docket event and evidence item
        Returns a score between 0 and 1
        """
        score = 0.0
        
        # Check if evidence mentions docket event type
        docket_type = docket.get('event_type', '').lower()
        docket_memo = docket.get('memo', '').lower()
        
        if evidence['type'] == 'email':
            body = evidence.get('body', '').lower()
            subject = evidence.get('subject', '').lower()
            
            # Check for docket event type in email
            if docket_type and (docket_type in body or docket_type in subject):
                score += 0.5
            
            # Check for memo content in email
            if docket_memo and (docket_memo in body or docket_memo in subject):
                score += 0.3
            
        elif evidence['type'] == 'sms':
            text = evidence.get('text', '').lower()
            
            # Check for docket event type in SMS
            if docket_type and docket_type in text:
                score += 0.5
            
            # Check for memo content in SMS
            if docket_memo and docket_memo in text:
                score += 0.3
        
        # Additional time-based relevance
        evidence_time = self._parse_timestamp(evidence.get('timestamp'))
        docket_time = self._parse_timestamp(docket.get('timestamp'))
        
        if evidence_time and docket_time:
            # Calculate hours difference
            hours_diff = abs((evidence_time - docket_time).total_seconds()) / 3600
            
            # Closer in time = more relevant
            if hours_diff <= 24:
                time_score = 0.2 * (1 - (hours_diff / 24))
                score += time_score
        
        return min(1.0, score)  # Cap at 1.0