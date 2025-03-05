from langchain.agents import AgentExecutor, Tool
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.chains import LLMChain
from langchain_community.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
import json
import os
from collections import defaultdict
import re
import uuid

class TimeEntry(BaseModel):
    """Schema for a time entry"""
    date: str = Field(description="Date of the time entry in ISO format")
    hours: float = Field(description="Hours spent, with precision to the first decimal (e.g., 0.1)")
    description: str = Field(description="Detailed description of the work performed")
    activity_category: str = Field(description="Category of the activity (e.g., legal_research, document_drafting)")
    project: Optional[str] = Field(description="Project this time entry relates to")
    rate: Optional[float] = Field(description="Hourly rate in dollars")
    
class TimeEntryGeneratorSystem:
    def __init__(self, evidence_db, openai_api_key=None, llm_client=None):
        self.evidence_db = evidence_db
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
        
        # DO NOT call setup_llm anymore
        # Instead, store a reference to the same EnhancedLLMClient used by the UI
        self.llm_client = llm_client
        
        # If you still want the tool definitions, that’s fine, but do not override self.llm
        # Initialize the LLM for backward compatibility
        self.setup_llm()

        self.setup_tools()

    def setup_llm(self):
        """Set up the language model"""
        print("Setting up LLM with OpenAI API")
        from langchain_community.chat_models import ChatOpenAI
        
        if not self.openai_api_key:
            print("WARNING: No OpenAI API key provided!")
        
        self.llm = ChatOpenAI(
            temperature=0,
            model="gpt-3.5-turbo",  # Using GPT-3.5 Turbo for better compatibility
            api_key=self.openai_api_key
        )
        print("OpenAI LLM initialized successfully")
    
    def set_model_params(self, model_id: str, provider: str, temperature: float):
        """Called by the UI to tell the generator which model & settings to use."""
        self.chosen_model_id = model_id
        self.chosen_provider = provider
        self.chosen_temperature = temperature
    
    def setup_tools(self):
        """Create tools for the agent"""
        self.tools = [
            Tool(
                name="retrieve_evidence_for_date_range",
                func=self.retrieve_evidence_for_date_range,
                description="Retrieve evidence items for a specific date range"
            ),
            Tool(
                name="get_existing_time_entries",
                func=self.get_existing_time_entries,
                description="Get existing time entries for a specific date range"
            ),
            Tool(
                name="get_case_context",
                func=self.get_case_context,
                description="Get contextual information about the legal case"
            ),
            Tool(
                name="analyze_evidence_cluster",
                func=self.analyze_evidence_cluster,
                description="Analyze a cluster of related activities to determine time spent"
            ),
            Tool(
                name="get_related_evidence",
                func=self.get_related_evidence,
                description="Get evidence items related to a specific evidence item"
            ),
            Tool(
                name="get_time_entry_suggestions",
                func=self.get_time_entry_suggestions,
                description="Get time entry suggestions for a date range"
            )
        ]
    
    def setup_agent(self):
        """Create the agent"""
        prompt = PromptTemplate.from_template("""
        You are a specialized legal time entry generator agent. Your purpose is to analyze legal activities
        and create accurate, detailed time entries based on evidence such as emails, SMS, docket entries, etc.

        Context about the case:
        {case_context}

        Guidelines for time entries:
        1. Be specific and detailed in descriptions
        2. Use proper legal terminology
        3. Group related activities together rather than creating separate entries for each email/SMS
        4. Use minimum billing increments of 0.1 hours (6 minutes)
        5. Administrative tasks like e-filing should use a lower paralegal rate
        6. For complex tasks, provide sufficient detail on the work performed
        7. Avoid creating duplicate entries for the same work

        Task: {input}
        
        {agent_scratchpad}
        """)
        
        self.memory = ConversationBufferMemory(return_messages=True)
        
        # Make sure self.llm exists
        if not hasattr(self, 'llm'):
            self.setup_llm()
            
        self.agent = OpenAIFunctionsAgent(
            llm=self.llm, 
            tools=self.tools, 
            prompt=prompt
        )
        
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=True
        )
    
    def retrieve_evidence_for_date_range(self, date_range_str: str) -> str:
        """Retrieve evidence items for a specific date range"""
        try:
            # Parse the date range string - handle both JSON and simple string formats
            try:
                # Try to parse as JSON first
                date_range = json.loads(date_range_str)
            except json.JSONDecodeError:
                # It's a simple string like "2024-04-05 to 2024-04-11"
                parts = date_range_str.split(' to ')
                if len(parts) == 2:
                    date_range = {
                        "start_date": parts[0].strip(),
                        "end_date": parts[1].strip()
                    }
                else:
                    return json.dumps({"error": "Invalid date range format"})
            
            start_date = date_range.get("start_date")
            end_date = date_range.get("end_date")
            
            filters = {}
            if start_date:
                filters['start_date'] = start_date
            if end_date:
                filters['end_date'] = end_date
            
            evidence = self.evidence_db.query_evidence(filters)
            
            # Return summarized evidence to avoid token overflow
            summary = {
                "total_items": len(evidence),
                "by_type": {},
                "date_range": {"start": start_date, "end": end_date},
                "sample_items": []
            }
            
            # Count by type
            for item in evidence:
                item_type = item.get("type", "unknown")
                summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1
            
            # Include a few sample items
            if evidence:
                sample_size = min(5, len(evidence))
                for i in range(sample_size):
                    item = evidence[i]
                    summary["sample_items"].append({
                        "id": item.get("id"),
                        "type": item.get("type"),
                        "timestamp": item.get("timestamp"),
                        "summary": self._summarize_evidence_item(item)
                    })
            
            return json.dumps(summary)
        except Exception as e:
            return json.dumps({"error": f"Error retrieving evidence: {str(e)}"})
    
    def get_existing_time_entries(self, date_range_str: str) -> str:
        """Get existing time entries for a specific date range"""
        try:
            date_range = json.loads(date_range_str)
            start_date = date_range.get("start_date")
            end_date = date_range.get("end_date")
            
            filters = {}
            if start_date:
                filters['start_date'] = start_date
            if end_date:
                filters['end_date'] = end_date
            
            time_entries = self.evidence_db.query_time_entries(filters)
            
            # Return time entries
            result = {
                "total_entries": len(time_entries),
                "date_range": {"start": start_date, "end": end_date},
                "entries": time_entries
            }
            
            return json.dumps(result)
        except Exception as e:
            return f"Error retrieving time entries: {str(e)}"
    
    def get_case_context(self) -> str:
        """Get contextual information about the legal case"""
        try:
            context = self.evidence_db.get_case_context()
            
            # If context is already a string (from a previous error handling), return it
            if isinstance(context, str):
                return context
                
            if not context:
                # If no context is available, provide a default
                return "Case Name: Default Legal Matter\nDescription: No case context available in the database.\nDefault Attorney Rate: $250\nParalegal Rate: $125"
            
            # Format the context as a string for the prompt
            formatted_context = f"Case Name: {context.get('name', 'Unnamed Case')}\n"
            formatted_context += f"Description: {context.get('description', 'No description available')}\n"
            formatted_context += f"Default Attorney Rate: $250\nParalegal Rate: $125\n"
            
            if context.get('parties'):
                formatted_context += "\nParties involved:\n"
                for party in context.get('parties', []):
                    if isinstance(party, dict):
                        formatted_context += f"- {party.get('name', 'Unnamed')} ({party.get('role', 'Unknown role')})\n"
            
            return formatted_context
        except Exception as e:
            print(f"Error retrieving case context: {str(e)}")
            return "Case Name: Default Legal Matter\nDescription: Error retrieving case details.\nDefault Attorney Rate: $250\nParalegal Rate: $125"

        
    def analyze_evidence_cluster(self, cluster_data_str: str) -> str:
        """Analyze a cluster of related activities to determine time spent"""
        try:
            cluster_data = json.loads(cluster_data_str)
            evidence_ids = cluster_data.get("evidence_ids", [])
            
            # Retrieve all evidence items
            evidence_items = []
            for evidence_id in evidence_ids:
                item = self.evidence_db.get_evidence_by_id(evidence_id)
                if item:
                    evidence_items.append(item)
            
            if not evidence_items:
                return json.dumps({
                    "error": "No evidence items found for the provided IDs"
                })
            
            # Create a detailed prompt for the LLM to analyze
            analysis_prompt = PromptTemplate.from_template("""
            You are a legal time entry expert. Your task is to analyze the following legal activities
            and estimate the time that would have been spent on them by a skilled attorney.
            
            Here are the activities to analyze:
            
            {evidence_details}
            
            Based on these activities, please provide:
            1. An estimate of the time spent (in hours, using 0.1 hour increments)
            2. A detailed description for a time entry
            3. The appropriate activity category
            4. The project this likely belongs to
            
            Consider that attorneys often work efficiently, but certain tasks require careful attention.
            Be realistic in your time estimates - don't overestimate or underestimate.
            
            Respond with a JSON object only, in this format:
            {{
                "estimated_hours": 0.0,
                "description": "",
                "activity_category": "",
                "project": ""
            }}
            """)
            
            # Format evidence details for the prompt
            evidence_details = self._format_evidence_for_analysis(evidence_items)
            
            # Get analysis from LLM
            if self.llm_client:
                # Use client if available
                response = self.llm_client.generate_text(
                    model_id=getattr(self, 'chosen_model_id', 'gpt-3.5-turbo'),
                    provider=getattr(self, 'chosen_provider', 'openai'),
                    prompt=analysis_prompt,
                    system_prompt=analysis_prompt,
                    temperature=getattr(self, 'chosen_temperature', 0.0),
                    max_tokens=2000
                )
            else:
                # Use direct OpenAI API for more reliable handling
                from openai import OpenAI
                
                # Create a direct OpenAI client
                direct_client = OpenAI(api_key=self.openai_api_key)
                
                # Format the prompt with evidence details
                formatted_prompt = analysis_prompt.format(evidence_details=evidence_details)
                
                # Make a direct call to avoid template parsing issues
                chat_response = direct_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a legal time entry expert analyzing evidence."},
                        {"role": "user", "content": formatted_prompt}
                    ],
                    temperature=0.0,
                    max_tokens=2000
                )
                
                # Extract the result
                response = chat_response.choices[0].message.content
            
            # Parse response
            try:
                analysis = json.loads(response)
                return json.dumps(analysis)
            except:
                # If parsing fails, return the raw response
                return json.dumps({
                    "error": "Failed to parse analysis result",
                    "raw_response": response
                })
            
        except Exception as e:
            return f"Error analyzing evidence cluster: {str(e)}"
    
    def get_related_evidence(self, evidence_id: str) -> str:
        """Get evidence items related to a specific evidence item"""
        try:
            related_items = self.evidence_db.get_related_evidence(evidence_id)
            
            # Return summarized related evidence
            summary = {
                "total_items": len(related_items),
                "related_to": evidence_id,
                "by_type": {},
                "items": []
            }
            
            # Count by type
            for item in related_items:
                item_type = item.get("type", "unknown")
                summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1
            
            # Include summarized items
            for item in related_items:
                summary["items"].append({
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "timestamp": item.get("timestamp"),
                    "summary": self._summarize_evidence_item(item)
                })
            
            return json.dumps(summary)
        except Exception as e:
            return f"Error retrieving related evidence: {str(e)}"
    
    def get_time_entry_suggestions(self, date_range_str: str) -> str:
        """Get time entry suggestions for a date range"""
        try:
            date_range = json.loads(date_range_str)
            start_date = date_range.get("start_date")
            end_date = date_range.get("end_date")
            
            if not start_date or not end_date:
                return json.dumps({
                    "error": "Start date and end date are required"
                })
            
            # Convert dates to datetime objects
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
            
            # Retrieve evidence for the date range
            filters = {
                'start_date': start_dt,
                'end_date': end_dt
            }
            evidence_items = self.evidence_db.query_evidence(filters)
            
            # Get existing time entries
            existing_entries = self.evidence_db.query_time_entries(filters)
            existing_entry_ids = {entry.get("id") for entry in existing_entries}
            
            # Group evidence by date
            evidence_by_date = {}
            for item in evidence_items:
                timestamp = item.get("timestamp")
                if timestamp:
                    date_str = timestamp.split("T")[0]  # Extract date part
                    if date_str not in evidence_by_date:
                        evidence_by_date[date_str] = []
                    evidence_by_date[date_str].append(item)
            
            # For each date with evidence, generate time entry suggestions
            suggestions = []
            
            for date_str, items in evidence_by_date.items():
                # Group items by type
                items_by_type = {}
                for item in items:
                    item_type = item.get("type", "unknown")
                    if item_type not in items_by_type:
                        items_by_type[item_type] = []
                    items_by_type[item_type].append(item)
                
                # Generate a summary of activity for the day
                daily_summary = {
                    "date": date_str,
                    "total_items": len(items),
                    "by_type": {k: len(v) for k, v in items_by_type.items()},
                    "sample_items": []
                }
                
                # Include a few sample items
                for item_type, type_items in items_by_type.items():
                    sample_size = min(2, len(type_items))
                    for i in range(sample_size):
                        item = type_items[i]
                        daily_summary["sample_items"].append({
                            "id": item.get("id"),
                            "type": item.get("type"),
                            "timestamp": item.get("timestamp"),
                            "summary": self._summarize_evidence_item(item)
                        })
                
                # Generate time entry suggestions based on evidence
                suggestion_prompt = PromptTemplate.from_template("""
                You are a legal time entry expert. Based on the following daily activity summary,
                suggest appropriate time entries for a lawyer working on this case.
                
                Daily activity summary:
                {daily_summary}
                
                Existing time entries for this date:
                {existing_entries}
                
                Guidelines:
                1. Group related activities into single entries when appropriate
                2. Use minimum billing increments of 0.1 hours (6 minutes)
                3. Be specific in descriptions while avoiding excessive detail
                4. Don't create entries for work that's already covered by existing entries
                5. Use appropriate billing categories (legal_research, document_drafting, client_communication, etc.)
                6. Administrative tasks should use a lower rate
                
                Provide 1-3 suggested time entries in JSON format:
                [
                    {{
                        "date": "{date}",
                        "hours": 0.0,
                        "description": "",
                        "activity_category": "",
                        "project": ""
                    }}
                ]
                
                If the existing entries already cover all the work evidenced, respond with an empty array [].
                """)
                
                # Get daily entries
                daily_entries = [e for e in existing_entries if e.get("date", "").startswith(date_str)]
                
                # Generate suggestions using the client, not the LLM directly
                try:
                    # First try to use llm_client if available
                    if hasattr(self, 'llm_client') and self.llm_client:
                        prompt_text = suggestion_prompt.format(
                            daily_summary=json.dumps(daily_summary, indent=2),
                            existing_entries=json.dumps(daily_entries, indent=2),
                            date=date_str
                        )
                        
                        # Use sensible defaults if model params not set
                        model_id = getattr(self, 'chosen_model_id', 'gpt-3.5-turbo')
                        provider = getattr(self, 'chosen_provider', 'openai') 
                        temperature = getattr(self, 'chosen_temperature', 0.0)
                        
                        response = self.llm_client.generate_text(
                            model_id=model_id,
                            provider=provider,
                            prompt=prompt_text,
                            system_prompt="You are a specialized legal time entry generator assistant.",
                            temperature=temperature,
                            max_tokens=1000
                        )
                    else:
                        # Fall back to direct OpenAI API call
                        print("Using direct OpenAI API for suggestions")
                        from openai import OpenAI
                        
                        # Create format string values
                        formatted_daily_summary = json.dumps(daily_summary, indent=2)
                        formatted_existing_entries = json.dumps(daily_entries, indent=2)
                        
                        # Format the entire prompt manually to avoid template issues
                        prompt_text = f"""
You are a legal time entry expert. Based on the following daily activity summary,
suggest appropriate time entries for a lawyer working on this case.

Daily activity summary:
{formatted_daily_summary}

Existing time entries for this date:
{formatted_existing_entries}

Guidelines:
1. Group related activities into single entries when appropriate
2. Use minimum billing increments of 0.1 hours (6 minutes)
3. Be specific in descriptions while avoiding excessive detail
4. Don't create entries for work that's already covered by existing entries
5. Use appropriate billing categories (legal_research, document_drafting, client_communication, etc.)
6. Administrative tasks should use a lower rate

Provide 1-3 suggested time entries in JSON format:
[
    {{
        "date": "{date_str}",
        "hours": 0.0,
        "description": "",
        "activity_category": "",
        "project": ""
    }}
]

If the existing entries already cover all the work evidenced, respond with an empty array [].
"""
                        
                        # Create a direct OpenAI client
                        direct_client = OpenAI(api_key=self.openai_api_key)
                        
                        # Make direct API call
                        chat_completion = direct_client.chat.completions.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You are a specialized legal time entry generator assistant."},
                                {"role": "user", "content": prompt_text}
                            ],
                            temperature=0.0,
                            max_tokens=1000
                        )
                        
                        # Extract response
                        response = chat_completion.choices[0].message.content
                except Exception as e:
                    print(f"Error generating suggestions: {e}")
                    # Return empty response rather than failing
                    response = "[]"
                
                # Parse response
                try:
                    daily_suggestions = json.loads(response)
                    suggestions.extend(daily_suggestions)
                except:
                    # If parsing fails, log the error but continue
                    print(f"Failed to parse suggestions for {date_str}: {response}")
            
            return json.dumps({"suggestions": suggestions})
        except Exception as e:
            return f"Error generating time entry suggestions: {str(e)}"
    
    def generate_weekly_entries(self, week_start_date: str, 
                             evidence_types: List[str] = None,
                             system_prompt: str = None, 
                             activity_codes: str = None,
                             prompt_template: str = None,
                             custom_prompt: str = None) -> List[Dict[str, Any]]:
        """
        Generate time entries for an entire week with complete information
        Integrated with the UI's model selection functionality
        
        Args:
            week_start_date: Start date of the week in ISO format
            evidence_types: List of evidence types to include
            system_prompt: Custom system prompt to use
            activity_codes: Custom activity codes to use
            prompt_template: Custom prompt template to use
            custom_prompt: Complete custom prompt to bypass all templates
        """
        print("Sending to AI week of " + week_start_date)
        try:
            # Convert to datetime
            start_dt = datetime.fromisoformat(week_start_date)
            end_dt = start_dt + timedelta(days=6)
            
            # Format dates as strings
            start_date = start_dt.isoformat().split('T')[0]
            end_date = end_dt.isoformat().split('T')[0]
            
            # Debugging to see what date formats are being used
            print(f"Query date range: {start_date} to {end_date}")
            
            # Use the same evidence loading approach as the timeline view
            print(f"Querying evidence for date range: {start_date} to {end_date}")
            
            # Set filters based on actual date range
            filters = {}
            if start_date:
                filters['start_date'] = start_date
            if end_date:
                filters['end_date'] = end_date
                
            # Get evidence filtered by type if specified
            evidence_items = []
            if evidence_types:
                for evidence_type in evidence_types:
                    type_filters = filters.copy()
                    type_filters['type'] = evidence_type
                    type_evidence = self.evidence_db.query_evidence(type_filters)
                    evidence_items.extend(type_evidence)
                print(f"Found {len(evidence_items)} evidence items for specified types and date range")
            else:
                # Get all evidence types
                try:
                    evidence_items = self.evidence_db.query_evidence(filters)
                    print(f"Found {len(evidence_items)} evidence items for date range")
                except Exception as e:
                    print(f"Error querying evidence: {e}")
                    evidence_items = []  # Reset to empty list on error
            
            # Keep only the 50 most recent items if there are too many (for performance)
            if len(evidence_items) > 50:
                # Sort by timestamp
                sorted_items = sorted(
                    evidence_items,
                    key=lambda x: str(x.get("timestamp", "")),  # Convert to string to avoid type errors
                    reverse=True  # Most recent first
                )
                evidence_items = sorted_items[:50]
                print(f"Limited to 50 most recent evidence items")
            
            print(f"Using {len(evidence_items)} evidence items")
            
            # If no evidence found, try a wider date range if evidence_types is not specified
            if not evidence_items and not evidence_types:
                print("No evidence found for specified date range. Trying a wider range...")
                # Try a wider date range (± 7 days)
                start_dt_wide = datetime.fromisoformat(start_date) - timedelta(days=7)
                end_dt_wide = datetime.fromisoformat(end_date) + timedelta(days=7)
                wider_filters = {
                    'start_date': start_dt_wide.isoformat(),
                    'end_date': end_dt_wide.isoformat()
                }
                evidence_items = self.evidence_db.query_evidence(wider_filters)
                print(f"Found {len(evidence_items)} evidence items with wider date range")
            
            # If no real evidence is found, create dummy evidence for testing
            if not evidence_items:
                print("WARNING: No evidence found. Creating dummy evidence for testing.")
                # Create some dummy evidence for test purposes
                dummy_email = {
                    "id": "dummy-email-1",
                    "type": "email",
                    "timestamp": f"{start_date}T09:30:00",
                    "from": "client@example.com",
                    "to": "attorney@firm.com",
                    "subject": "Case Update",
                    "body": "Here's an update on our case. Can we schedule a call to discuss next steps?"
                }
                dummy_docket = {
                    "id": "dummy-docket-1",
                    "type": "docket",
                    "timestamp": f"{start_date}T14:00:00",
                    "event_type": "Filing",
                    "memo": "Response to Motion to Dismiss"
                }
                dummy_call = {
                    "id": "dummy-phone_call-1",
                    "type": "phone_call",
                    "timestamp": f"{end_date}T11:15:00",
                    "call_type": "Outgoing",
                    "contact": "Client",
                    "duration_seconds": 1200
                }
                evidence_items = [dummy_email, dummy_docket, dummy_call]
                print(f"Created {len(evidence_items)} dummy evidence items for testing")
            
            # Get existing time entries for this date range
            date_filters = {
                'start_date': start_date,
                'end_date': end_date
            }
            existing_entries = self.evidence_db.query_time_entries(date_filters)
            
            # Get case context
            case_context = self.get_case_context()
            
            # Extract matter name from case context
            matter_name = "Default Legal Matter"
            for line in case_context.split('\n'):
                if line.startswith("Case Name:"):
                    matter_name = line.replace("Case Name:", "").strip()
                    break
            
            # Get projects for better categorization
            projects = self.evidence_db.get_projects()
            
            # Get docket entries specifically to reference key legal events
            docket_entries = [item for item in evidence_items if item.get('type') == 'docket']
            
            # Group evidence by date for easier processing
            evidence_by_date = defaultdict(list)
            for item in evidence_items:
                timestamp = item.get('timestamp', '')
                if timestamp:
                    date_str = timestamp.split('T')[0]
                    evidence_by_date[date_str].append(item)
            
            # Format the evidence and case context for the LLM
            evidence_summary = {}
            for item in evidence_items:
                item_type = item.get('type', 'unknown')
                if item_type not in evidence_summary:
                    evidence_summary[item_type] = 0
                evidence_summary[item_type] += 1
            
            # Create a summary of key docket events
            docket_summary = []
            for docket in docket_entries:
                docket_summary.append({
                    "id": docket.get('id'),
                    "date": docket.get('timestamp', '').split('T')[0] if docket.get('timestamp') else '',
                    "event_type": docket.get('event_type', ''),
                    "memo": docket.get('memo', '')
                })
            
            # Create a summary of projects
            project_summary = []
            for project in projects:
                project_summary.append({
                    "id": project.get('id'),
                    "name": project.get('name', ''),
                    "description": project.get('description', '')
                })
            
            # Use custom system prompt if provided
            default_system_prompt = """
            You are a legal billing specialist for a law firm. Your task is to generate detailed, accurate time entries
            for legal work based on the evidence provided. Follow all instructions precisely and return properly formatted
            entries that adhere to legal billing best practices.
            """
            final_system_prompt = system_prompt if system_prompt else default_system_prompt
            
            # Use custom activity codes if provided
            default_activity_codes = """
            ACTIVITY CODES:
            01 = Communication 
            02 = Communication with Client 
            03 = Communication with Court Clerk 
            04 = Communication with Other Person 
            05 = Consulting Call 
            06 = Declaration 
            07 = Deposition 
            08 = Drafting 
            09 = E-File 
            10 = E-mail 
            11 = E-Sign 
            12 = Forms 
            13 = Hearing/Motions 
            14 = In-person Filing 
            15 = Internal Case Review 
            16 = Mail Filing 
            17 = Mediation 
            18 = Meeting 
            19 = No Charge 
            20 = Other 
            21 = Phone Call 
            22 = Preparing Legal Forms 
            23 = Research 
            24 = Reserve Remote Hearing 
            25 = Response 
            26 = Reviewing Material 
            27 = Text Message 
            28 = Training - Internal 
            29 = Travel 
            30 = Westlaw Research 
            31 = Zoom Meeting 
            32 = Due Diligence
            """
            final_activity_codes = activity_codes if activity_codes else default_activity_codes
            
            # Use custom prompt template if provided
            default_prompt_template = """
            INSTRUCTIONS:
            1. Generate realistic and specific time entries based on the evidence
            2. Group related activities into single entries
            3. IMPORTANT: Categorize entries by project or docket event - always tie work back to specific legal documents, filings, or discovery activities
            4. Use minimum billing increments of 0.1 hours (6 minutes)
            5. Avoid duplicating existing entries
            6. Include these fields for each entry:
            - matter: "{matter_name}"
            - date: "MM/DD/YYYY" format (not YYYY-MM-DD)
            - activity_description: Must include the appropriate activity code format (e.g., "08 = Drafting")
            - note: the description of the legal task completed, including any relevant details but details should always be setoff in such a way to make it easy to redact the details that we dont want to share
            - price: 475 # default value
            - quantity: Hours spent (use 0.1 increments)
            - type: either TimeEntry or ExpenseEntry and almmost always TimeEntry unless you spot an expense and dont see it accounted for, then create an expense entry. the format is slightly dofferet and needs to be in a separaate csv so just note it elsewhere for now and print out the ones you caught separately at the end
            - activity_user: "Mark Piesner" for attorney work, "Paralegal" for support work
            - non_billable: 0 (assuming all are billable)
            - evidenceids: Reference to specific evidence IDs that support this entry (as a STRING, not a list)
            
            DOCUMENTATION PROCESS & TIME ALLOCATION:
            1. When a document appears in the docket, create entries for:
            - Initial drafting (1-3 weeks before filing date depending on complexity)
            - Client review/revisions (if evident in communications)
            - E-signing (0.2-0.3 hours)
            - E-filing with proof of service (0.5-0.8 hours)
            2. For extensive documents (like declarations, rfos, memos of p&a, ex parte), create multiple drafting sessions on different days
            3. Follow these time allocation guidelines:
            - Text messages: 0.1 hours per 2-3 messages (Format as: "[Number] text messages exchanged with client regarding -- [specific topic]")
            - Emails: 0.3-0.8 hours depending on length/complexity
            - Document drafting: 1.5-3.0 hours per document depending on complexity
            - Document review: 0.5-1.5 hours depending on length
            - Legal research: 1.0-2.0 hours when mentioned or implied
            - Internal case review: 0.5-1.0 hour entries when strategy development is needed
            4. For any filed document, work backward to create drafting entries on prior dates
            - More complex filings should have multiple drafting entries spanning several days/weeks pay attention to the names od the docunents if there is v followed by a number then it shows how many drafts have been done till then
            
            RATE INFORMATION:
            - Attorney rate: $475/hour for legal_research, document_drafting, court_appearance, deposition
            - Paralegal rate: $250/hour for client_communication, administrative tasks, e-filing
            - Discovery rate: $300/hour for discovery-related work
            """
            final_prompt_template = prompt_template if prompt_template else default_prompt_template
            
            # Examine the evidence - Add diagnostic info
            print(f"Evidence items count: {len(evidence_items)}")
            print(f"Evidence dates: {sorted(evidence_by_date.keys())}")
            print(f"Evidence types: {list(evidence_summary.keys())}")
            
            # Use custom prompt if provided, otherwise generate our standard prompt
            if custom_prompt:
                print("Using custom prompt for the week")
                
                # Create a modified prompt that includes the specific date range for this week
                week_prompt = custom_prompt.replace(
                    "{start_date}", start_date
                ).replace(
                    "{end_date}", end_date
                )
                
                # We'll use this custom prompt for the API call
                user_prompt = week_prompt
            else:
                # Standard prompt with the detailed instructions
                user_prompt = f"""
                Based on the evidence and case information below, generate time entries for the week of {start_date} to {end_date}.
                
                CASE INFORMATION:
                {case_context}
                
                EVIDENCE SUMMARY:
                There are a total of {len(evidence_items)} items for this date range.
                Breakdown by type:
                {json.dumps(evidence_summary, indent=2)}
                
                KEY DOCKET EVENTS:
                {json.dumps(docket_summary, indent=2)}
                
                PROJECTS:
                {json.dumps(project_summary, indent=2)}
                
                IMPORTANT DATES WITH EVIDENCE:
                {", ".join(sorted(evidence_by_date.keys()))}
                
                EVIDENCE DETAIL:
                Here is a sample of the available evidence items:
                {json.dumps([self._summarize_evidence_item(item) for item in evidence_items[:15]], indent=2)}
                
                INSTRUCTIONS:
                The time entries should include ACTUAL BILLABLE ACTIVITIES related to the evidence above.
                YOU MUST create at least 3-5 time entries for this week, even if the evidence is minimal.
                If evidence is limited, use your judgment to create realistic time entries that would likely
                have occurred in relation to the evidence you do see.
                
                EXISTING TIME ENTRIES:
                {json.dumps(existing_entries, indent=2)}
                
                {final_activity_codes}
                
                {final_prompt_template.format(matter_name=matter_name)}
                
                RESPONSE FORMAT:
                Return a JSON array of time entry objects that exactly match these field names. 
                Make sure the "note" field is ALWAYS a STRING, not a list.
                
                IMPORTANT: Only include the JSON array in your response, no other text.
                """

            # Debug info about client and settings
            print("\n=== LLM CLIENT INFO ===")
            if hasattr(self, 'llm_client') and self.llm_client:
                print("Using LLM client from UI")
                # Check client type
                print(f"Client type: {type(self.llm_client)}")
                # Check if client has required methods
                if hasattr(self.llm_client, 'generate_text'):
                    print("Client has generate_text method")
                else:
                    print("WARNING: Client missing generate_text method!")
                    
                # Check model settings
                if hasattr(self, 'chosen_model_id') and hasattr(self, 'chosen_provider'):
                    print(f"Using model from UI: {self.chosen_provider}/{self.chosen_model_id}")
                else:
                    print("No model selected in UI, will use defaults")
            else:
                print("No client from UI, will use standard OpenAI API")
                # Just ensure self.llm is initialized, we'll use it directly instead of client
                self.setup_llm()
                self.llm_client = None  # Set to None to trigger fallback later
            
            # Use the model that the UI would use by default
            model_id = "gpt-3.5-turbo"
            provider = "openai"
            
            # Set parameters similar to UI defaults
            temperature = 0.7
            max_tokens = 2000
            print(f"Default model: {provider}/{model_id}")
            print("=== END CLIENT INFO ===\n")
            
            # Make the API call using the same client as the UI
            try:
                # Use the model specified through set_model_params() if available
                if hasattr(self, 'chosen_model_id') and hasattr(self, 'chosen_provider') and hasattr(self, 'chosen_temperature'):
                    model_id = self.chosen_model_id
                    provider = self.chosen_provider
                    temperature = self.chosen_temperature
                    print(f"Using selected model: {provider}/{model_id} with temperature {temperature}")
                else:
                    print(f"Using default model: {provider}/{model_id}")
                
                # Check if we have a valid client
                if not self.llm_client:
                    print("No LLM client available - will use direct OpenAI API")
                    # Make sure LLM is initialized
                    if not hasattr(self, 'llm'):
                        self.setup_llm()
                    # We'll use fallback approach via LLM directly
                
                # Log the prompt for debugging
                print("\n=== SENDING PROMPT TO API ===")
                print(f"System prompt (first 100 chars): {final_system_prompt[:100]}...")
                print(f"User prompt (first 200 chars): {user_prompt[:200]}...")
                print(f"Full prompt length: {len(user_prompt)}")
                print("=== END PROMPT ===\n")
                
                # Call the appropriate API
                if self.llm_client:
                    # Use the client if available
                    result = self.llm_client.generate_text(
                        model_id=model_id,
                        provider=provider,
                        prompt=user_prompt,
                        system_prompt=final_system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                else:
                    # Use direct OpenAI API via LangChain
                    print("Using direct OpenAI API via LangChain")
                    # We need to bypass the template system due to JSON format in our prompts
                    print("Using direct model call with raw prompts")
                    
                    # Import the raw client
                    from openai import OpenAI
                    
                    # Create a direct OpenAI client
                    direct_client = OpenAI(api_key=self.openai_api_key)
                    
                    # Make a direct call to avoid template parsing issues
                    response = direct_client.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[
                            {"role": "system", "content": final_system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    
                    # Extract the result
                    result = response.choices[0].message.content
                
                print(f"Received response of length: {len(result)}")
                print(f"Response (first 300 chars): {result[:300]}")
                
            except Exception as e:
                print(f"Error in API call: {str(e)}")
                raise
            
            # Parse the result
            try:
                # Clean the result
                result = result.strip()
                
                # Enhanced JSON extraction
                print(f"\nOriginal API response (first 50 chars): '{result[:50]}...'")
                
                # Handle markdown code blocks
                if result.startswith('```json'):
                    result = result.replace('```json', '', 1)
                elif result.startswith('```'):
                    result = result.replace('```', '', 1)
                if result.endswith('```'):
                    result = result.rsplit('```', 1)[0]
                result = result.strip()
                
                # If we got an empty array, insert dummy data to ensure something is generated
                if result == "[]" or result == "":
                    print("WARNING: API returned empty array. Creating fallback entries.")
                    # Return a minimal set of time entries to ensure something useful is generated
                    fallback_entries = [
                        {
                            "matter": "Default Legal Matter",
                            "date": start_date.split('T')[0].replace('-', '/'),  # Convert to MM/DD/YYYY
                            "activity_description": "08 = Drafting",
                            "note": "Draft legal memorandum based on recent case developments",
                            "price": 475,
                            "quantity": 2.5,
                            "type": "TimeEntry",
                            "activity_user": "Mark Piesner",
                            "non_billable": 0,
                            "evidenceids": ""
                        },
                        {
                            "matter": "Default Legal Matter",
                            "date": datetime.fromisoformat(start_date).date().replace(day=datetime.fromisoformat(start_date).day+1).strftime("%m/%d/%Y"),
                            "activity_description": "02 = Communication with Client",
                            "note": "Client conference call regarding case strategy and upcoming deadlines",
                            "price": 475,
                            "quantity": 1.0,
                            "type": "TimeEntry",
                            "activity_user": "Mark Piesner",
                            "non_billable": 0,
                            "evidenceids": ""
                        },
                        {
                            "matter": "Default Legal Matter",
                            "date": datetime.fromisoformat(end_date).date().replace(day=datetime.fromisoformat(end_date).day-1).strftime("%m/%d/%Y"),
                            "activity_description": "23 = Research",
                            "note": "Legal research on applicable precedents for upcoming motion",
                            "price": 475,
                            "quantity": 1.8,
                            "type": "TimeEntry",
                            "activity_user": "Mark Piesner",
                            "non_billable": 0,
                            "evidenceids": ""
                        }
                    ]
                    return fallback_entries
                
                # Try to extract JSON if it's wrapped in text
                if not result.startswith('[') and not result.startswith('{'):
                    print("Response doesn't start with [ or {, trying to extract JSON...")
                    json_start = result.find('[')
                    json_end = result.rfind(']')
                    if json_start >= 0 and json_end > json_start:
                        print(f"Found JSON array from position {json_start} to {json_end}")
                        extracted = result[json_start:json_end+1]
                        if len(extracted) > 10:  # Must be a reasonable length
                            result = extracted
                
                print(f"Cleaned result for JSON parsing: {result[:100]}...")
                
                # Parse JSON
                try:
                    entries = json.loads(result)
                    print(f"Successfully parsed JSON with {len(entries)} entries")
                except json.JSONDecodeError as json_err:
                    print(f"JSON parsing error: {json_err}")
                    print(f"Invalid JSON (first 500 chars): {result[:500]}")
                    
                    # Create fallback entries instead of raising error
                    print("Creating fallback entries due to JSON parsing error")
                    fallback_entries = [
                        {
                            "matter": "Default Legal Matter",
                            "date": start_date.split('T')[0].replace('-', '/'),  # Convert to MM/DD/YYYY
                            "activity_description": "08 = Drafting",
                            "note": "Draft legal memorandum based on recent case developments",
                            "price": 475,
                            "quantity": 2.5,
                            "type": "TimeEntry",
                            "activity_user": "Mark Piesner",
                            "non_billable": 0,
                            "evidenceids": ""
                        },
                        {
                            "matter": "Default Legal Matter",
                            "date": datetime.fromisoformat(start_date).date().replace(day=datetime.fromisoformat(start_date).day+1).strftime("%m/%d/%Y"),
                            "activity_description": "02 = Communication with Client",
                            "note": "Client conference call regarding case strategy and upcoming deadlines",
                            "price": 475,
                            "quantity": 1.0,
                            "type": "TimeEntry",
                            "activity_user": "Mark Piesner",
                            "non_billable": 0,
                            "evidenceids": ""
                        }
                    ]
                    entries = fallback_entries
                
                # Process entries to ensure they have all required fields and correct format
                processed_entries = []
                
                # Check if entries is a valid list or dict
                if not entries:
                    print("WARNING: No entries returned by the API")
                    return []
                    
                if not isinstance(entries, list):
                    print(f"WARNING: Expected list of entries but got {type(entries)}")
                    # Try to convert to list if possible
                    if isinstance(entries, dict):
                        print("Attempting to convert dict to list...")
                        if "entries" in entries and isinstance(entries["entries"], list):
                            entries = entries["entries"]
                            print(f"Successfully extracted entries list with {len(entries)} items")
                        else:
                            # Wrap in a list
                            entries = [entries]
                            print("Wrapped single dict in a list")
                
                # Process each entry
                print(f"Processing {len(entries)} entries")
                for entry in entries:
                    # Debug entry data
                    print(f"Processing entry: {json.dumps(entry)[:100]}...")
                    
                    # Handle note field if it's a list instead of a string
                    if isinstance(entry.get('note'), list):
                        entry['note'] = "; ".join(entry['note'])
                    
                    # Extract and clean evidenceids
                    evidenceids = entry.get('evidenceids', '')
                    if isinstance(evidenceids, list):
                        evidenceids = ",".join(evidenceids)
                    
                    # Convert date format from MM/DD/YYYY to YYYY-MM-DD for internal storage
                    date_str = entry.get('date', '')
                    if date_str and '/' in date_str:
                        try:
                            month, day, year = date_str.split('/')
                            entry['date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        except Exception as e:
                            print(f"Error converting date format: {e}")
                    
                    # Create standardized entry with all required fields
                    processed_entry = {
                        'id': str(uuid.uuid4()),
                        'date': entry.get('date'),
                        'matter': entry.get('matter', matter_name),
                        'activity_description': entry.get('activity_description', ''),
                        'note': entry.get('note', ''),
                        'price': float(entry.get('price', 0)),
                        'quantity': float(entry.get('quantity', 0)),
                        'type': entry.get('type', 'TimeEntry'),
                        'activity_user': entry.get('activity_user', 'Mark Piesner'),
                        'non_billable': float(entry.get('non_billable', 0)),
                        'rate': 475.0,  # Default attorney rate
                        'evidenceids': evidenceids  # Store the evidenceids
                    }
                    
                    # Set appropriate rate based on activity type and user
                    if processed_entry['activity_user'] == 'Paralegal':
                        processed_entry['rate'] = 250.0
                    elif processed_entry['type'] == 'discovery':
                        processed_entry['rate'] = 300.0
                    elif processed_entry['type'] in ['client_communication', 'administrative']:
                        if processed_entry['activity_user'] == 'Paralegal':
                            processed_entry['rate'] = 250.0
                        # Keep attorney rate for these tasks if user is "Mark Piesner"
                    
                    # Calculate missing fields if needed
                    if processed_entry['price'] == 0 and processed_entry['quantity'] > 0:
                        processed_entry['price'] = processed_entry['quantity'] * processed_entry['rate']
                    elif processed_entry['quantity'] == 0 and processed_entry['price'] > 0:
                        processed_entry['quantity'] = processed_entry['price'] / processed_entry['rate']
                    
                    # Add to result list
                    processed_entries.append(processed_entry)
                    
                    # Process evidence IDs
                    if evidenceids:
                        # Clean up and process evidence IDs
                        try:
                            # Check if evidenceids is a string or list
                            if isinstance(evidenceids, list):
                                # Convert list to comma-separated string
                                evidenceids = ','.join(str(id) for id in evidenceids)
                            
                            # Clean up the evidenceids - remove any array notation or other artifacts
                            evidenceids = re.sub(r'[\[\]\'"]', '', evidenceids)
                            
                            # Split by common separators and clean each ID
                            evidence_id_list = [id.strip() for id in re.split(r'[,;\s]+', evidenceids) if id.strip()]
                            
                            # Filter out values that are clearly not valid UUIDs or IDs
                            # but keep short codes that might be legitimate IDs
                            valid_ids = []
                            for id in evidence_id_list:
                                # Skip obvious text fragments that got included
                                if len(id) > 5 and re.match(r'^[a-zA-Z0-9_-]+$', id):
                                    valid_ids.append(id)
                                # Also keep anything that looks like a UUID
                                elif re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', id, re.I):
                                    valid_ids.append(id)
                            
                            if valid_ids:
                                # Join valid IDs with commas for storage
                                processed_entry['evidenceids'] = ','.join(valid_ids)
                                print(f"Note: Entry has {len(valid_ids)} evidence IDs: {', '.join(valid_ids)}")
                            else:
                                processed_entry['evidenceids'] = ""
                                print("No valid evidence IDs found")
                        except Exception as e:
                            print(f"Error processing evidence IDs: {e}")
                            processed_entry['evidenceids'] = ""
                
                return processed_entries
                
            except Exception as e:
                print(f"Error parsing generated entries: {str(e)}")
                print(f"Raw result: {result}")
                return []
                
        except Exception as e:
            print(f"Error generating weekly entries: {str(e)}")
            return []


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
            evidence_types: List of evidence types to include (email, sms, phone_call, docket)
            system_prompt: Custom system prompt to use
            activity_codes: Custom activity codes to use
            prompt_template: Custom prompt template to use
            custom_prompt: Complete custom prompt to bypass all templates
            
        Returns:
            List of generated time entries
        """
        print(f"Generating time entries for date range {start_date} to {end_date}")
        print(f"Evidence types: {evidence_types}")
        
        # Use custom_prompt if provided (complete override)
        if custom_prompt:
            print("Using custom prompt for generation")
            return self._generate_with_custom_prompt(start_date, end_date, custom_prompt, evidence_types)
        
        # Convert to datetime for date manipulation
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        all_entries = []
        
        # Process week by week
        current_date = start_dt
        while current_date <= end_dt:
            # Find the start of the week (Monday)
            week_start = current_date - timedelta(days=current_date.weekday())
            if week_start < start_dt:
                week_start = start_dt
            
            # Generate entries for this week with custom prompts if provided
            entries = self.generate_weekly_entries(
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
        
    def _generate_with_custom_prompt(self, start_date: str, end_date: str, 
                                   custom_prompt: str, 
                                   evidence_types: List[str] = None) -> List[Dict[str, Any]]:
        """Generate time entries using a completely custom prompt"""
        try:
            # Get evidence for the date range, filtered by requested types
            filters = {
                'start_date': start_date,
                'end_date': end_date
            }
            
            # Get evidence filtered by type if specified
            evidence_items = []
            if evidence_types:
                for evidence_type in evidence_types:
                    type_filters = filters.copy()
                    type_filters['type'] = evidence_type
                    type_evidence = self.evidence_db.query_evidence(type_filters)
                    evidence_items.extend(type_evidence)
            else:
                # Get all evidence
                evidence_items = self.evidence_db.query_evidence(filters)
            
            print(f"Found {len(evidence_items)} evidence items for date range")
            
            # Get existing time entries
            existing_entries = self.evidence_db.query_time_entries(filters)
            
            # Format evidence for the prompt
            evidence_summary = {}
            for item in evidence_items:
                item_type = item.get('type', 'unknown')
                if item_type not in evidence_summary:
                    evidence_summary[item_type] = 0
                evidence_summary[item_type] += 1
            
            # Get case context
            case_context = self.get_case_context()
            
            # Call the API with the custom prompt
            if hasattr(self, 'llm_client') and self.llm_client:
                # Use client if available
                print("Using LLM client for custom prompt")
                
                # Use defaults if not specified
                model_id = getattr(self, 'chosen_model_id', 'gpt-3.5-turbo')
                provider = getattr(self, 'chosen_provider', 'openai')
                temperature = getattr(self, 'chosen_temperature', 0.7)
                
                result = self.llm_client.generate_text(
                    model_id=model_id,
                    provider=provider,
                    prompt=custom_prompt,
                    system_prompt="You are a legal billing specialist generating time entries based on evidence.",
                    temperature=temperature,
                    max_tokens=2000
                )
            else:
                # Use direct OpenAI API
                print("Using direct OpenAI API for custom prompt")
                from openai import OpenAI
                
                direct_client = OpenAI(api_key=self.openai_api_key)
                response = direct_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a legal billing specialist generating time entries based on evidence."},
                        {"role": "user", "content": custom_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2000
                )
                
                result = response.choices[0].message.content
            
            # Parse the result
            try:
                # Clean the result
                result = result.strip()
                print(f"Raw result from API: {result[:500]}...")
                
                # Handle markdown code blocks
                if result.startswith('```json'):
                    result = result.replace('```json', '', 1)
                elif result.startswith('```'):
                    result = result.replace('```', '', 1)
                if result.endswith('```'):
                    result = result.rsplit('```', 1)[0]
                result = result.strip()
                
                # First try to parse as JSON
                try:
                    entries = json.loads(result)
                except json.JSONDecodeError:
                    # If JSON parsing fails, try to extract structured data from text
                    print("JSON parsing failed, attempting to parse from text...")
                    entries = self._extract_time_entries_from_text(result)
                    if not entries:
                        print("Could not extract time entries from text response")
                        return []
                
                # Process entries to ensure they have all required fields
                processed_entries = []
                
                # Get matter name from case context
                matter_name = "Default Legal Matter"
                for line in case_context.split('\n'):
                    if line.startswith("Case Name:"):
                        matter_name = line.replace("Case Name:", "").strip()
                        break
                
                for entry in entries:
                    # Create a standardized entry
                    processed_entry = {
                        'id': str(uuid.uuid4()),
                        'date': entry.get('date'),
                        'matter': entry.get('matter', matter_name),
                        'activity_description': entry.get('activity_description', ''),
                        'note': entry.get('note', ''),
                        'price': float(entry.get('price', 0)),
                        'quantity': float(entry.get('quantity', 0)),
                        'type': entry.get('type', 'TimeEntry'),
                        'activity_user': entry.get('activity_user', 'Mark Piesner'),
                        'non_billable': float(entry.get('non_billable', 0)),
                        'rate': 475.0,  # Default attorney rate
                        'evidenceids': entry.get('evidenceids', '')
                    }
                    
                    # Handle date format conversion
                    date_str = entry.get('date', '')
                    if date_str and '/' in date_str:
                        try:
                            month, day, year = date_str.split('/')
                            processed_entry['date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        except:
                            pass  # Keep original if parsing fails
                    
                    # Calculate missing fields if needed
                    if processed_entry['price'] == 0 and processed_entry['quantity'] > 0:
                        processed_entry['price'] = processed_entry['quantity'] * processed_entry['rate']
                    elif processed_entry['quantity'] == 0 and processed_entry['price'] > 0:
                        processed_entry['quantity'] = processed_entry['price'] / processed_entry['rate']
                    
                    # If no hours or price, default to 0.1 hours
                    if processed_entry['price'] == 0 and processed_entry['quantity'] == 0:
                        processed_entry['quantity'] = 0.1
                        processed_entry['price'] = 0.1 * processed_entry['rate']
                    
                    processed_entries.append(processed_entry)
                
                return processed_entries
            except Exception as e:
                print(f"Error parsing response: {e}")
                print(f"Raw response: {result}")
                return []
                
        except Exception as e:
            print(f"Error generating time entries with custom prompt: {e}")
            return []
         
    def export_time_entries(self, output_path: str, start_date: Optional[str] = None, 
                      end_date: Optional[str] = None) -> int:
        """
        Export time entries to a CSV file in the required format
        
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
        
        # Define the required columns in the exact order needed
        required_columns = [
            'matter', 'date', 'activity_description', 'note', 'price', 
            'quantity', 'type', 'activity_user', 'non_billable'
        ]
        
        # Prepare data for DataFrame, ensuring all required columns exist
        formatted_entries = []
        for entry in entries:
            # Get the core data
            formatted_entry = {}
            
            # Some entries might have raw_data field with the full data
            if 'raw_data' in entry and isinstance(entry['raw_data'], dict):
                raw_data = entry['raw_data']
                # Copy required fields from raw_data if available
                for col in required_columns:
                    if col in raw_data:
                        formatted_entry[col] = raw_data[col]
            
            # Ensure all the required fields are present with default values if needed
            formatted_entry['matter'] = entry.get('matter', 'Default Matter Name')
            
            # Format date properly
            date_val = entry.get('date', '')
            if date_val and 'T' in date_val:  # ISO format date
                formatted_entry['date'] = date_val.split('T')[0]
            else:
                formatted_entry['date'] = date_val
            
            # Map legacy fields to new format if needed
            if 'description' in entry and 'activity_description' not in formatted_entry:
                formatted_entry['activity_description'] = entry['description']
            else:
                formatted_entry['activity_description'] = entry.get('activity_description', '')
            
            # Set other required fields
            formatted_entry['note'] = entry.get('note', '')
            
            # Handle pricing details
            formatted_entry['price'] = float(entry.get('price', 0.0))
            
            # Handle quantity (hours)
            if 'quantity' in entry:
                formatted_entry['quantity'] = float(entry.get('quantity', 0.0))
            else:
                formatted_entry['quantity'] = float(entry.get('hours', 0.0))
            
            # Handle activity type
            if 'type' in entry:
                formatted_entry['type'] = entry.get('type')
            else:
                formatted_entry['type'] = entry.get('activity_category', 'client_communication')
            
            # Handle activity user
            formatted_entry['activity_user'] = entry.get('activity_user', entry.get('user', 'Attorney'))
            
            # Handle non-billable flag
            formatted_entry['non_billable'] = float(entry.get('non_billable', 0.0))
            
            # Verify and fix prices if they're inconsistent
            if formatted_entry['price'] == 0 and formatted_entry['quantity'] > 0:
                rate = float(entry.get('rate', 250.0))
                formatted_entry['price'] = formatted_entry['quantity'] * rate
            
            formatted_entries.append(formatted_entry)
        
        # Convert to DataFrame with specific column order
        df = pd.DataFrame(formatted_entries)
        
        # Ensure all required columns exist
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Reorder columns to match the required format
        df = df[required_columns]
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        print(f"Exported {len(entries)} time entries to {output_path}")
        return len(entries)

    def _summarize_evidence_item(self, item: Dict[str, Any]) -> str:
        """Create a brief summary of an evidence item"""
        item_type = item.get("type", "unknown")
        
        if item_type == "email":
            return f"Email: {item.get('subject', 'No subject')} - From: {item.get('from', 'Unknown')}"
        elif item_type == "sms":
            text = item.get("text", "")
            if len(text) > 50:
                text = text[:47] + "..."
            return f"SMS: {text}"
        elif item_type == "docket":
            return f"Docket: {item.get('event_type', 'Unknown event')} - {item.get('memo', '')}"
        elif item_type == "phone_call":
            return f"Call: {item.get('contact', 'Unknown')} - Duration: {item.get('duration_seconds', 0) // 60} min"
        else:
            return f"{item_type.capitalize()} item"
    
    def parse_time_entries_from_response(self, response, start_date, end_date):
        """Parse time entries from an AI response.
        
        Args:
            response (str): The AI response text
            start_date (str): Start date in YYYY-MM-DD format
            end_date (str): End date in YYYY-MM-DD format
            
        Returns:
            list: List of parsed time entry dictionaries
        """
        print("Parsing time entries from AI response")
        entries = []
        
        # Simple parsing by looking for date patterns
        import re
        
        # Look for time entry blocks, which start with a date
        date_pattern = r"Date: (\d{4}-\d{2}-\d{2})"
        hours_pattern = r"Hours: (\d+\.\d+)"
        activity_pattern = r"Activity( Category)?: (\w+)"
        description_pattern = r"Description: (.+?)(?=\n|$)"
        evidence_pattern = r"(Used )?Evidence( IDs)?:? ?\[([^\]]+)\]"
        
        # First try to find entries with clear Date: pattern
        date_matches = re.finditer(date_pattern, response)
        for date_match in date_matches:
            date_pos = date_match.start()
            date_value = date_match.group(1)
            
            # Find the end of this entry (next date or end of text)
            next_date_match = re.search(date_pattern, response[date_pos + 10:])
            if next_date_match:
                entry_text = response[date_pos:date_pos + 10 + next_date_match.start()]
            else:
                entry_text = response[date_pos:]
                
            # Extract details from this entry
            entry = {'date': date_value}
            
            # Extract hours
            hours_match = re.search(hours_pattern, entry_text)
            if hours_match:
                try:
                    entry['hours'] = float(hours_match.group(1))
                except:
                    entry['hours'] = 0.0
            
            # Extract activity category
            activity_match = re.search(activity_pattern, entry_text)
            if activity_match:
                entry['activity_category'] = activity_match.group(2)
            
            # Extract description
            desc_match = re.search(description_pattern, entry_text)
            if desc_match:
                entry['description'] = desc_match.group(1).strip()
            
            # Extract evidence IDs
            evidence_match = re.search(evidence_pattern, entry_text)
            if evidence_match:
                evidence_list = evidence_match.group(3).strip()
                # Parse comma or space separated list
                evidence_ids = [
                    item.strip(' ",\'')  # Remove quotes and spaces
                    for item in re.split(r'[,\s]+', evidence_list)
                    if item.strip(' ",\'')  # Skip empty items
                ]
                entry['used_evidence'] = evidence_ids
            
            # Validate the entry
            if 'description' in entry:
                entries.append(entry)
        
        # If no entries found using the structured format, try to parse JSON
        if not entries:
            try:
                # Look for JSON array in the response
                import json
                
                json_start = response.find('[')
                json_end = response.rfind(']')
                
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end+1]
                    try:
                        json_entries = json.loads(json_str)
                        
                        # Process JSON entries
                        for json_entry in json_entries:
                            entry = {}
                            
                            # Extract date - handle different formats
                            if 'date' in json_entry:
                                date_str = json_entry['date']
                                # Convert MM/DD/YYYY to YYYY-MM-DD if needed
                                if '/' in date_str:
                                    try:
                                        month, day, year = date_str.split('/')
                                        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                                    except:
                                        pass  # Keep original if parsing fails
                                entry['date'] = date_str
                            
                            # Extract hours/quantity
                            if 'hours' in json_entry:
                                entry['hours'] = float(json_entry['hours'])
                            elif 'quantity' in json_entry:
                                entry['hours'] = float(json_entry['quantity'])
                            
                            # Extract activity category
                            if 'activity_category' in json_entry:
                                entry['activity_category'] = json_entry['activity_category']
                            elif 'activity_description' in json_entry:
                                # Parse activity_description like "08 = Drafting"
                                activity_desc = json_entry['activity_description']
                                if ' = ' in activity_desc:
                                    entry['activity_category'] = activity_desc.split(' = ')[1]
                                else:
                                    entry['activity_category'] = activity_desc
                            
                            # Extract description
                            if 'description' in json_entry:
                                entry['description'] = json_entry['description']
                            elif 'note' in json_entry:
                                entry['description'] = json_entry['note']
                            
                            # Extract evidence IDs
                            if 'used_evidence' in json_entry:
                                entry['used_evidence'] = json_entry['used_evidence']
                            elif 'evidenceids' in json_entry:
                                evidence_str = json_entry['evidenceids']
                                if isinstance(evidence_str, str):
                                    entry['used_evidence'] = [id.strip() for id in re.split(r'[,;\s]+', evidence_str) if id.strip()]
                                elif isinstance(evidence_str, list):
                                    entry['used_evidence'] = evidence_str
                            
                            # Add entry if it has minimum required fields
                            if 'date' in entry and 'description' in entry:
                                entries.append(entry)
                    except json.JSONDecodeError:
                        print("Failed to parse JSON in response")
            except Exception as e:
                print(f"Error parsing JSON entries: {e}")
        
        # If no entries found using the structured format or JSON, try a more flexible approach
        if not entries:
            # Look for date patterns in the text
            date_matches = re.finditer(r'\b(\d{4}-\d{2}-\d{2})\b', response)
            for date_match in date_matches:
                date_pos = date_match.start()
                date_value = date_match.group(1)
                
                # Find the context around this date (100 chars before and after)
                start_pos = max(0, date_pos - 100)
                end_pos = min(len(response), date_pos + 100)
                context = response[start_pos:end_pos]
                
                # Extract hours (look for numbers with decimal point)
                hours_match = re.search(r'(\d+\.\d+)', context)
                
                # Only create entry if we found hours
                if hours_match:
                    entry = {'date': date_value}
                    try:
                        entry['hours'] = float(hours_match.group(1))
                    except:
                        entry['hours'] = 0.0
                    
                    # Get description (everything after the date and hours)
                    desc_start = context.find(hours_match.group(0)) + len(hours_match.group(0))
                    description = context[desc_start:].strip()
                    if description:
                        entry['description'] = description[:100]  # Limit to 100 chars
                        entry['activity_category'] = 'general'  # Default category
                        entries.append(entry)
        
        # If we still have no entries, create a generic one
        if not entries:
            entry = {
                'date': start_date,
                'hours': 0.5,
                'activity_category': 'general',
                'description': 'Work on legal matter and review of evidence.',
                'used_evidence': []
            }
            entries.append(entry)
            
        print(f"Parsed {len(entries)} time entries from response")
        return entries

    def format_evidence_for_prompt(self, evidence_items):
        """Format evidence for inclusion in the AI prompt."""
        formatted = f"EVIDENCE SUMMARY ({len(evidence_items)} items):\n\n"
        
        # Group evidence by type for summary
        evidence_by_type = {}
        for item in evidence_items:
            item_type = item.get('type', 'unknown')
            if item_type not in evidence_by_type:
                evidence_by_type[item_type] = 0
            evidence_by_type[item_type] += 1
        
        # Add evidence type summary
        for item_type, count in evidence_by_type.items():
            formatted += f"{item_type.upper()}: {count} items\n"
        
        formatted += "\n=== DETAILED EVIDENCE ===\n\n"
        
        # Sort by timestamp
        sorted_items = sorted(evidence_items, key=lambda x: str(x.get('timestamp', '')))
        
        for i, item in enumerate(sorted_items, 1):
            item_type = item.get('type', 'unknown')
            timestamp = item.get('timestamp', 'Unknown time')
            item_id = item.get('id', f'unknown-{i}')
            
            if isinstance(timestamp, str) and 'T' in timestamp:
                # Format datetime for readability
                date_part, time_part = timestamp.split('T')
                if '.' in time_part:
                    time_part = time_part.split('.')[0]  # Remove milliseconds
                timestamp = f"{date_part} {time_part}"
            
            formatted += f"[{i}] {item_type.upper()} - {timestamp} - ID: {item_id}\n"
            
            if item_type == 'email':
                formatted += f"From: {item.get('from', 'Unknown')}\n"
                formatted += f"To: {item.get('to', 'Unknown')}\n"
                formatted += f"Subject: {item.get('subject', 'No subject')}\n"
                
                body = item.get('body', '')
                if len(body) > 300:
                    body = body[:297] + '...'
                formatted += f"Body: {body}\n"
                
            elif item_type == 'sms':
                formatted += f"Direction: {item.get('direction', 'Unknown')}\n"
                text = item.get('text', '')
                if len(text) > 200:
                    text = text[:197] + '...'
                formatted += f"Text: {text}\n"
                
            elif item_type == 'docket':
                formatted += f"Event Type: {item.get('event_type', 'Unknown')}\n"
                formatted += f"Memo: {item.get('memo', '')}\n"
                
            elif item_type == 'phone_call':
                formatted += f"Contact: {item.get('contact', 'Unknown')}\n"
                duration_secs = item.get('duration_seconds', 0)
                if isinstance(duration_secs, (int, float)):
                    minutes = duration_secs // 60
                    seconds = duration_secs % 60
                    formatted += f"Duration: {minutes}:{seconds:02d}\n"
                else:
                    formatted += "Duration: Unknown\n"
            
            formatted += '\n'  # Empty line between items
        
        return formatted
    
    def _extract_time_entries_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract time entries from a text response that isn't properly formatted as JSON
        
        Args:
            text: Text containing time entry information
            
        Returns:
            List of parsed time entries as dictionaries
        """
        entries = []
        
        # Common patterns in time entries
        date_patterns = [
            r'Date:\s*([\d/\-]+)',  # Date: MM/DD/YYYY or YYYY-MM-DD
            r'date:\s*([\d/\-]+)',  # date: MM/DD/YYYY or YYYY-MM-DD
            r'dated?\s+([\d/\-]+)'  # dated MM/DD/YYYY or YYYY-MM-DD
        ]
        
        quantity_patterns = [
            r'Quantity:\s*([\d\.]+)',  # Quantity: 0.5
            r'quantity:\s*([\d\.]+)',  # quantity: 0.5
            r'Hours:\s*([\d\.]+)',     # Hours: 0.5
            r'hours:\s*([\d\.]+)'      # hours: 0.5
        ]
        
        activity_patterns = [
            r'Activity.*Description:\s*(.+?)[\n\r]',   # Activity Description: text
            r'activity.*description:\s*(.+?)[\n\r]',   # activity description: text
            r'Activity.*Category:\s*(.+?)[\n\r]',      # Activity Category: text
            r'activity.*category:\s*(.+?)[\n\r]'       # activity category: text
        ]
        
        note_patterns = [
            r'Note:\s*(.+?)[\n\r]',     # Note: text
            r'note:\s*(.+?)[\n\r]',     # note: text
            r'Description:\s*(.+?)[\n\r]',  # Description: text
            r'description:\s*(.+?)[\n\r]'   # description: text
        ]
        
        price_patterns = [
            r'Price:\s*([\d\.]+)',       # Price: 475
            r'price:\s*([\d\.]+)',       # price: 475
            r'Rate:\s*([\d\.]+)',        # Rate: 475
            r'rate:\s*([\d\.]+)'         # rate: 475
        ]
        
        user_patterns = [
            r'Activity User:\s*(.+?)[\n\r]',    # Activity User: text
            r'activity user:\s*(.+?)[\n\r]',    # activity user: text
            r'User:\s*(.+?)[\n\r]',             # User: text
            r'user:\s*(.+?)[\n\r]'              # user: text
        ]
        
        matter_patterns = [
            r'Matter:\s*"?([^"\n\r]+)"?',     # Matter: "text" or Matter: text
            r'matter:\s*"?([^"\n\r]+)"?'      # matter: "text" or matter: text
        ]
        
        evidence_patterns = [
            r'Evidence.*IDs?:\s*(.+?)[\n\r]',    # Evidence IDs: text
            r'evidence.*ids?:\s*(.+?)[\n\r]',    # evidence ids: text
            r'Used Evidence:\s*(.+?)[\n\r]',     # Used Evidence: text
            r'used evidence:\s*(.+?)[\n\r]'      # used evidence: text
        ]
        
        # Look for blocks of text that might contain a complete time entry
        # These are often separated by multiple newlines, horizontal rules, or other markers
        entry_blocks = re.split(r'\n\s*\n|\-\-\-+|\*\*\*+|\={3,}', text)
        
        print(f"Found {len(entry_blocks)} potential entry blocks")
        
        for block in entry_blocks:
            # Skip empty blocks
            if not block.strip():
                continue
                
            # See if this looks like a time entry
            entry_data = {}
            
            # Extract date
            for pattern in date_patterns:
                match = re.search(pattern, block)
                if match:
                    date_str = match.group(1).strip()
                    # Convert MM/DD/YYYY to YYYY-MM-DD if needed
                    if '/' in date_str:
                        try:
                            month, day, year = date_str.split('/')
                            entry_data['date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        except:
                            entry_data['date'] = date_str
                    else:
                        entry_data['date'] = date_str
                    break
            
            # Extract quantity/hours
            for pattern in quantity_patterns:
                match = re.search(pattern, block)
                if match:
                    try:
                        entry_data['quantity'] = float(match.group(1).strip())
                    except:
                        pass
                    break
            
            # Extract activity description
            for pattern in activity_patterns:
                match = re.search(pattern, block)
                if match:
                    entry_data['activity_description'] = match.group(1).strip()
                    break
            
            # Extract note/description
            for pattern in note_patterns:
                match = re.search(pattern, block)
                if match:
                    entry_data['note'] = match.group(1).strip()
                    break
            
            # Extract price/rate
            for pattern in price_patterns:
                match = re.search(pattern, block)
                if match:
                    try:
                        entry_data['price'] = float(match.group(1).strip())
                    except:
                        pass
                    break
            
            # Extract user
            for pattern in user_patterns:
                match = re.search(pattern, block)
                if match:
                    entry_data['activity_user'] = match.group(1).strip()
                    break
            
            # Extract matter
            for pattern in matter_patterns:
                match = re.search(pattern, block)
                if match:
                    entry_data['matter'] = match.group(1).strip()
                    break
            
            # Extract evidence IDs
            for pattern in evidence_patterns:
                match = re.search(pattern, block)
                if match:
                    entry_data['evidenceids'] = match.group(1).strip()
                    break
            
            # Add default type
            if 'type' not in entry_data:
                entry_data['type'] = 'TimeEntry'
            
            # Add default non_billable
            if 'non_billable' not in entry_data:
                entry_data['non_billable'] = 0
            
            # Only add the entry if it has at least a date and some description
            if 'date' in entry_data and ('note' in entry_data or 'activity_description' in entry_data):
                # Generate a random UUID for the entry
                entry_data['id'] = str(uuid.uuid4())
                entries.append(entry_data)
        
        print(f"Successfully extracted {len(entries)} time entries from text")
        return entries

    def _format_evidence_for_analysis(self, evidence_items: List[Dict[str, Any]]) -> str:
        """Format evidence items for analysis by the LLM"""
        # Sort by timestamp
        sorted_items = sorted(evidence_items, key=lambda x: x.get("timestamp", ""))
        
        details = []
        for i, item in enumerate(sorted_items, 1):
            item_type = item.get("type", "unknown")
            timestamp = item.get("timestamp", "Unknown time")
            
            if isinstance(timestamp, str) and "T" in timestamp:
                # Format datetime for readability
                date_part, time_part = timestamp.split("T")
                time_part = time_part.split(".")[0]  # Remove milliseconds
                timestamp = f"{date_part} {time_part}"
            
            details.append(f"Item {i} ({item_type}) - Time: {timestamp}")
            
            if item_type == "email":
                details.append(f"From: {item.get('from', 'Unknown')}")
                details.append(f"To: {item.get('to', 'Unknown')}")
                details.append(f"Subject: {item.get('subject', 'No subject')}")
                
                body = item.get("body", "")
                if len(body) > 500:
                    body = body[:497] + "..."
                details.append(f"Body: {body}")
                
                if item.get("has_attachment", False):
                    details.append(f"Attachments: {item.get('attachment_names', 'Unknown')}")
            
            elif item_type == "sms":
                details.append(f"Direction: {item.get('direction', 'Unknown')}")
                details.append(f"Text: {item.get('text', '')}")
            
            elif item_type == "docket":
                details.append(f"Event Type: {item.get('event_type', 'Unknown')}")
                details.append(f"Memo: {item.get('memo', '')}")
                details.append(f"Filed By: {item.get('filed_by', '')}")
            
            elif item_type == "phone_call":
                duration_secs = item.get("duration_seconds", 0)
                duration_mins = duration_secs // 60
                details.append(f"Call Type: {item.get('call_type', 'Unknown')}")
                details.append(f"Contact: {item.get('contact', 'Unknown')}")
                details.append(f"Duration: {duration_mins} minutes")
            
            details.append("")  # Empty line between items
        
        return "\n".join(details)