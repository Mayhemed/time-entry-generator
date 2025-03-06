import React, { useState, useEffect } from 'react';
import EvidenceViewer from './EvidenceViewer';
import AiPromptManager from './AiPromptManager';
import { Clock, Loader, FileDown, Save, AlertCircle } from 'lucide-react';

const IntegratedSystem = ({ initialData = null }) => {
  // State for evidence data
  const [evidenceData, setEvidenceData] = useState(null);
  const [dateRange, setDateRange] = useState({ start: '', end: '' });
  const [selectedEvidence, setSelectedEvidence] = useState({});
  
  // State for AI processing
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('evidence');
  
  // History of prompts run
  const [promptHistory, setPromptHistory] = useState([]);
  
  // Load initial data
  useEffect(() => {
    if (initialData) {
      setEvidenceData(initialData);
    } else {
      // In a real app, you would fetch data from the backend here
      // For now, we'll load from localStorage if available
      const storedData = localStorage.getItem('evidenceData');
      if (storedData) {
        try {
          setEvidenceData(JSON.parse(storedData));
        } catch (error) {
          console.error('Error loading stored data:', error);
        }
      }
    }
  }, [initialData]);

  // Handle evidence selection changes
  const handleSelectionChange = (selections) => {
    setSelectedEvidence(selections);
  };

  // Handle date range changes
  const handleDateRangeChange = (range) => {
    setDateRange(range);
  };

  // Helper to count total selected evidence
  const countSelectedEvidence = () => {
    return Object.values(selectedEvidence).reduce(
      (total, selectionsArray) => total + (selectionsArray?.length || 0), 
      0
    );
  };

  // Run prompt with selected evidence
  const runPrompt = async (prompt) => {
    setIsProcessing(true);
    setError(null);
    
    try {
      // Check if there's any evidence selected
      const totalSelected = countSelectedEvidence();
      if (totalSelected === 0) {
        throw new Error('No evidence selected. Please select some evidence items first.');
      }

      // Prepare the evidence data to send
      const evidenceToSend = {};
      
      for (const [type, ids] of Object.entries(selectedEvidence)) {
        if (ids && ids.length > 0 && evidenceData && evidenceData[type]) {
          evidenceToSend[type] = evidenceData[type].filter(item => ids.includes(item.id));
        }
      }

      // In a real app, you would send this to your backend
      // For demo purposes, we'll simulate an API call with a timeout
      console.log('Running prompt with:', prompt);
      console.log('Evidence being processed:', evidenceToSend);
      
      // Record this run in history
      const historyEntry = {
        id: Date.now().toString(),
        promptName: prompt.name,
        timestamp: new Date().toISOString(),
        evidenceCount: totalSelected,
        dateRange: {...dateRange}
      };
      
      setPromptHistory(prev => [historyEntry, ...prev]);
      
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // For this demo, we'll generate mock results based on the prompt type
      let mockResults;
      
      switch(prompt.goal) {
        case 'time_entries':
          mockResults = generateMockTimeEntries(evidenceToSend);
          break;
        case 'project_timeline':
          mockResults = generateMockProjectTimeline(evidenceToSend);
          break;
        case 'evidence_summary':
          mockResults = generateMockEvidenceSummary(evidenceToSend);
          break;
        case 'key_themes':
          mockResults = generateMockKeyThemes(evidenceToSend);
          break;
        case 'case_narrative':
          mockResults = generateMockCaseNarrative(evidenceToSend);
          break;
        default:
          mockResults = {
            type: 'custom',
            data: {
              title: 'Custom Output',
              content: 'This is a placeholder for custom output based on your prompt.'
            }
          };
      }
      
      setResults(mockResults);
      
      // Switch to results tab
      setActiveTab('results');
      
    } catch (error) {
      console.error('Error running prompt:', error);
      setError(error.message || 'An unexpected error occurred');
    } finally {
      setIsProcessing(false);
    }
  };

  // Mock result generators
  const generateMockTimeEntries = (evidence) => {
    const entries = [];
    const today = new Date();
    
    // Generate mock time entries based on evidence
    const totalEmails = evidence.emails?.length || 0;
    const totalSms = evidence.sms?.length || 0;
    const totalCalls = evidence.phone_calls?.length || 0;
    const totalDocketEntries = evidence.docket_entries?.length || 0;
    
    // Email review
    if (totalEmails > 0) {
      entries.push({
        id: `entry_${Date.now()}_1`,
        date: today.toISOString().split('T')[0],
        hours: Math.round((totalEmails * 0.1) * 10) / 10, // 6 min per email
        activity_category: 'client_communication',
        description: `Review and respond to ${totalEmails} client email${totalEmails > 1 ? 's' : ''}`,
        rate: 475.00,
        billable: Math.round((totalEmails * 0.1) * 475 * 100) / 100
      });
    }
    
    // SMS review
    if (totalSms > 0) {
      entries.push({
        id: `entry_${Date.now()}_2`,
        date: today.toISOString().split('T')[0],
        hours: Math.round((totalSms * 0.05) * 10) / 10, // 3 min per SMS
        activity_category: 'client_communication',
        description: `Review and respond to ${totalSms} text message${totalSms > 1 ? 's' : ''}`,
        rate: 475.00,
        billable: Math.round((totalSms * 0.05) * 475 * 100) / 100
      });
    }
    
    // Call time
    if (totalCalls > 0) {
      // Calculate actual call duration in hours
      const totalDuration = evidence.phone_calls.reduce(
        (sum, call) => sum + (call.duration_seconds || 0), 0
      ) / 3600; // convert to hours
      
      entries.push({
        id: `entry_${Date.now()}_3`,
        date: today.toISOString().split('T')[0],
        hours: Math.round(totalDuration * 10) / 10,
        activity_category: 'client_communication',
        description: `Phone calls with client and related parties (${totalCalls} call${totalCalls > 1 ? 's' : ''})`,
        rate: 475.00,
        billable: Math.round(totalDuration * 475 * 100) / 100
      });
    }
    
    // Docket review
    if (totalDocketEntries > 0) {
      entries.push({
        id: `entry_${Date.now()}_4`,
        date: today.toISOString().split('T')[0],
        hours: Math.round((totalDocketEntries * 0.3) * 10) / 10, // 18 min per docket entry
        activity_category: 'legal_research',
        description: `Review and analyze ${totalDocketEntries} docket entries and case developments`,
        rate: 475.00,
        billable: Math.round((totalDocketEntries * 0.3) * 475 * 100) / 100
      });
    }
    
    return {
      type: 'time_entries',
      data: entries
    };
  };
  
  const generateMockProjectTimeline = (evidence) => {
    // Extract all evidence items into a single array with type information
    const allItems = [];
    
    for (const [type, items] of Object.entries(evidence)) {
      if (items && items.length > 0) {
        items.forEach(item => {
          allItems.push({
            ...item,
            evidenceType: type
          });
        });
      }
    }
    
    // Sort by date
    allItems.sort((a, b) => {
      const dateA = new Date(a.timestamp || a.date);
      const dateB = new Date(b.timestamp || b.date);
      return dateA - dateB;
    });
    
    // Group by day
    const timeline = {};
    
    allItems.forEach(item => {
      const date = new Date(item.timestamp || item.date);
      const dateStr = date.toISOString().split('T')[0];
      
      if (!timeline[dateStr]) {
        timeline[dateStr] = [];
      }
      
      timeline[dateStr].push(item);
    });
    
    // Convert to array format
    const timelineArray = Object.entries(timeline).map(([date, items]) => ({
      date,
      items
    }));
    
    return {
      type: 'project_timeline',
      data: timelineArray
    };
  };
  
  const generateMockEvidenceSummary = (evidence) => {
    // Count by type
    const counts = {
      emails: evidence.emails?.length || 0,
      sms: evidence.sms?.length || 0,
      phone_calls: evidence.phone_calls?.length || 0,
      docket_entries: evidence.docket_entries?.length || 0
    };
    
    // Find date range
    let minDate = new Date();
    let maxDate = new Date(0); // epoch start
    
    for (const [type, items] of Object.entries(evidence)) {
      if (items && items.length > 0) {
        items.forEach(item => {
          const date = new Date(item.timestamp || item.date);
          if (date < minDate) minDate = date;
          if (date > maxDate) maxDate = date;
        });
      }
    }
    
    const dateRange = {
      start: minDate.toISOString().split('T')[0],
      end: maxDate.toISOString().split('T')[0]
    };
    
    // Key participants
    const participants = new Set();
    
    if (evidence.emails && evidence.emails.length > 0) {
      evidence.emails.forEach(email => {
        if (email.from) participants.add(email.from);
        if (email.to) {
          email.to.split(',').forEach(recipient => {
            participants.add(recipient.trim());
          });
        }
      });
    }
    
    return {
      type: 'evidence_summary',
      data: {
        counts,
        dateRange,
        participants: Array.from(participants),
        totalItems: Object.values(counts).reduce((a, b) => a + b, 0)
      }
    };
  };
  
  const generateMockKeyThemes = (evidence) => {
    // Pretend we've identified key themes in the evidence
    return {
      type: 'key_themes',
      data: [
        {
          id: 'theme_1',
          name: 'Contract Dispute',
          description: 'Issues related to the interpretation of section 5.3 of the contract',
          relevance: 'high',
          relatedEvidence: 7
        },
        {
          id: 'theme_2',
          name: 'Timeline Discrepancies',
          description: 'Conflicting accounts of when certain events occurred',
          relevance: 'medium',
          relatedEvidence: 5
        },
        {
          id: 'theme_3',
          name: 'Settlement Negotiations',
          description: 'Multiple attempts to reach settlement terms',
          relevance: 'high',
          relatedEvidence: 9
        },
        {
          id: 'theme_4',
          name: 'Procedural Issues',
          description: 'Questions about filing deadlines and proper notice',
          relevance: 'low',
          relatedEvidence: 3
        }
      ]
    };
  };
  
  const generateMockCaseNarrative = (evidence) => {
    return {
      type: 'case_narrative',
      data: {
        title: 'Case Narrative',
        introduction: 'This case involves a contract dispute between the plaintiff and defendant over terms related to service delivery and payment schedules.',
        keyEvents: [
          {
            date: '2024-01-15',
            title: 'Contract Execution',
            description: 'Parties executed the service agreement with a 12-month term'
          },
          {
            date: '2024-02-28',
            title: 'First Payment Dispute',
            description: 'Defendant disputed invoice claiming services were not delivered as specified'
          },
          {
            date: '2024-03-10',
            title: 'Attempted Resolution',
            description: 'Parties met to discuss disagreements but failed to reach resolution'
          },
          {
            date: '2024-04-05',
            title: 'Notice of Breach',
            description: 'Plaintiff sent formal notice of breach with 30-day cure period'
          }
        ],
        conclusion: 'The evidence suggests a pattern of communication breakdowns and different interpretations of the contract terms, particularly regarding the quality metrics in Section 3.2.'
      }
    };
  };

  // Render the results based on type
  const renderResults = () => {
    if (!results) return null;
    
    switch(results.type) {
      case 'time_entries':
        return renderTimeEntries(results.data);
      case 'project_timeline':
        return renderProjectTimeline(results.data);
      case 'evidence_summary':
        return renderEvidenceSummary(results.data);
      case 'key_themes':
        return renderKeyThemes(results.data);
      case 'case_narrative':
        return renderCaseNarrative(results.data);
      default:
        return (
          <div className="p-4 bg-gray-50 rounded border">
            <h3 className="text-lg font-medium mb-2">Custom Output</h3>
            <pre className="whitespace-pre-wrap bg-white p-3 rounded border">
              {JSON.stringify(results.data, null, 2)}
            </pre>
          </div>
        );
    }
  };
  
  // Render time entries
  const renderTimeEntries = (entries) => {
    if (!entries || entries.length === 0) {
      return (
        <div className="text-center p-4 bg-yellow-50 text-yellow-800 rounded border border-yellow-200">
          No time entries generated.
        </div>
      );
    }
    
    // Calculate total
    const totalHours = entries.reduce((sum, entry) => sum + (entry.hours || 0), 0);
    const totalBillable = entries.reduce((sum, entry) => sum + (entry.billable || 0), 0);
    
    return (
      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium">Generated Time Entries</h3>
          <button className="flex items-center text-blue-600 hover:text-blue-800">
            <FileDown size={16} className="mr-1" />
            Export to CSV
          </button>
        </div>
        
        <div className="bg-blue-50 text-blue-800 p-3 rounded border border-blue-200 mb-4">
          <div className="flex justify-between">
            <div>
              <span className="font-medium">Total Entries:</span> {entries.length}
            </div>
            <div>
              <span className="font-medium">Total Hours:</span> {totalHours.toFixed(1)}
            </div>
            <div>
              <span className="font-medium">Total Billable:</span> ${totalBillable.toFixed(2)}
            </div>
          </div>
        </div>
        
        <div className="border rounded overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Date
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Hours
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Activity
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Description
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Billable
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {entries.map(entry => (
                <tr key={entry.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {entry.date}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {entry.hours}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                      {entry.activity_category}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {entry.description}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    ${entry.billable}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="mt-4 flex justify-end">
          <button className="flex items-center bg-blue-600 text-white px-3 py-2 rounded hover:bg-blue-700">
            <Save size={16} className="mr-1" />
            Save Time Entries
          </button>
        </div>
      </div>
    );
  };
  
  // Render project timeline
  const renderProjectTimeline = (timeline) => {
    if (!timeline || timeline.length === 0) {
      return (
        <div className="text-center p-4 bg-yellow-50 text-yellow-800 rounded border border-yellow-200">
          No timeline events found.
        </div>
      );
    }
    
    return (
      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium">Project Timeline</h3>
          <button className="flex items-center text-blue-600 hover:text-blue-800">
            <FileDown size={16} className="mr-1" />
            Export Timeline
          </button>
        </div>
        
        <div className="space-y-8">
          {timeline.map(day => (
            <div key={day.date} className="relative">
              <div className="flex items-center">
                <div className="bg-blue-600 rounded-full h-8 w-8 flex items-center justify-center text-white font-medium z-10">
                  {new Date(day.date).getDate()}
                </div>
                <div className="ml-4">
                  <h4 className="font-medium">
                    {new Date(day.date).toLocaleDateString(undefined, { 
                      weekday: 'long', 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}
                  </h4>
                  <div className="text-sm text-gray-500">
                    {day.items.length} event{day.items.length !== 1 ? 's' : ''}
                  </div>
                </div>
              </div>
              
              <div className="ml-4 pl-8 border-l-2 border-gray-200 mt-2 space-y-4">
                {day.items.map((item, i) => (
                  <div key={`${day.date}_${i}`} className="bg-white p-3 rounded border shadow-sm">
                    <div className="flex items-start">
                      <div className={`rounded-full h-6 w-6 flex items-center justify-center text-white text-xs mr-2 ${
                        item.evidenceType === 'emails' ? 'bg-blue-500' :
                        item.evidenceType === 'sms' ? 'bg-green-500' :
                        item.evidenceType === 'phone_calls' ? 'bg-yellow-500' :
                        'bg-red-500'
                      }`}>
                        {item.evidenceType === 'emails' ? 'E' :
                         item.evidenceType === 'sms' ? 'S' :
                         item.evidenceType === 'phone_calls' ? 'P' : 'D'}
                      </div>
                      <div className="flex-1">
                        <div className="text-sm">
                          {new Date(item.timestamp || item.date).toLocaleTimeString()}
                        </div>
                        <div className="font-medium">
                          {item.evidenceType === 'emails' ? `Email: ${item.subject || 'No Subject'}` :
                           item.evidenceType === 'sms' ? `SMS: ${item.text ? item.text.substring(0, 50) + (item.text.length > 50 ? '...' : '') : 'No Content'}` :
                           item.evidenceType === 'phone_calls' ? `Call: ${item.contact || item.number || 'Unknown'}` :
                           `Docket: ${item.event_type || 'Entry'}`}
                        </div>
                        {item.evidenceType === 'emails' && (
                          <div className="text-sm text-gray-600">
                            From: {item.from} | To: {item.to}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  // Render evidence summary
  const renderEvidenceSummary = (summary) => {
    return (
      <div>
        <h3 className="text-lg font-medium mb-4">Evidence Summary</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <div className="bg-white p-4 rounded border shadow-sm">
            <h4 className="font-medium mb-3">Evidence Counts</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Emails:</span>
                <span className="font-medium">{summary.counts.emails}</span>
              </div>
              <div className="flex justify-between">
                <span>SMS Messages:</span>
                <span className="font-medium">{summary.counts.sms}</span>
              </div>
              <div className="flex justify-between">
                <span>Phone Calls:</span>
                <span className="font-medium">{summary.counts.phone_calls}</span>
              </div>
              <div className="flex justify-between">
                <span>Docket Entries:</span>
                <span className="font-medium">{summary.counts.docket_entries}</span>
              </div>
              <div className="border-t pt-2 mt-2 flex justify-between font-medium">
                <span>Total Items:</span>
                <span>{summary.totalItems}</span>
              </div>
            </div>
          </div>
          
          <div className="bg-white p-4 rounded border shadow-sm">
            <h4 className="font-medium mb-3">Date Range</h4>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Start Date:</span>
                <span className="font-medium">{summary.dateRange.start}</span>
              </div>
              <div className="flex justify-between">
                <span>End Date:</span>
                <span className="font-medium">{summary.dateRange.end}</span>
              </div>
              <div className="flex justify-between">
                <span>Duration:</span>
                <span className="font-medium">
                  {Math.ceil((new Date(summary.dateRange.end) - new Date(summary.dateRange.start)) / (1000 * 60 * 60 * 24))} days
                </span>
              </div>
            </div>
          </div>
        </div>
        
        <div className="bg-white p-4 rounded border shadow-sm">
          <h4 className="font-medium mb-3">Key Participants ({summary.participants.length})</h4>
          <div className="flex flex-wrap gap-2">
            {summary.participants.map((participant, index) => (
              <span key={index} className="bg-gray-100 text-gray-800 px-2 py-1 rounded text-sm">
                {participant}
              </span>
            ))}
          </div>
        </div>
      </div>
    );
  };
  
  // Render key themes
  const renderKeyThemes = (themes) => {
    return (
      <div>
        <h3 className="text-lg font-medium mb-4">Key Themes Identified</h3>
        
        <div className="space-y-4">
          {themes.map(theme => (
            <div key={theme.id} className="bg-white p-4 rounded border shadow-sm">
              <div className="flex items-start">
                <div className={`rounded-full h-6 w-6 flex items-center justify-center text-white text-xs mr-3 ${
                  theme.relevance === 'high' ? 'bg-red-500' :
                  theme.relevance === 'medium' ? 'bg-yellow-500' :
                  'bg-blue-500'
                }`}>
                  {theme.relevance === 'high' ? 'H' :
                   theme.relevance === 'medium' ? 'M' : 'L'}
                </div>
                <div>
                  <h4 className="font-medium">{theme.name}</h4>
                  <p className="text-gray-700 mt-1">{theme.description}</p>
                  <div className="text-sm text-gray-500 mt-2">
                    Related to {theme.relatedEvidence} evidence items
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };
  
  // Render case narrative
  const renderCaseNarrative = (narrative) => {
    return (
      <div>
        <h3 className="text-xl font-medium mb-4">{narrative.title}</h3>
        
        <div className="bg-white p-4 rounded border shadow-sm mb-6">
          <h4 className="font-medium mb-2">Introduction</h4>
          <p className="text-gray-700">{narrative.introduction}</p>
        </div>
        
        <div className="bg-white p-4 rounded border shadow-sm mb-6">
          <h4 className="font-medium mb-4">Key Events</h4>
          <div className="space-y-4">
            {narrative.keyEvents.map((event, index) => (
              <div key={index} className="flex">
                <div className="mr-4 text-sm font-medium w-24 shrink-0">
                  {event.date}
                </div>
                <div>
                  <div className="font-medium">{event.title}</div>
                  <div className="text-gray-700">{event.description}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
        
        <div className="bg-white p-4 rounded border shadow-sm">
          <h4 className="font-medium mb-2">Conclusion</h4>
          <p className="text-gray-700">{narrative.conclusion}</p>
        </div>
      </div>
    );
  };

  return (
    <div className="integrated-system p-4">
      <div className="mb-4">
        <div className="flex border-b">
          <button 
            className={`px-4 py-2 font-medium ${
              activeTab === 'evidence' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab('evidence')}
          >
            Evidence
          </button>
          <button 
            className={`px-4 py-2 font-medium ${
              activeTab === 'prompts' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab('prompts')}
          >
            AI Prompts
          </button>
          <button 
            className={`px-4 py-2 font-medium ${
              activeTab === 'results' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab('results')}
          >
            Results
          </button>
          <button 
            className={`px-4 py-2 font-medium ${
              activeTab === 'history' ? 'text-blue-600 border-b-2 border-blue-600' : 'text-gray-500 hover:text-gray-700'
            }`}
            onClick={() => setActiveTab('history')}
          >
            History
          </button>
        </div>
      </div>
      
      {activeTab === 'evidence' && (
        <div className="evidence-tab">
          {evidenceData ? (
            <EvidenceViewer 
              jsonData={evidenceData} 
              onSelectionChange={handleSelectionChange} 
            />
          ) : (
            <div className="text-center p-8 bg-gray-50 rounded border">
              <p className="text-gray-500 mb-4">No evidence data loaded. Please upload evidence files.</p>
              <button className="bg-blue-600 text-white px-3 py-2 rounded hover:bg-blue-700">
                Upload Evidence
              </button>
            </div>
          )}
        </div>
      )}
      
      {activeTab === 'prompts' && (
        <div className="prompts-tab">
          <AiPromptManager onSubmitPrompt={runPrompt} />
        </div>
      )}
      
      {activeTab === 'results' && (
        <div className="results-tab">
          {isProcessing ? (
            <div className="text-center p-8">
              <Loader className="animate-spin h-10 w-10 text-blue-600 mx-auto mb-4" />
              <p className="text-gray-700">Processing your request...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 border border-red-200 rounded">
              <div className="flex items-start">
                <AlertCircle className="text-red-600 mr-2 mt-0.5" size={20} />
                <div>
                  <h3 className="text-lg font-medium text-red-800">Error</h3>
                  <p className="text-red-700">{error}</p>
                </div>
              </div>
            </div>
          ) : results ? (
            renderResults()
          ) : (
            <div className="text-center p-8 bg-gray-50 rounded border">
              <p className="text-gray-500">No results yet. Run a prompt to generate results.</p>
            </div>
          )}
        </div>
      )}
      
      {activeTab === 'history' && (
        <div className="history-tab">
          <h3 className="text-lg font-medium mb-4">Prompt Run History</h3>
          
          {promptHistory.length > 0 ? (
            <div className="bg-white rounded border overflow-hidden">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date & Time
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Prompt
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Evidence Count
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date Range
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {promptHistory.map(run => (
                    <tr key={run.id}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {new Date(run.timestamp).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {run.promptName}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {run.evidenceCount}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {run.dateRange.start ? (
                          <>
                            {run.dateRange.start} to {run.dateRange.end}
                          </>
                        ) : (
                          <span className="text-gray-500">All dates</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <button className="text-blue-600 hover:text-blue-800">
                          View Results
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center p-4 bg-gray-50 rounded border">
              <Clock className="h-8 w-8 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500">No prompt history yet.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default IntegratedSystem;