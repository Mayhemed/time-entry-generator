import os
import sys
import pandas as pd
import json
import argparse
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from tqdm import tqdm

# Import our modules
from data_processors import (
    BaseProcessor, EmailProcessor, SMSProcessor, 
    DocketProcessor, PhoneCallProcessor, TimeEntryProcessor
)
from evidence_database import EvidenceDatabase, TimelineConstructor
from time_entry_generator import TimeEntryGeneratorSystem

def main():
    """Command-line interface for the Time Entry Generator/Auditor system"""
    parser = argparse.ArgumentParser(description="Time Entry Generator/Auditor")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Ingest data command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest data files")
    ingest_parser.add_argument("--email", help="Path to email CSV file")
    ingest_parser.add_argument("--sms", help="Path to SMS CSV file")
    ingest_parser.add_argument("--docket", help="Path to docket CSV file")
    ingest_parser.add_argument("--phone", help="Path to phone call CSV file")
    ingest_parser.add_argument("--time-entries", help="Path to existing time entries CSV file")
    ingest_parser.add_argument("--db", default="evidence.db", help="Path to database file")
    
    # Set case context command
    context_parser = subparsers.add_parser("set-context", help="Set case context")
    context_parser.add_argument("--name", required=True, help="Case name")
    context_parser.add_argument("--description", required=True, help="Case description")
    context_parser.add_argument("--parties", help="Path to JSON file with parties information")
    context_parser.add_argument("--db", default="evidence.db", help="Path to database file")
    
    # Build timeline command
    timeline_parser = subparsers.add_parser("build-timeline", help="Build timeline")
    timeline_parser.add_argument("--db", default="evidence.db", help="Path to database file")
    
    # Generate time entries command
    generate_parser = subparsers.add_parser("generate", help="Generate time entries")
    generate_parser.add_argument("--start-date", required=True, help="Start date (YYYY-MM-DD)")
    generate_parser.add_argument("--end-date", required=True, help="End date (YYYY-MM-DD)")
    generate_parser.add_argument("--output", required=True, help="Output CSV file path")
    generate_parser.add_argument("--db", default="evidence.db", help="Path to database file")
    generate_parser.add_argument("--api-key", help="OpenAI API key (or set OPENAI_API_KEY env var)")
    
    # Export time entries command
    export_parser = subparsers.add_parser("export", help="Export time entries")
    export_parser.add_argument("--output", required=True, help="Output CSV file path")
    export_parser.add_argument("--start-date", help="Start date filter (YYYY-MM-DD)")
    export_parser.add_argument("--end-date", help="End date filter (YYYY-MM-DD)")
    export_parser.add_argument("--db", default="evidence.db", help="Path to database file")
    
    args = parser.parse_args()
    
    if args.command == "ingest":
        app = TimeEntryApp(db_path=args.db)
        file_paths = {}
        
        if args.email:
            file_paths["email"] = args.email
        if args.sms:
            file_paths["sms"] = args.sms
        if args.docket:
            file_paths["docket"] = args.docket
        if args.phone:
            file_paths["phone_call"] = args.phone
        if args.time_entries:
            file_paths["time_entry"] = args.time_entries
        
        results = app.ingest_data_files(file_paths)
        for file_type, count in results.items():
            print(f"Ingested {count} {file_type} items")
    
    elif args.command == "set-context":
        app = TimeEntryApp(db_path=args.db)
        parties = None
        
        if args.parties:
            with open(args.parties, 'r') as f:
                parties = json.load(f)
        
        context_id = app.set_case_context(args.name, args.description, parties)
        print(f"Set case context with ID: {context_id}")
    
    elif args.command == "build-timeline":
        app = TimeEntryApp(db_path=args.db)
        relationship_count = app.build_timeline()
        print(f"Built timeline with {relationship_count} relationships")
        
        # Also suggest projects
        projects = app.suggest_projects()
        print(f"Suggested {len(projects)} projects:")
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project['name']}: {project['description']}")
    
    elif args.command == "generate":
        api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OpenAI API key is required. Set it with --api-key or OPENAI_API_KEY env var.")
            sys.exit(1)
        
        app = TimeEntryApp(db_path=args.db, openai_api_key=api_key)
        entries = app.generate_time_entries_for_date_range(args.start_date, args.end_date)
        
        if entries:
            app.export_time_entries(args.output, args.start_date, args.end_date)
        else:
            print("No time entries were generated")
    
    elif args.command == "export":
        app = TimeEntryApp(db_path=args.db)
        app.export_time_entries(args.output, args.start_date, args.end_date)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


class TimeEntryApp:
    """Main application for the Time Entry Generator/Auditor system"""
    
    def __init__(self, db_path: str = "evidence.db", openai_api_key: Optional[str] = None):
        self.db_path = db_path
        self.evidence_db = EvidenceDatabase(db_path)
        self.timeline_constructor = TimelineConstructor(self.evidence_db)
        self.time_entry_generator = TimeEntryGeneratorSystem(self.evidence_db, openai_api_key)
        
        # Initialize processors
        self.processors = {
            'email': EmailProcessor(),
            'sms': SMSProcessor(),
            'docket': DocketProcessor(),
            'phone_call': PhoneCallProcessor(),
            'time_entry': TimeEntryProcessor()
        }
    
    def ingest_data_files(self, file_paths: Dict[str, str]) -> Dict[str, int]:
        """
        Ingest data files of different types
        
        Args:
            file_paths: Dictionary mapping file types to file paths
            
        Returns:
            Dictionary with counts of items ingested by type
        """
        results = {}
        
        for file_type, file_path in file_paths.items():
            if file_type in self.processors:
                processor = self.processors[file_type]
                try:
                    print(f"Processing {file_type} file: {file_path}")
                    evidence_items = processor.process(file_path)
                    count = self.evidence_db.insert_evidence_items(evidence_items)
                    results[file_type] = count
                    print(f"Successfully ingested {count} {file_type} items")
                except Exception as e:
                    print(f"Error processing {file_type} file: {e}")
                    results[file_type] = 0
            else:
                print(f"Unsupported file type: {file_type}")
                results[file_type] = 0
        
        return results
    
    def set_case_context(self, name: str, description: str, parties: List[Dict] = None) -> str:
        """
        Set the case context information
        
        Args:
            name: Case name
            description: Case description
            parties: List of parties involved
            
        Returns:
            Context ID
        """
        return self.evidence_db.set_case_context(name, description, parties)
    
    def build_timeline(self) -> int:
        """
        Build the timeline and identify relationships between evidence items
        
        Returns:
            Number of relationships identified
        """
        print("Identifying relationships between evidence items...")
        relationship_count = self.timeline_constructor.identify_relationships()
        
        print("Associating evidence with docket events...")
        association_count = self.timeline_constructor.associate_evidence_with_docket_events()
        
        print(f"Identified {relationship_count} relationships and {association_count} docket associations")
        return relationship_count + association_count
    
    def suggest_projects(self) -> List[Dict[str, Any]]:
        """
        Suggest potential projects based on evidence
        
        Returns:
            List of suggested projects
        """
        projects = self.timeline_constructor.suggest_projects()
        print(f"Suggested {len(projects)} projects")
        return projects
    
    def create_project(self, name: str, description: str, evidence_ids: List[str] = None) -> str:
        """
        Create a new project and link evidence to it
        
        Args:
            name: Project name
            description: Project description
            evidence_ids: List of evidence IDs to link to the project
            
        Returns:
            Project ID
        """
        project_id = self.evidence_db.create_project(name, description)
        
        if evidence_ids:
            for evidence_id in evidence_ids:
                self.evidence_db.link_evidence_to_project(evidence_id, project_id)
        
        return project_id
    
    def generate_time_entries_for_week(self, week_start: Union[str, datetime], 
                                evidence_types: List[str] = None,
                                system_prompt: str = None,
                                activity_codes: str = None,
                                prompt_template: str = None) -> List[Dict[str, Any]]:
        """
        Generate time entries for a specific week
        
        Args:
            week_start: Start date of the week (string in ISO format or datetime)
            evidence_types: List of evidence types to include
            system_prompt: Custom system prompt to use
            activity_codes: Custom activity codes to use
            prompt_template: Custom prompt template to use
            
        Returns:
            List of generated time entries
        """
        if isinstance(week_start, datetime):
            week_start_str = week_start.isoformat()
        else:
            week_start_str = week_start
        
        print(f"Generating time entries for week of {week_start_str}...")
        entries = self.time_entry_generator.generate_weekly_entries(
            week_start_str,
            evidence_types=evidence_types,
            system_prompt=system_prompt,
            activity_codes=activity_codes,
            prompt_template=prompt_template
        )
        
        if entries:
            # Insert the generated entries into the database
            count = self.evidence_db.insert_time_entries(entries)
            print(f"Generated and inserted {count} time entries")
            
            # Link evidence to time entries
            for entry in entries:
                # Check if the entry has evidence IDs
                if 'evidenceids' in entry and entry['evidenceids']:
                    entry_id = entry['id']
                    evidence_ids_str = entry['evidenceids']
                    
                    # Split by commas or other separators
                    evidence_ids = [id.strip() for id in re.split(r'[,;\s]+', evidence_ids_str) if id.strip()]
                    
                    # Filter out any IDs that are likely activity codes (not evidence IDs)
                    filtered_ids = []
                    for eid in evidence_ids:
                        # Skip numeric values under 100 (likely activity codes)
                        if eid.isdigit() and int(eid) < 100:
                            print(f"Skipping likely activity code: {eid}")
                            continue
                        # Skip anything that's clearly not a valid ID format
                        if len(eid) < 5 or ':' in eid or '=' in eid:
                            print(f"Skipping invalid ID format: {eid}")
                            continue
                        filtered_ids.append(eid)
                    
                    # Link each evidence ID to the time entry
                    for evidence_id in filtered_ids:
                        try:
                            # Only link if the evidence ID exists in the database
                            evidence = self.evidence_db.get_evidence_by_id(evidence_id)
                            if evidence:
                                self.evidence_db.link_evidence_to_time_entry(evidence_id, entry_id)
                                print(f"Linked evidence {evidence_id} to time entry {entry_id}")
                        except Exception as e:
                            print(f"Error linking evidence {evidence_id} to time entry: {e}")
        else:
            print("No time entries were generated")
        
        return entries
    
    def generate_time_entries_for_date_range(self, start_date: str, end_date: str, 
                                    evidence_types: List[str] = None,
                                    system_prompt: str = None,
                                    activity_codes: str = None,
                                    prompt_template: str = None,
                                    custom_prompt: str = None) -> List[Dict[str, Any]]:
        """
        Generate time entries for a date range
        
        Args:
            start_date: Start date in ISO format
            end_date: End date in ISO format
            evidence_types: List of evidence types to include
            system_prompt: Custom system prompt to use
            activity_codes: Custom activity codes to use
            prompt_template: Custom prompt template to use
            custom_prompt: Complete custom prompt to bypass all templates
            
        Returns:
            List of generated time entries
        """
        print(f"Generating time entries for date range - time_entry_app.py {start_date} to {end_date}")
        if evidence_types:
            print(f"Evidence types filter: {evidence_types}")
        
        # Ensure dates are in proper ISO format (YYYY-MM-DD)
        try:
            # Try parsing the date - this will standardize the format
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00') if 'Z' in start_date else start_date)
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00') if 'Z' in end_date else end_date)
            
            # Format to YYYY-MM-DD for consistency
            start_date = start_dt.date().isoformat()
            end_date = end_dt.date().isoformat()
            
            # Update datetime objects with normalized dates
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            
            print(f"Normalized date range: {start_date} to {end_date}")
        except Exception as e:
            print(f"Warning: Error normalizing dates: {e}")
            # Continue with original dates if there's an error
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        
        # If we have a custom prompt, still process week by week, but pass the custom prompt
        if custom_prompt:
            all_entries = []
            
            # Process week by week
            current_date = start_dt
            while current_date <= end_dt:
                # Find the start of the week (Monday)
                week_start = current_date - timedelta(days=current_date.weekday())
                if week_start < start_dt:
                    week_start = start_dt
                
                # End of week is 6 days later or the end date, whichever is earlier
                week_end = week_start + timedelta(days=6)
                if week_end > end_dt:
                    week_end = end_dt
                    
                print(f"Processing week from {week_start.isoformat()} to {week_end.isoformat()} with custom prompt")
                
                # Generate entries for this week with custom prompt
                week_entries = self.time_entry_generator.generate_weekly_entries(
                    week_start.isoformat(),
                    evidence_types=evidence_types,
                    custom_prompt=custom_prompt
                )
                
                # Insert the entries for this week
                if week_entries:
                    count = self.evidence_db.insert_time_entries(week_entries)
                    print(f"Generated and inserted {count} time entries for week of {week_start.isoformat()}")
                    all_entries.extend(week_entries)
                
                # Move to the next week
                current_date += timedelta(days=7)
            
            return all_entries
            
        # Otherwise, use the week-by-week approach with the customized prompts
        all_entries = []
        
        # Process week by week
        current_date = start_dt
        while current_date <= end_dt:
            # Find the start of the week (Monday)
            week_start = current_date - timedelta(days=current_date.weekday())
            if week_start < start_dt:
                week_start = start_dt
            
            # Generate entries for this week with custom prompts
            entries = self.generate_time_entries_for_week(
                week_start.isoformat(),
                evidence_types=evidence_types,
                system_prompt=system_prompt,
                activity_codes=activity_codes,
                prompt_template=prompt_template
            )
            all_entries.extend(entries)
            
            # Move to the next week
            current_date += timedelta(days=7)
        
        return all_entries
         
    
    def export_time_entries(self, output_path: str, start_date: Optional[str] = None, 
                          end_date: Optional[str] = None) -> int:
        """
        Export time entries to a CSV file
        
        Args:
            output_path: Path to save the CSV file
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Number of entries exported
        """
        filters = {}
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        entries = self.evidence_db.query_time_entries(filters)
        
        if not entries:
            print("No time entries to export")
            return 0
        
        # Convert to DataFrame for easy CSV export
        df = pd.DataFrame(entries)
        df.to_csv(output_path, index=False)
        
        print(f"Exported {len(entries)} time entries to {output_path}")
        return len(entries)
    
    def close(self):
        """Close database connections"""
        self.evidence_db.close()