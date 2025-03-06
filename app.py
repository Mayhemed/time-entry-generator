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

#############################################################
# API ROUTES - These routes serve JSON data for the frontend
#############################################################

@app.route('/api/test')
def api_test():
    """Simple test API endpoint"""
    return jsonify({
        'status': 'success',
        'message': 'API is working',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/debug/routes')
def debug_routes():
    """Show all registered routes"""
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            'endpoint': rule.endpoint,
            'methods': [method for method in rule.methods if method != 'OPTIONS' and method != 'HEAD'],
            'url': str(rule)
        })
    return jsonify(routes)

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

@app.route('/api/evidence/<evidence_id>')
def api_evidence_detail(evidence_id):
    """API endpoint to get a specific evidence item"""
    evidence = time_entry_app.evidence_db.get_evidence_by_id(evidence_id)
    if not evidence:
        return jsonify({'error': 'Evidence not found'}), 404
    
    return jsonify({'evidence': evidence})

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

@app.route('/api/update-time-entry', methods=['POST'])
def api_update_time_entry():
    """API endpoint to update a time entry"""
    data = request.json
    entry_id = data.get('id')
    
    if not entry_id:
        return jsonify({'success': False, 'error': 'Time entry ID is required'}), 400
    
    try:
        # Get the existing time entry
        entry = time_entry_app.evidence_db.get_time_entry_by_id(entry_id)
        if not entry:
            return jsonify({'success': False, 'error': 'Time entry not found'}), 404
        
        # Update the fields provided in the request
        fields_to_update = [
            'date', 'quantity', 'hours', 'note', 'description', 'activity_category', 
            'matter', 'rate', 'price', 'billable', 'activity_user', 'user', 'activity_description'
        ]
        
        for field in fields_to_update:
            if field in data:
                entry[field] = data[field]
        
        # If quantity is updated, update price based on rate
        if 'quantity' in data and 'rate' in entry:
            entry['price'] = float(data['quantity']) * float(entry['rate'])
        
        # If hours is updated but not quantity, update quantity
        if 'hours' in data and 'quantity' not in data:
            entry['quantity'] = float(data['hours'])
            
        # If price and rate are both specified, don't override
        if 'price' in data and 'rate' in data:
            # Use the provided values
            pass
        # If only rate is updated, update price based on quantity
        elif 'rate' in data and ('quantity' in entry or 'hours' in entry):
            quantity = float(entry.get('quantity', entry.get('hours', 0)))
            entry['price'] = quantity * float(data['rate'])
        # If only price is updated, set billable to match
        elif 'price' in data:
            entry['billable'] = float(data['price'])
        
        # Save back to the database
        cursor = time_entry_app.evidence_db.conn.cursor()
        cursor.execute(
            'UPDATE time_entries SET data = ? WHERE id = ?',
            (json.dumps(entry), entry_id)
        )
        time_entry_app.evidence_db.conn.commit()
        
        return jsonify({'success': True, 'entry': entry})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete-time-entries', methods=['POST'])
def api_delete_time_entries():
    """API endpoint to delete time entries"""
    data = request.json
    entry_ids = data.get('entry_ids', [])
    
    if not entry_ids:
        return jsonify({'success': False, 'error': 'No time entry IDs provided'}), 400
    
    try:
        # Delete each time entry
        deleted_count = 0
        cursor = time_entry_app.evidence_db.conn.cursor()
        
        for entry_id in entry_ids:
            # First remove any links to evidence
            cursor.execute('DELETE FROM evidence_time_entry_links WHERE time_entry_id = ?', (entry_id,))
            
            # Then delete the time entry
            cursor.execute('DELETE FROM time_entries WHERE id = ?', (entry_id,))
            deleted_count += cursor.rowcount
        
        time_entry_app.evidence_db.conn.commit()
        
        return jsonify({
            'success': True, 
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} time entries'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/api/evidence-json/<date_range>')
def get_evidence_json(date_range):
    """Return all evidence as a structured JSON for use in the enhanced UI"""
    try:
        # Debug info
        app.logger.info(f"Evidence JSON endpoint called with date_range: {date_range}")
        print(f"Evidence JSON endpoint called with date_range: {date_range}")
        
        # Parse date range if provided
        start_date = None
        end_date = None
        
        if date_range != 'all':
            dates = date_range.split('_to_')
            if len(dates) == 2:
                start_date = dates[0]
                end_date = dates[1]
        
        # Debug info
        app.logger.info(f"Parsed date range: start={start_date}, end={end_date}")
        print(f"Parsed date range: start={start_date}, end={end_date}")
        
        # Create a simple response for testing
        return jsonify({
            'emails': [],
            'sms': [],
            'docket_entries': [],
            'phone_calls': [],
            'time_entries': []
        })
        
        # ORIGINAL CODE COMMENTED OUT FOR TESTING
        """
        # Get all types of evidence
        evidence_data = {
            'emails': [],
            'sms': [],
            'docket_entries': [],
            'phone_calls': [],
            'time_entries': []
        }
        
        # Get evidence for each type
        for evidence_type in evidence_data.keys():
            if evidence_type == 'time_entries':
                # Time entries are structured differently
                filters = {}
                if start_date:
                    filters['start_date'] = start_date
                if end_date:
                    filters['end_date'] = end_date
                
                entries = time_entry_app.evidence_db.query_time_entries(filters)
                evidence_data['time_entries'] = entries
            else:
                # Map our internal type names to the API type names
                api_type_map = {
                    'emails': 'email',
                    'sms': 'sms',
                    'docket_entries': 'docket',
                    'phone_calls': 'phone_call'
                }
                
                filters = {
                    'type': api_type_map[evidence_type]
                }
                
                if start_date:
                    filters['start_date'] = start_date
                if end_date:
                    filters['end_date'] = end_date
                
                items = time_entry_app.evidence_db.query_evidence(filters)
                evidence_data[evidence_type] = items
        
        # Clean up any NaN or infinity values for JSON serialization
        def clean_for_json(obj):
            if isinstance(obj, dict):
                return {k: clean_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_for_json(i) for i in obj]
            elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            else:
                return obj
        
        cleaned_data = clean_for_json(evidence_data)
        
        return jsonify(cleaned_data)
        """
    except Exception as e:
        app.logger.error(f"Error in evidence JSON endpoint: {str(e)}")
        print(f"Error in evidence JSON endpoint: {str(e)}")
        import traceback
        error_traceback = traceback.format_exc()
        app.logger.error(error_traceback)
        print(error_traceback)
        return jsonify({
            "error": str(e),
            "traceback": error_traceback,
            "endpoint": f"/api/evidence-json/{date_range}"
        }), 500

@app.route('/api/prompts', methods=['GET', 'POST'])
def manage_prompts():
    """Manage saved AI prompts"""
    if request.method == 'GET':
        # Return saved prompts from the database
        try:
            cursor = time_entry_app.evidence_db.conn.cursor()
            cursor.execute('SELECT * FROM saved_prompts ORDER BY updated_at DESC')
            prompts = cursor.fetchall()
            return jsonify({
                'prompts': [dict(prompt) for prompt in prompts]
            })
        except Exception as e:
            print(f"Error fetching prompts: {e}")
            return jsonify({"error": str(e)}), 500
    
    elif request.method == 'POST':
        # Save a new prompt
        try:
            data = request.json
            prompt_id = data.get('id') or str(uuid.uuid4())
            
            cursor = time_entry_app.evidence_db.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO saved_prompts
                (id, name, template, system_prompt, description, goal, tags, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                prompt_id,
                data.get('name', 'Unnamed Prompt'),
                data.get('template', ''),
                data.get('systemPrompt', ''),
                data.get('description', ''),
                data.get('goal', 'time_entries'),
                json.dumps(data.get('tags', []))
            ))
            time_entry_app.evidence_db.conn.commit()
            
            return jsonify({
                'success': True,
                'prompt_id': prompt_id
            })
        except Exception as e:
            print(f"Error saving prompt: {e}")
            return jsonify({"error": str(e)}), 500

@app.route('/api/prompts/<prompt_id>', methods=['GET', 'DELETE'])
def prompt_operations(prompt_id):
    """Get or delete a specific prompt"""
    try:
        cursor = time_entry_app.evidence_db.conn.cursor()
        
        if request.method == 'GET':
            cursor.execute('SELECT * FROM saved_prompts WHERE id = ?', (prompt_id,))
            prompt = cursor.fetchone()
            
            if not prompt:
                return jsonify({"error": "Prompt not found"}), 404
            
            return jsonify(dict(prompt))
        
        elif request.method == 'DELETE':
            cursor.execute('DELETE FROM saved_prompts WHERE id = ?', (prompt_id,))
            time_entry_app.evidence_db.conn.commit()
            
            return jsonify({
                'success': True,
                'message': f"Prompt {prompt_id} deleted successfully"
            })
    
    except Exception as e:
        print(f"Error with prompt operation: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/run-prompt', methods=['POST'])
def run_prompt():
    """Run a prompt against selected evidence"""
    try:
        data = request.json
        prompt_template = data.get('prompt', {}).get('template')
        system_prompt = data.get('prompt', {}).get('systemPrompt')
        goal = data.get('prompt', {}).get('goal', 'time_entries')
        selected_evidence = data.get('selectedEvidence', {})
        date_range = data.get('dateRange', {})
        
        if not prompt_template:
            return jsonify({"error": "No prompt template provided"}), 400
        
        # Collect the selected evidence
        evidence_to_process = {}
        
        for evidence_type, ids in selected_evidence.items():
            if not ids or len(ids) == 0:
                continue
            
            # Get the evidence from the database
            if evidence_type == 'time_entries':
                # Time entries need to be handled differently
                entries = []
                for entry_id in ids:
                    entry = time_entry_app.evidence_db.get_time_entry_by_id(entry_id)
                    if entry:
                        entries.append(entry)
                evidence_to_process[evidence_type] = entries
            else:
                # Regular evidence
                items = []
                for item_id in ids:
                    item = time_entry_app.evidence_db.get_evidence_by_id(item_id)
                    if item:
                        items.append(item)
                evidence_to_process[evidence_type] = items
        
        # Format date range for the prompt
        start_date = date_range.get('start', '')
        end_date = date_range.get('end', '')
        
        # Replace placeholders in the prompt
        formatted_prompt = prompt_template.replace('{start_date}', start_date).replace('{end_date}', end_date)
        
        # Set up the AI model based on goal
        ai_model = data.get('ai_model', 'gpt-3.5-turbo')
        
        # Set the model in the time entry generator
        provider = 'anthropic' if 'claude' in ai_model else 'openai'
        time_entry_app.time_entry_generator.set_model_params(
            model_id=ai_model,
            provider=provider,
            temperature=0.7
        )
        
        # Process based on goal
        response = None
        
        if goal == 'time_entries':
            # Use the existing time entry generation logic, but with our custom prompt
            response = time_entry_app.time_entry_generator.generate_entries_for_period(
                start_date, 
                end_date,
                custom_prompt=formatted_prompt
            )
            
            # Insert the entries into the database if requested
            if data.get('save_entries', False) and response:
                time_entry_app.evidence_db.insert_time_entries(response)
                
                # Link evidence to time entries if we have IDs in the response
                for entry in response:
                    if 'evidenceids' in entry:
                        entry_id = entry['id']
                        evidenceids_str = entry['evidenceids']
                        
                        # Parse evidence IDs
                        evidence_ids = [id.strip() for id in re.split(r'[,;\s]+', evidenceids_str) if id.strip()]
                        
                        # Link each evidence ID to the entry
                        for evidence_id in evidence_ids:
                            time_entry_app.evidence_db.link_evidence_to_time_entry(evidence_id, entry_id)
            
            return jsonify({
                'success': True,
                'goal': goal,
                'results': response
            })
        else:
            # For other goals, call the LLM directly with the gathered evidence
            
            # Prepare evidence summary to include in the prompt
            evidence_summary = []
            
            for evidence_type, items in evidence_to_process.items():
                evidence_summary.append(f"--- {evidence_type.upper()} ({len(items)} items) ---")
                
                # Include a sample of the evidence
                sample_size = min(5, len(items))
                for i in range(sample_size):
                    item = items[i]
                    
                    if evidence_type == 'emails':
                        evidence_summary.append(f"Email {i+1}: {item.get('subject')} - From: {item.get('from')} - To: {item.get('to')}")
                    elif evidence_type == 'sms':
                        evidence_summary.append(f"SMS {i+1}: {item.get('text', '')[:50]}...")
                    elif evidence_type == 'docket_entries':
                        evidence_summary.append(f"Docket {i+1}: {item.get('event_type')} - {item.get('memo', '')[:50]}...")
                    elif evidence_type == 'phone_calls':
                        evidence_summary.append(f"Call {i+1}: {item.get('contact')} - Duration: {item.get('duration_seconds', 0) // 60} min")
                    elif evidence_type == 'time_entries':
                        evidence_summary.append(f"Time Entry {i+1}: {item.get('date')} - {item.get('hours')} hrs - {item.get('description')}")
                
                evidence_summary.append("\n")
            
            # Construct the full prompt with evidence summary
            full_prompt = f"""
            {formatted_prompt}
            
            Date Range: {start_date} to {end_date}
            
            Evidence Summary:
            {'\n'.join(evidence_summary)}
            """
            
            # Call the AI model
            result = time_entry_app.time_entry_generator.llm.predict(full_prompt)
            
            return jsonify({
                'success': True,
                'goal': goal,
                'results': result
            })
    
    except Exception as e:
        print(f"Error running prompt: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/export-selected', methods=['POST'])
def export_selected_evidence():
    """Export selected evidence to CSV"""
    try:
        data = request.json
        selected_evidence = data.get('selectedEvidence', {})
        
        if not any(ids for ids in selected_evidence.values()):
            return jsonify({"error": "No evidence selected"}), 400
        
        # Create a temporary file for the CSV
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        temp_file.close()
        
        # Collect all selected evidence
        all_items = []
        
        for evidence_type, ids in selected_evidence.items():
            if not ids or len(ids) == 0:
                continue
            
            # Get the evidence from the database
            for item_id in ids:
                if evidence_type == 'time_entries':
                    item = time_entry_app.evidence_db.get_time_entry_by_id(item_id)
                else:
                    item = time_entry_app.evidence_db.get_evidence_by_id(item_id)
                
                if item:
                    # Add a type field to distinguish in the export
                    item['evidence_type'] = evidence_type
                    all_items.append(item)
        
        if not all_items:
            return jsonify({"error": "No evidence found for the selected IDs"}), 404
        
        # Sort by date
        all_items.sort(key=lambda x: x.get('timestamp') or x.get('date') or '')
        
        # Convert to DataFrame for easy CSV export
        # First, flatten the items and select common fields
        flattened_items = []
        
        for item in all_items:
            flat_item = {
                'id': item.get('id'),
                'evidence_type': item.get('evidence_type'),
                'date': item.get('timestamp') or item.get('date'),
            }
            
            # Add type-specific fields
            if item.get('evidence_type') == 'emails':
                flat_item.update({
                    'subject': item.get('subject'),
                    'from': item.get('from'),
                    'to': item.get('to'),
                    'content': item.get('body')
                })
            elif item.get('evidence_type') == 'sms':
                flat_item.update({
                    'sender': item.get('sender_name'),
                    'direction': item.get('direction'),
                    'content': item.get('text')
                })
            elif item.get('evidence_type') == 'docket_entries':
                flat_item.update({
                    'event_type': item.get('event_type'),
                    'filed_by': item.get('filed_by'),
                    'content': item.get('memo')
                })
            elif item.get('evidence_type') == 'phone_calls':
                flat_item.update({
                    'contact': item.get('contact'),
                    'number': item.get('number'),
                    'duration_mins': (item.get('duration_seconds') or 0) // 60,
                    'call_type': item.get('call_type')
                })
            elif item.get('evidence_type') == 'time_entries':
                flat_item.update({
                    'hours': item.get('hours'),
                    'activity': item.get('activity_category'),
                    'content': item.get('description'),
                    'billable': item.get('billable')
                })
            
            flattened_items.append(flat_item)
        
        # Create DataFrame and export to CSV
        df = pd.DataFrame(flattened_items)
        df.to_csv(temp_file.name, index=False)
        
        return send_file(
            temp_file.name, 
            as_attachment=True,
            download_name='evidence_export.csv',
            mimetype='text/csv'
        )
    
    except Exception as e:
        print(f"Error exporting evidence: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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

@app.route('/build-timeline', methods=['POST'])
def build_timeline():
    """Build timeline and identify relationships"""
    relationship_count = time_entry_app.build_timeline()
    return jsonify({'relationship_count': relationship_count})

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

#############################################################
# UI ROUTES - These routes serve HTML pages for the frontend
#############################################################

@app.route('/')
def index():
    """Render the main dashboard page"""
    return render_template('index.html')

@app.route('/enhanced') 
def enhanced_ui():
    """Render the enhanced UI with React components"""
    return render_template('enhanced.html')

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

@app.route('/projects')
def projects():
    """View projects page"""
    all_projects = time_entry_app.evidence_db.get_projects()
    return render_template('projects.html', projects=all_projects)

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
        period_days = data.get('period_days', 7)  # Default to 7 days (weekly) if not specified
        debug_prompt = data.get('debug_prompt', False)  # Whether to return debug info about the prompt
        
        if not start_date or not end_date:
            return jsonify({'error': 'Start date and end date are required'}), 400
        
        # Ensure period_days is an integer
        try:
            period_days = int(period_days)
            if period_days < 1:
                period_days = 1  # Minimum of 1 day
            elif period_days > 31:
                period_days = 31  # Maximum of 31 days
        except (ValueError, TypeError):
            period_days = 7  # Default to weekly if conversion fails
        
        # Debugging log
        print(f"Generating time entries for {start_date} to {end_date}")
        print(f"Evidence types: {evidence_types}")
        print(f"Using {period_days}-day periods")
        
        try:
            # Log what we're doing
            print(f"Calling generate_time_entries_for_date_range with parameters:")
            print(f"  start_date: {start_date}")
            print(f"  end_date: {end_date}")
            print(f"  evidence_types: {evidence_types}")
            print(f"  period_days: {period_days}")
            print(f"  debug_prompt: {debug_prompt}")
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
                
            # Get AI model parameter
            ai_model = data.get('ai_model', 'gpt-3.5-turbo')
            print(f"Using AI model: {ai_model}")
            
            # Set the model in the time entry generator
            if ai_model != 'gpt-3.5-turbo':
                print(f"Setting generator to use model: {ai_model}")
                provider = 'anthropic' if 'claude' in ai_model else 'openai'
                time_entry_app.time_entry_generator.set_model_params(
                    model_id=ai_model,
                    provider=provider,
                    temperature=0.7
                )
            
            # Pass the additional parameters to the generator function
            result = time_entry_app.generate_time_entries_for_date_range(
                start_date, 
                end_date,
                evidence_types=evidence_types,
                system_prompt=system_prompt,
                activity_codes=activity_codes,
                prompt_template=prompt_template,
                custom_prompt=custom_prompt,
                period_days=period_days,
                debug_prompt=debug_prompt
            )
            
            # Handle result based on whether debug info was requested
            if debug_prompt and isinstance(result, dict) and "entries" in result and "debug_info" in result:
                entries = result["entries"]
                debug_info = result["debug_info"]
                print(f"Generated {len(entries) if entries else 0} entries with debug info")
            else:
                entries = result
                debug_info = None
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
                
                # Prepare response data
                response_data = {
                    'success': True, 
                    'entries': sanitized_entries
                }
                
                # Include debug info if requested and available
                if debug_prompt and debug_info:
                    # Sanitize debug info to ensure it's serializable
                    if 'evidence_samples' in debug_info:
                        # Make sure samples don't contain unserializable data
                        for sample_set in debug_info['evidence_samples']:
                            if 'sample' in sample_set:
                                for item in sample_set['sample']:
                                    for key in list(item.keys()):
                                        if not isinstance(item[key], (str, int, float, bool, list, dict)) or item[key] is None:
                                            item[key] = str(item[key])
                    
                    # Add log file path info if available
                    if 'debug_log_path' in debug_info:
                        log_path = debug_info['debug_log_path']
                        print(f"Debug log created at: {log_path}")
                        # Add a message to inform the user
                        debug_info['debug_message'] = f"Complete debug information has been logged to a file for detailed review."
                                            
                    # Add to response
                    response_data['debug_info'] = debug_info
                
                # Create a proper response
                json_str = json.dumps(response_data, cls=CustomJSONEncoder)
                return app.response_class(
                    response=json_str,
                    status=200,
                    mimetype='application/json'
                )
            else:
                # No entries were generated but debug info might be available
                response_data = {
                    'success': False, 
                    'error': 'No time entries were generated for the selected date range.',
                    'details': 'The AI was unable to generate time entries from the available evidence. Try adjusting your prompt or date range.'
                }
                
                # Include debug info if requested and available
                if debug_prompt and debug_info:
                    response_data['debug_info'] = debug_info
                    
                return jsonify(response_data)
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

# Template filter for formatting dates
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

# Run the app if executed directly
if __name__ == '__main__':
    app.run(debug=True)
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