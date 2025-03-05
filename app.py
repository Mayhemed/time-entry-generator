from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os
import json
import pandas as pd
import math
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import tempfile
import sys
import uuid
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import our application code
from time_entry_app import TimeEntryApp

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Initialize TimeEntryApp
time_entry_app = TimeEntryApp(
    db_path=os.environ.get("DB_PATH", "evidence.db"),
    openai_api_key=os.environ.get("OPENAI_API_KEY")
)

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/timeline')
def timeline():
    """Render the timeline view"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
        
    evidence_items = time_entry_app.evidence_db.query_evidence(filters)
    time_entries = time_entry_app.evidence_db.query_time_entries(filters)
    
    return render_template(
        'timeline.html', 
        evidence_items=evidence_items,
        time_entries=time_entries,
        start_date=start_date,
        end_date=end_date
    )

@app.route('/upload', methods=['GET', 'POST'])
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        results = {}
        # A list to accumulate upload records
        upload_records = []
        
        # Example for email files:
        if 'email_file' in request.files:
            email_files = request.files.getlist('email_file')
            total_email_count = 0
            for email_file in email_files:
                if email_file.filename:
                    file_name = secure_filename(email_file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                    email_file.save(filepath)
                    
                    # Process the file and get a count (this function already exists)
                    count = time_entry_app.ingest_data_files({'email': filepath}).get('email', 0)
                    total_email_count += count
                    
                    # Record the upload
                    upload_records.append({
                        'id': str(uuid.uuid4()),
                        'file_name': file_name,
                        'file_type': 'email',
                        'record_count': count,
                        'file_path': filepath
                    })
            results['email'] = total_email_count

        # Process SMS files
        if 'sms_file' in request.files:
            sms_files = request.files.getlist('sms_file')
            total_sms_count = 0
            for sms_file in sms_files:
                if sms_file.filename:
                    file_name = secure_filename(sms_file.filename)  # Define file_name inside this block
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                    sms_file.save(filepath)
                    count = time_entry_app.ingest_data_files({'sms': filepath}).get('sms', 0)
                    total_sms_count += count
                    
                    # Record the upload
                    upload_records.append({
                        'id': str(uuid.uuid4()),
                        'file_name': file_name,
                        'file_type': 'sms',
                        'record_count': count,
                        'file_path': filepath
                    })
            results['sms'] = total_sms_count

        # Process docket files
        if 'docket_file' in request.files:
            docket_files = request.files.getlist('docket_file')
            total_docket_count = 0
            for docket_file in docket_files:
                if docket_file.filename:
                    file_name = secure_filename(docket_file.filename)  # Define file_name inside this block
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                    docket_file.save(filepath)
                    count = time_entry_app.ingest_data_files({'docket': filepath}).get('docket', 0)
                    total_docket_count += count
                    
                    # Record the upload
                    upload_records.append({
                        'id': str(uuid.uuid4()),
                        'file_name': file_name,
                        'file_type': 'docket',
                        'record_count': count,
                        'file_path': filepath
                    })
            results['docket'] = total_docket_count

        # Process phone call files
        if 'phone_file' in request.files:
            phone_files = request.files.getlist('phone_file')
            total_phone_count = 0
            for phone_file in phone_files:
                if phone_file.filename:
                    file_name = secure_filename(phone_file.filename)  # Define file_name inside this block
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                    phone_file.save(filepath)
                    count = time_entry_app.ingest_data_files({'phone_call': filepath}).get('phone_call', 0)
                    total_phone_count += count
                    
                    # Record the upload
                    upload_records.append({
                        'id': str(uuid.uuid4()),
                        'file_name': file_name,
                        'file_type': 'phone_call',
                        'record_count': count,
                        'file_path': filepath
                    })
            results['phone_call'] = total_phone_count

        # Process time entries files
        if 'time_entries_file' in request.files:
            time_entries_files = request.files.getlist('time_entries_file')
            total_time_entries_count = 0
            for time_entries_file in time_entries_files:
                if time_entries_file.filename:
                    file_name = secure_filename(time_entries_file.filename)  # Define file_name inside this block
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
                    time_entries_file.save(filepath)
                    count = time_entry_app.ingest_data_files({'time_entry': filepath}).get('time_entry', 0)
                    total_time_entries_count += count
                    
                    # Record the upload
                    upload_records.append({
                        'id': str(uuid.uuid4()),
                        'file_name': file_name,
                        'file_type': 'time_entry',
                        'record_count': count,
                        'file_path': filepath
                    })
            results['time_entry'] = total_time_entries_count

        # Save upload records to database
        for record in upload_records:
            # Assuming you have a connection in time_entry_app.evidence_db.conn:
            cursor = time_entry_app.evidence_db.conn.cursor()
            cursor.execute('''
                INSERT INTO uploads (id, file_name, file_type, record_count, file_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (record['id'], record['file_name'], record['file_type'], record['record_count'], record['file_path']))
        time_entry_app.evidence_db.conn.commit()

        return jsonify(results)
    
    # For GET, also retrieve the list of uploads:
    cursor = time_entry_app.evidence_db.conn.cursor()
    cursor.execute('SELECT * FROM uploads ORDER BY uploaded_at DESC')
    uploads_list = cursor.fetchall()
    # Pass uploads_list to the template (convert to dicts if needed)
    uploads = [dict(row) for row in uploads_list]
    
    return render_template('upload.html', uploads=uploads)

@app.route('/upload_details/<upload_id>', methods=['GET'])
def upload_details(upload_id):
    """Return details for a specific upload."""
    cursor = time_entry_app.evidence_db.conn.cursor()
    cursor.execute('SELECT * FROM uploads WHERE id = ?', (upload_id,))
    upload = cursor.fetchone()
    if upload:
        # Convert the row to a dict.
        upload = dict(upload)
        return jsonify(upload)
    else:
        return jsonify({"error": "Upload not found"}), 404

@app.route('/case-context', methods=['GET', 'POST'])
def case_context():
    """Set or view case context"""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        
        parties = []
        if 'parties' in request.form:
            try:
                parties = json.loads(request.form.get('parties'))
            except:
                parties = []
        
        time_entry_app.set_case_context(name, description, parties)
        return redirect(url_for('case_context'))
    
    context = time_entry_app.evidence_db.get_case_context()
    return render_template('case_context.html', context=context)

@app.route('/build-timeline', methods=['POST'])
def build_timeline():
    """Build timeline and identify relationships"""
    relationship_count = time_entry_app.build_timeline()
    return jsonify({'relationship_count': relationship_count})

@app.route('/projects')
def projects():
    """View projects page"""
    all_projects = time_entry_app.evidence_db.get_projects()
    return render_template('projects.html', projects=all_projects)

@app.route('/suggest-projects')
def suggest_projects():
    """Suggest projects based on evidence"""
    suggested_projects = time_entry_app.suggest_projects()
    return jsonify({'projects': suggested_projects})

@app.route('/create-project', methods=['POST'])
def create_project():
    """Create a new project"""
    data = request.json
    name = data.get('name')
    description = data.get('description')
    evidence_ids = data.get('evidence_ids', [])
    
    project_id = time_entry_app.create_project(name, description, evidence_ids)
    return jsonify({'project_id': project_id})

@app.route('/project/<project_id>')
def view_project(project_id):
    """View a specific project"""
    project = None
    for p in time_entry_app.evidence_db.get_projects():
        if p['id'] == project_id:
            project = p
            break
    
    if not project:
        return redirect(url_for('projects'))
    
    evidence_items = time_entry_app.evidence_db.get_evidence_for_project(project_id)
    
    return render_template('project_detail.html', project=project, evidence_items=evidence_items)

@app.route('/preview-evidence', methods=['POST'])
def preview_evidence():
    """Preview evidence that would be sent to AI for time entry generation"""
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    evidence_types = data.get('evidence_types', ['email', 'sms', 'phone_call', 'docket'])
    
    if not start_date or not end_date:
        return jsonify({'error': 'Start date and end date are required'}), 400
    
    try:
        # Get evidence for the date range, filtered by requested types
        filters = {
            'start_date': start_date,
            'end_date': end_date
        }
        
        # Create a result object by evidence type
        result = {}
        
        # Helper function to sanitize evidence items for JSON serialization
        def sanitize_evidence(items):
            sanitized = []
            for item in items:
                # Create a new dict with only serializable values
                clean_item = {}
                for key, value in item.items():
                    # Skip problematic fields entirely
                    if key in ['raw_data', 'data']:
                        continue
                        
                    # Handle non-serializable types
                    if isinstance(value, (int, str, bool, list, dict)) or value is None:
                        clean_item[key] = value
                    elif isinstance(value, float):
                        # Convert NaN and infinity to null
                        if math.isnan(value) or math.isinf(value):
                            clean_item[key] = None
                        else:
                            clean_item[key] = value
                    else:
                        # Convert other types to string
                        clean_item[key] = str(value)
                sanitized.append(clean_item)
            return sanitized
                
        # Get each type of evidence separately based on selected types
        if 'email' in evidence_types:
            filters['type'] = 'email'
            email_items = time_entry_app.evidence_db.query_evidence(filters)
            result['emails'] = sanitize_evidence(email_items)
        
        if 'sms' in evidence_types:
            filters['type'] = 'sms'
            sms_items = time_entry_app.evidence_db.query_evidence(filters)
            result['sms'] = sanitize_evidence(sms_items)
        
        if 'phone_call' in evidence_types:
            filters['type'] = 'phone_call'
            phone_items = time_entry_app.evidence_db.query_evidence(filters)
            result['phone_calls'] = sanitize_evidence(phone_items)
        
        if 'docket' in evidence_types:
            filters['type'] = 'docket'
            docket_items = time_entry_app.evidence_db.query_evidence(filters)
            result['docket_entries'] = sanitize_evidence(docket_items)
        
        # Use a custom JSON encoder with improved NaN handling
        class CustomJSONEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, float):
                    if math.isnan(obj) or math.isinf(obj):
                        return None
                return super().default(obj)
        
        # Manually convert to string to ensure proper handling
        json_str = json.dumps(result, cls=CustomJSONEncoder)
        # Return a proper response with correct mime type
        return app.response_class(
            response=json_str,
            status=200,
            mimetype='application/json'
        )
    except Exception as e:
        print(f"Error previewing evidence: {str(e)}")
        import traceback
        error_details = traceback.format_exc()
        print(error_details)
        
        # First try to handle known error cases more gracefully
        error_message = str(e)
        
        if "JSON" in error_message or "NaN" in error_message:
            # Problems with JSON serialization
            return jsonify({
                'error': "Data serialization error",
                'details': "There was a problem with the evidence data format. Some fields couldn't be properly converted to JSON. Try selecting a different date range or evidence types.",
                'technical_details': error_message
            }), 500
            
        # Generic error handling
        return jsonify({
            'error': f"Error previewing evidence: {str(e)}",
            'details': "An unexpected error occurred when retrieving evidence data. Please try again with a different date range.",
            'technical_details': error_details.split("\n")[-5:] # Just the last few lines
        }), 500

@app.route('/generate-time-entries', methods=['GET', 'POST'])
def generate_time_entries():
    """Generate time entries"""
    if request.method == 'POST':
        data = request.json
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        evidence_types = data.get('evidence_types', ['email', 'sms', 'phone_call', 'docket'])
        system_prompt = data.get('system_prompt')
        activity_codes = data.get('activity_codes')
        prompt_template = data.get('prompt_template')
        custom_prompt = data.get('custom_prompt')
        
        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400
        
        # Debugging log
        print(f"Generating time entries for {start_date} to {end_date}")
        print(f"Evidence types: {evidence_types}")
        
        try:
            # Log what we're doing
            print(f"Calling generate_time_entries_for_date_range with parameters:")
            print(f"  start_date: {start_date}")
            print(f"  end_date: {end_date}")
            print(f"  evidence_types: {evidence_types}")
            if system_prompt:
                print(f"  system_prompt length: {len(system_prompt)} chars")
            if activity_codes:
                print(f"  activity_codes length: {len(activity_codes)} chars")
            if prompt_template:
                print(f"  prompt_template length: {len(prompt_template)} chars")
            if custom_prompt:
                print(f"  custom_prompt length: {len(custom_prompt)} chars")
                
            # First check if there's evidence for the date range
            filters = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            # Check if we have evidence for this date range
            if evidence_types:
                total_evidence = 0
                for evidence_type in evidence_types:
                    type_filters = filters.copy()
                    type_filters['type'] = evidence_type
                    count = len(time_entry_app.evidence_db.query_evidence(type_filters))
                    total_evidence += count
                    print(f"Found {count} items of type {evidence_type}")
            else:
                all_evidence = time_entry_app.evidence_db.query_evidence(filters)
                total_evidence = len(all_evidence)
                print(f"Found {total_evidence} total evidence items")
                
            if total_evidence == 0:
                return jsonify({
                    'success': False, 
                    'error': 'No evidence found for the selected date range.',
                    'details': 'Please select a date range that contains evidence data, or upload new evidence data.'
                })
                
            # Pass the additional parameters to the generator function
            entries = time_entry_app.generate_time_entries_for_date_range(
                start_date, 
                end_date,
                evidence_types=evidence_types,
                system_prompt=system_prompt,
                activity_codes=activity_codes,
                prompt_template=prompt_template,
                custom_prompt=custom_prompt
            )
            
            print(f"Generated {len(entries) if entries else 0} entries")
            
            # Debug print the first entry if available
            if entries and len(entries) > 0:
                print("Sample generated entry:")
                for key, value in entries[0].items():
                    print(f"  {key}: {value}")
            
            if entries and len(entries) > 0:
                # Sanitize entries to ensure JSON serialization
                sanitized_entries = []
                for entry in entries:
                    clean_entry = {}
                    for key, value in entry.items():
                        # Skip problematic fields
                        if key in ['raw_data', 'data']:
                            continue
                            
                        # Handle non-serializable types
                        if isinstance(value, (int, str, bool, list, dict)) or value is None:
                            clean_entry[key] = value
                        elif isinstance(value, float):
                            # Convert NaN and infinity to null
                            if math.isnan(value) or math.isinf(value):
                                clean_entry[key] = None
                            else:
                                clean_entry[key] = value
                        else:
                            # Convert other types to string
                            clean_entry[key] = str(value)
                    sanitized_entries.append(clean_entry)
                
                # Use a custom JSON encoder for the response
                class CustomJSONEncoder(json.JSONEncoder):
                    def default(self, obj):
                        if isinstance(obj, float):
                            if math.isnan(obj) or math.isinf(obj):
                                return None
                        return super().default(obj)
                
                # Create a proper response
                json_str = json.dumps({'success': True, 'entries': sanitized_entries}, cls=CustomJSONEncoder)
                return app.response_class(
                    response=json_str,
                    status=200,
                    mimetype='application/json'
                )
            else:
                # No entries were generated but no error occurred
                return jsonify({
                    'success': False, 
                    'error': 'No time entries were generated for the selected date range.',
                    'details': 'The AI was unable to generate time entries from the available evidence. Try adjusting your prompt or date range.'
                })
        except Exception as e:
            print(f"Error generating time entries: {str(e)}")
            import traceback
            error_details = traceback.format_exc()
            print(error_details)
            
            return jsonify({
                'success': False,
                'error': f"Error generating time entries: {str(e)}",
                'details': error_details
            }), 500
    
    # For GET requests, get the date range from query parameters
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    return render_template('generate_entries.html', start_date=start_date, end_date=end_date)

@app.route('/time-entries')
def time_entries():
    """View time entries"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    activity_type = request.args.get('activity_type')
    
    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    if activity_type:
        filters['type'] = activity_type
    
    entries = time_entry_app.evidence_db.query_time_entries(filters)
    
    # Debug to console what fields are available
    if entries and len(entries) > 0:
        print(f"Sample time entry fields: {list(entries[0].keys())}")
        print(f"Sample time entry values for first entry:")
        for key, value in entries[0].items():
            print(f"  {key}: {value}")
    
    return render_template(
        'time_entries.html', 
        entries=entries, 
        start_date=start_date, 
        end_date=end_date,
        activity_type=activity_type
    )
@app.route('/export-time-entries')
def export_time_entries():
    """Export time entries to CSV"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Create a temporary file for the CSV
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    temp_file.close()
    
    time_entry_app.export_time_entries(temp_file.name, start_date, end_date)
    
    return send_file(
        temp_file.name, 
        as_attachment=True,
        download_name='time_entries.csv',
        mimetype='text/csv'
    )

@app.route('/evidence/<evidence_id>')
def view_evidence(evidence_id):
    """View a specific evidence item"""
    evidence = time_entry_app.evidence_db.get_evidence_by_id(evidence_id)
    if not evidence:
        return redirect(url_for('timeline'))
    
    related_evidence = time_entry_app.evidence_db.get_related_evidence(evidence_id)
    time_entries = time_entry_app.evidence_db.get_time_entries_for_evidence(evidence_id)
    
    return render_template(
        'evidence_detail.html',
        evidence=evidence,
        related_evidence=related_evidence,
        time_entries=time_entries
    )

@app.route('/time-entry/<entry_id>')
def view_time_entry(entry_id):
    """View a specific time entry"""
    entry = time_entry_app.evidence_db.get_time_entry_by_id(entry_id)
    if not entry:
        return redirect(url_for('time_entries'))
    
    evidence_items = time_entry_app.evidence_db.get_evidence_for_time_entry(entry_id)
    
    return render_template(
        'time_entry_detail.html',
        entry=entry,
        evidence_items=evidence_items
    )
@app.route('/api/project-backups')
def api_project_backups():
    """API endpoint to get available project backups"""
    try:
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute('SELECT * FROM project_backups ORDER BY created_at DESC')
        backups_list = cursor.fetchall()
        backups = [dict(row) for row in backups_list]
        
        return jsonify({'backups': backups})
    except Exception as e:
        # Check if the table exists
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='project_backups'")
        if not cursor.fetchone():
            # Create the table if it doesn't exist
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_backups (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')
            time_entry_app.evidence_db.conn.commit()
            return jsonify({'backups': []})
        
        return jsonify({'error': str(e)}), 500

@app.route('/api/evidence')
def api_evidence():
    """API endpoint to get evidence items"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    evidence_type = request.args.get('type')
    
    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    if evidence_type:
        filters['type'] = evidence_type
    
    evidence_items = time_entry_app.evidence_db.query_evidence(filters)
    return jsonify({'evidence': evidence_items})

@app.route('/api/time-entries')
def api_time_entries():
    """API endpoint to get time entries"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    filters = {}
    if start_date:
        filters['start_date'] = start_date
    if end_date:
        filters['end_date'] = end_date
    
    entries = time_entry_app.evidence_db.query_time_entries(filters)
    return jsonify({'time_entries': entries})

@app.route('/api/stats')
def api_stats():
    """API endpoint to get statistics"""
    # Count evidence by type
    evidence_stats = {}
    for evidence_type in ['email', 'sms', 'docket', 'phone_call']:
        evidence_stats[evidence_type] = len(time_entry_app.evidence_db.query_evidence({'type': evidence_type}))
    
    # Count time entries
    time_entries = time_entry_app.evidence_db.query_time_entries({})
    total_hours = sum(entry.get('hours', 0) for entry in time_entries)
    total_billable = sum(entry.get('billable', 0) for entry in time_entries)
    
    # Get relationship count
    cursor = time_entry_app.evidence_db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM evidence_relationships')
    relationship_count = cursor.fetchone()[0]
    
    stats = {
        **evidence_stats,
        'time_entry': len(time_entries),
        'generated_entries': len([e for e in time_entries if e.get('generated', False)]),
        'total_hours': round(total_hours, 1),
        'total_billable': round(total_billable, 2),
        'relationships': relationship_count
    }
    
    return jsonify({'stats': stats})

@app.route('/api/case-context')
def api_case_context():
    """API endpoint to get case context"""
    context = time_entry_app.evidence_db.get_case_context()
    return jsonify({'context': context})

@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M'):
    """Format a datetime string"""
    if not value:
        return ''
    
    try:
        if 'T' in value:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(value)
        return dt.strftime(format)
    except:
        return value
@app.route('/save-project-state', methods=['POST'])
def save_project_state():
    """Save the current project state"""
    data = request.json
    name = data.get('name', f'Project Backup {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    description = data.get('description', 'Automatic backup of project state')
    
    try:
        # Create a backup in the database
        cursor = time_entry_app.evidence_db.conn.cursor()
        
        # Create backup entry
        backup_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO project_backups (id, name, description, created_at)
            VALUES (?, ?, ?, datetime('now'))
        ''', (backup_id, name, description))
        
        # Get the current case context
        context = time_entry_app.evidence_db.get_case_context()
        if context:
            cursor.execute('''
                INSERT INTO backup_case_context (backup_id, context_data)
                VALUES (?, ?)
            ''', (backup_id, json.dumps(context)))
        
        time_entry_app.evidence_db.conn.commit()
        
        return jsonify({'success': True, 'backup_id': backup_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/clear-project', methods=['POST'])
def clear_project():
    """Clear the current project and start fresh"""
    try:
        # First save current state
        backup_id = str(uuid.uuid4())
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute('''
            INSERT INTO project_backups (id, name, description, created_at)
            VALUES (?, ?, ?, datetime('now'))
        ''', (backup_id, f'Auto-backup before clear {datetime.now().strftime("%Y-%m-%d %H:%M")}', 
              'Automatic backup before project clear'))
        
        context = time_entry_app.evidence_db.get_case_context()
        if context:
            cursor.execute('''
                INSERT INTO backup_case_context (backup_id, context_data)
                VALUES (?, ?)
            ''', (backup_id, json.dumps(context)))
        
        # Now clear the current project data
        tables_to_clear = [
            'evidence', 'time_entries', 'evidence_relationships', 
            'evidence_time_entry_links', 'case_context', 'projects',
            'evidence_project_links'
        ]
        
        for table in tables_to_clear:
            cursor.execute(f'DELETE FROM {table}')
        
        # Keep the upload history but mark as archived
        cursor.execute('UPDATE uploads SET archived = 1')
        
        time_entry_app.evidence_db.conn.commit()
        
        return jsonify({'success': True, 'backup_id': backup_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/restore-project/<backup_id>', methods=['POST'])
def restore_project(backup_id):
    """Restore a project from a backup"""
    try:
        # First clear current project
        cursor = time_entry_app.evidence_db.conn.cursor()
        tables_to_clear = [
            'evidence', 'time_entries', 'evidence_relationships', 
            'evidence_time_entry_links', 'case_context', 'projects',
            'evidence_project_links'
        ]
        
        for table in tables_to_clear:
            cursor.execute(f'DELETE FROM {table}')
        
        # Then restore from backup
        # This would be implemented based on how you store the backups
        
        time_entry_app.evidence_db.conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/evidence/<evidence_id>')
def api_evidence_detail(evidence_id):
    """API endpoint to get a specific evidence item"""
    evidence = time_entry_app.evidence_db.get_evidence_by_id(evidence_id)
    if not evidence:
        return jsonify({'error': 'Evidence not found'}), 404
    
    return jsonify({'evidence': evidence})

@app.route('/api/update-contact', methods=['POST'])
def api_update_contact():
    """API endpoint to update contact information for an evidence item"""
    data = request.json
    evidence_id = data.get('evidence_id')
    contact_name = data.get('contact_name')
    contact_email = data.get('contact_email', '')
    
    if not evidence_id or not contact_name:
        return jsonify({'success': False, 'error': 'Evidence ID and contact name are required'}), 400
    
    try:
        # Get the existing evidence
        evidence = time_entry_app.evidence_db.get_evidence_by_id(evidence_id)
        if not evidence:
            return jsonify({'success': False, 'error': 'Evidence not found'}), 404
        
        # Update the contact information
        evidence['contact'] = contact_name
        evidence['contact_email'] = contact_email
        
        # Save back to the database
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute(
            'UPDATE evidence SET data = ? WHERE id = ?',
            (json.dumps(evidence), evidence_id)
        )
        time_entry_app.evidence_db.conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/analyze-timeline', methods=['POST'])
def analyze_timeline():
    """Analyze timeline with AI and suggest relationships and time entries"""
    data = request.json
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': 'Start date and end date are required'}), 400
    
    try:
        # Get evidence for the date range
        filters = {
            'start_date': start_date,
            'end_date': end_date
        }
        evidence_items = time_entry_app.evidence_db.query_evidence(filters)
        
        if not evidence_items:
            return jsonify({
                'message': 'No evidence items found in the selected date range',
                'relationships': [],
                'time_entries': []
            })
        
        # Get existing time entries for the date range
        existing_entries = time_entry_app.evidence_db.query_time_entries(filters)
        
        # Get case context
        context = time_entry_app.evidence_db.get_case_context()
        
        # Prepare prompt for OpenAI
        prompt = f"""
        You are a legal assistant specialized in analyzing legal timelines and suggesting time entries.
        
        Case Context:
        {json.dumps(context) if context else "No case context provided"}
        
        I'll provide evidence items from {start_date} to {end_date}. Please analyze them to:
        1. Identify relationships between items that should be connected
        2. Suggest legal time entries that should be billed based on the evidence
        
        Here are the evidence items:
        {json.dumps(evidence_items[:50])}  # Limit to avoid token limits
        
        Existing time entries for this period:
        {json.dumps(existing_entries)}
        
        Please respond with JSON in this format:
        {{
            "relationships": [
                {{
                    "id": "unique_id",
                    "evidence_id_1": "id_of_first_item",
                    "evidence_id_2": "id_of_second_item",
                    "relationship_type": "type_of_relationship",
                    "confidence": 0.8,
                    "description": "Human-readable description of the relationship"
                }}
            ],
            "time_entries": [
                {{
                    "id": "unique_id",
                    "date": "YYYY-MM-DD",
                    "hours": 0.5,
                    "description": "Detailed description of work performed",
                    "activity_category": "category_of_activity",
                    "evidence_ids": ["id1", "id2"]
                }}
            ]
        }}
        
        Only suggest time entries that are not already covered by existing entries.
        Focus on billable activities that require attorney time.
        """
        
        # Store the prompt for debugging
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute('''
            INSERT INTO ai_analysis_logs (id, prompt, created_at)
            VALUES (?, ?, datetime('now'))
        ''', (str(uuid.uuid4()), prompt))
        time_entry_app.evidence_db.conn.commit()
        
        # Call OpenAI
        result = time_entry_app.time_entry_generator.llm.predict(prompt)
        
        # Store the raw result
        log_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO ai_analysis_logs (id, prompt, result, created_at)
            VALUES (?, ?, ?, datetime('now'))
        ''', (log_id, prompt, result))
        time_entry_app.evidence_db.conn.commit()
        
        try:
            # Parse the JSON response
            analysis = json.loads(result)
            
            # Generate unique IDs for suggestions
            for rel in analysis.get('relationships', []):
                if 'id' not in rel:
                    rel['id'] = str(uuid.uuid4())
                
                # Store relationship suggestion for later
                cursor.execute('''
                    INSERT INTO ai_relationship_suggestions 
                    (id, evidence_id_1, evidence_id_2, relationship_type, confidence, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    rel['id'], 
                    rel['evidence_id_1'], 
                    rel['evidence_id_2'], 
                    rel['relationship_type'],
                    rel['confidence'],
                    rel['description']
                ))
            
            for entry in analysis.get('time_entries', []):
                if 'id' not in entry:
                    entry['id'] = str(uuid.uuid4())
                
                # Store time entry suggestion for later
                cursor.execute('''
                    INSERT INTO ai_time_entry_suggestions 
                    (id, data)
                    VALUES (?, ?)
                ''', (
                    entry['id'],
                    json.dumps(entry)
                ))
            
            time_entry_app.evidence_db.conn.commit()
            
            # Add the log ID to the response
            analysis['log_id'] = log_id
            
            return jsonify(analysis)
            
        except json.JSONDecodeError:
            # If the response isn't valid JSON, try to extract JSON from the text
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
            if json_match:
                try:
                    analysis = json.loads(json_match.group(1))
                    analysis['log_id'] = log_id
                    return jsonify(analysis)
                except json.JSONDecodeError:
                    pass
            
            return jsonify({
                'error': 'Could not parse AI response',
                'raw_response': result,
                'log_id': log_id
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/apply-suggestions', methods=['POST'])
def apply_suggestions():
    """Apply the selected AI suggestions"""
    data = request.json
    relationship_ids = data.get('relationships', [])
    time_entry_ids = data.get('time_entries', [])
    
    try:
        cursor = time_entry_app.evidence_db.conn.cursor()
        
        # Apply relationships
        for rel_id in relationship_ids:
            # Get the relationship suggestion
            cursor.execute('SELECT * FROM ai_relationship_suggestions WHERE id = ?', (rel_id,))
            rel = cursor.fetchone()
            
            if rel:
                # Create the relationship
                time_entry_app.evidence_db.link_related_evidence(
                    rel['evidence_id_1'],
                    rel['evidence_id_2'],
                    rel['relationship_type'],
                    rel['confidence']
                )
                
                # Mark as applied
                cursor.execute(
                    'UPDATE ai_relationship_suggestions SET applied = 1 WHERE id = ?',
                    (rel_id,)
                )
        
        # Apply time entries
        for entry_id in time_entry_ids:
            # Get the time entry suggestion
            cursor.execute('SELECT * FROM ai_time_entry_suggestions WHERE id = ?', (entry_id,))
            entry_row = cursor.fetchone()
            
            if entry_row:
                # Create the time entry
                entry_data = json.loads(entry_row['data'])
                entry_id = str(uuid.uuid4())
                
                # Standard fields
                new_entry = {
                    'id': entry_id,
                    'date': entry_data['date'],
                    'hours': float(entry_data['hours']),
                    'description': entry_data['description'],
                    'activity_category': entry_data['activity_category'],
                    'generated': True,
                    'billable': float(entry_data['hours']) * 250.0,  # Example rate
                    'rate': 250.0
                }
                
                # Insert the time entry
                time_entry_app.evidence_db.insert_time_entries([new_entry])
                
                # Link to evidence
                for evidence_id in entry_data.get('evidence_ids', []):
                    time_entry_app.evidence_db.link_evidence_to_time_entry(evidence_id, entry_id)
                
                # Mark as applied
                cursor.execute(
                    'UPDATE ai_time_entry_suggestions SET applied = 1 WHERE id = ?',
                    (entry_data['id'],)
                )
        
        time_entry_app.evidence_db.conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analysis-logs/<log_id>')
def get_analysis_log(log_id):
    """Get an AI analysis log for debugging"""
    try:
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute('SELECT * FROM ai_analysis_logs WHERE id = ?', (log_id,))
        log = cursor.fetchone()
        
        if not log:
            return jsonify({'error': 'Log not found'}), 404
        
        return jsonify({
            'id': log['id'],
            'prompt': log['prompt'],
            'result': log['result'],
            'created_at': log['created_at']
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/create-mock-time-entries', methods=['GET'])
def create_mock_time_entries():
    """Create mock time entries for testing"""
    try:
        # Create a list of sample time entries
        mock_entries = [
            {
                'id': str(uuid.uuid4()),
                'date': '2024-06-01',
                'hours': 1.5,
                'activity_category': 'legal_research',
                'description': 'Reviewed case documents and prepared research memo',
                'user': 'Attorney',
                'rate': 250.0,
                'billable': 375.0,
                'matter': 'Sample v. Test',
                'note': 'Review of key documents for upcoming hearing'
            },
            {
                'id': str(uuid.uuid4()),
                'date': '2024-06-02',
                'hours': 0.8,
                'activity_category': 'client_communication',
                'description': 'Phone call with client regarding case updates',
                'user': 'Attorney',
                'rate': 250.0,
                'billable': 200.0,
                'matter': 'Sample v. Test',
                'note': 'Discussed upcoming deposition and preparation steps'
            },
            {
                'id': str(uuid.uuid4()),
                'date': '2024-06-03',
                'hours': 2.0,
                'activity_category': 'document_drafting',
                'description': 'Drafted motion to compel discovery responses',
                'user': 'Attorney',
                'rate': 250.0,
                'billable': 500.0,
                'matter': 'Sample v. Test',
                'note': 'Prepared motion and supporting declaration'
            }
        ]
        
        # Insert the mock entries into the database
        count = time_entry_app.evidence_db.insert_time_entries(mock_entries)
        
        return jsonify({
            'success': True,
            'message': f'Created {count} mock time entries',
            'entries': mock_entries
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    
if __name__ == '__main__':
    app.run(debug=True)