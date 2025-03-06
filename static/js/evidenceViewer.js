import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronUp, Calendar, Search } from 'lucide-react';

const EvidenceViewer = ({ jsonData, onSelectionChange }) => {
  // State for evidence data and selection
  const [data, setData] = useState({
    emails: [],
    sms: [],
    docket_entries: [],
    phone_calls: [],
    time_entries: []
  });
  
  // State for selections
  const [selections, setSelections] = useState({
    emails: new Set(),
    sms: new Set(),
    docket_entries: new Set(),
    phone_calls: new Set(),
    time_entries: new Set()
  });
  
  // State for expanded items
  const [expanded, setExpanded] = useState({});
  
  // Date range filter
  const [dateRange, setDateRange] = useState({
    start: '',
    end: ''
  });
  
  // Active tab
  const [activeTab, setActiveTab] = useState('emails');
  
  // Category checkboxes
  const [selectAll, setSelectAll] = useState({
    emails: false,
    sms: false,
    docket_entries: false,
    phone_calls: false,
    time_entries: false
  });
  
  // Load data on component mount
  useEffect(() => {
    if (jsonData) {
      setData(jsonData);
    }
  }, [jsonData]);
  
  // Handle date range changes
  const handleDateChange = (e) => {
    const { name, value } = e.target;
    setDateRange(prev => ({
      ...prev,
      [name]: value
    }));
  };
  
  // Apply date filter to all evidence
  const filteredData = React.useMemo(() => {
    const result = {...data};
    
    Object.keys(result).forEach(type => {
      if (dateRange.start || dateRange.end) {
        result[type] = result[type].filter(item => {
          const itemDate = new Date(item.timestamp || item.date);
          
          if (dateRange.start && dateRange.end) {
            return itemDate >= new Date(dateRange.start) && 
                   itemDate <= new Date(dateRange.end);
          } else if (dateRange.start) {
            return itemDate >= new Date(dateRange.start);
          } else if (dateRange.end) {
            return itemDate <= new Date(dateRange.end);
          }
          return true;
        });
      }
    });
    
    return result;
  }, [data, dateRange]);
  
  // Toggle item expansion
  const toggleExpand = (type, id) => {
    setExpanded(prev => ({
      ...prev,
      [`${type}-${id}`]: !prev[`${type}-${id}`]
    }));
  };
  
  // Toggle selection of individual item
  const toggleSelection = (type, id) => {
    const newSelections = {...selections};
    if (newSelections[type].has(id)) {
      newSelections[type].delete(id);
    } else {
      newSelections[type].add(id);
    }
    setSelections(newSelections);
    
    // Update select all status
    setSelectAll(prev => ({
      ...prev,
      [type]: newSelections[type].size === filteredData[type].length && filteredData[type].length > 0
    }));
    
    // Notify parent component of selection changes
    if (onSelectionChange) {
      const allSelections = {};
      Object.keys(newSelections).forEach(type => {
        allSelections[type] = Array.from(newSelections[type]);
      });
      onSelectionChange(allSelections);
    }
  };
  
  // Toggle select all for a category
  const toggleSelectAll = (type) => {
    const newSelectAll = !selectAll[type];
    setSelectAll(prev => ({
      ...prev,
      [type]: newSelectAll
    }));
    
    const newSelections = {...selections};
    if (newSelectAll) {
      // Select all items in this category
      filteredData[type].forEach(item => {
        newSelections[type].add(item.id);
      });
    } else {
      // Deselect all items in this category
      newSelections[type] = new Set();
    }
    setSelections(newSelections);
    
    // Notify parent component of selection changes
    if (onSelectionChange) {
      const allSelections = {};
      Object.keys(newSelections).forEach(type => {
        allSelections[type] = Array.from(newSelections[type]);
      });
      onSelectionChange(allSelections);
    }
  };
  
  // Evidence type renderers
  const renderEmail = (email) => {
    const isExpanded = expanded[`emails-${email.id}`];
    
    return (
      <div className="border rounded p-3 mb-2 bg-white">
        <div className="flex justify-between items-start">
          <div className="flex items-start">
            <input 
              type="checkbox" 
              className="form-checkbox h-4 w-4 mt-1 mr-2"
              checked={selections.emails.has(email.id)}
              onChange={() => toggleSelection('emails', email.id)}
              id={`email-${email.id}`}
            />
            <label className="cursor-pointer" htmlFor={`email-${email.id}`}>
              <div className="font-medium">{email.subject || 'No Subject'}</div>
              <div className="text-gray-500 text-sm">
                {new Date(email.timestamp).toLocaleString()} | From: {email.from} | To: {email.to}
              </div>
            </label>
          </div>
          <button 
            className="text-gray-500 hover:text-gray-700"
            onClick={() => toggleExpand('emails', email.id)}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
        
        {isExpanded && (
          <div className="mt-3">
            <hr className="my-2" />
            <div className="mb-2">
              <strong>Subject:</strong> {email.subject}
            </div>
            <div className="mb-2">
              <strong>From:</strong> {email.from}
            </div>
            <div className="mb-2">
              <strong>To:</strong> {email.to}
            </div>
            {email.cc && (
              <div className="mb-2">
                <strong>CC:</strong> {email.cc}
              </div>
            )}
            <div className="mt-3 bg-gray-100 p-3 rounded whitespace-pre-wrap">
              {email.body}
            </div>
            
            {email.has_attachment && (
              <div className="mt-3">
                <span className="bg-gray-200 text-gray-800 px-2 py-1 rounded text-xs font-medium">
                  Has Attachments
                </span>
                {email.attachment_names && (
                  <div className="text-sm mt-1">
                    {email.attachment_names}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };
  
  const renderSMS = (sms) => {
    const isExpanded = expanded[`sms-${sms.id}`];
    
    return (
      <div className="border rounded p-3 mb-2 bg-white">
        <div className="flex justify-between items-start">
          <div className="flex items-start">
            <input 
              type="checkbox" 
              className="form-checkbox h-4 w-4 mt-1 mr-2"
              checked={selections.sms.has(sms.id)}
              onChange={() => toggleSelection('sms', sms.id)}
              id={`sms-${sms.id}`}
            />
            <label className="cursor-pointer" htmlFor={`sms-${sms.id}`}>
              <div>
                <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                  sms.direction === 'incoming' ? 'bg-blue-100 text-blue-800' : 'bg-green-100 text-green-800'
                }`}>
                  {sms.direction === 'incoming' ? 'Received' : 'Sent'}
                </span>
                <span className="ml-2">{sms.text ? sms.text.substring(0, 50) + (sms.text.length > 50 ? '...' : '') : 'No Content'}</span>
              </div>
              <div className="text-gray-500 text-sm">
                {new Date(sms.timestamp).toLocaleString()} | {sms.sender_name || sms.chat_session || 'Unknown'}
              </div>
            </label>
          </div>
          <button 
            className="text-gray-500 hover:text-gray-700"
            onClick={() => toggleExpand('sms', sms.id)}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
        
        {isExpanded && (
          <div className="mt-3">
            <hr className="my-2" />
            <div className="mb-2">
              <strong>Sender:</strong> {sms.sender_name || 'Unknown'}
            </div>
            <div className="mb-2">
              <strong>Direction:</strong> {sms.direction || 'Unknown'}
            </div>
            <div className="mb-2">
              <strong>Chat Session:</strong> {sms.chat_session || 'Not specified'}
            </div>
            <div className="mt-3 bg-gray-100 p-3 rounded whitespace-pre-wrap">
              {sms.text}
            </div>
            
            {sms.has_attachment && (
              <div className="mt-3">
                <span className="bg-gray-200 text-gray-800 px-2 py-1 rounded text-xs font-medium">
                  Has Attachment
                </span>
                {sms.attachment_type && (
                  <span className="ml-2 text-sm">{sms.attachment_type}</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };
  
  const renderDocket = (docket) => {
    const isExpanded = expanded[`docket_entries-${docket.id}`];
    
    return (
      <div className="border rounded p-3 mb-2 bg-white">
        <div className="flex justify-between items-start">
          <div className="flex items-start">
            <input 
              type="checkbox" 
              className="form-checkbox h-4 w-4 mt-1 mr-2"
              checked={selections.docket_entries.has(docket.id)}
              onChange={() => toggleSelection('docket_entries', docket.id)}
              id={`docket-${docket.id}`}
            />
            <label className="cursor-pointer" htmlFor={`docket-${docket.id}`}>
              <div className="font-medium">{docket.event_type || 'Docket Entry'}</div>
              <div className="text-gray-500 text-sm">
                {new Date(docket.timestamp).toLocaleString()} | Filed by: {docket.filed_by || 'Unknown'}
              </div>
            </label>
          </div>
          <button 
            className="text-gray-500 hover:text-gray-700"
            onClick={() => toggleExpand('docket_entries', docket.id)}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
        
        {isExpanded && (
          <div className="mt-3">
            <hr className="my-2" />
            <div className="mb-2">
              <strong>Event Type:</strong> {docket.event_type || 'Not specified'}
            </div>
            <div className="mb-2">
              <strong>Filed By:</strong> {docket.filed_by || 'Not specified'}
            </div>
            <div className="mt-3 bg-gray-100 p-3 rounded whitespace-pre-wrap">
              {docket.memo || 'No additional information available'}
            </div>
          </div>
        )}
      </div>
    );
  };
  
  const renderPhoneCall = (call) => {
    const isExpanded = expanded[`phone_calls-${call.id}`];
    const durationMins = call.duration_seconds ? Math.floor(call.duration_seconds / 60) : 0;
    const durationSecs = call.duration_seconds ? call.duration_seconds % 60 : 0;
    
    return (
      <div className="border rounded p-3 mb-2 bg-white">
        <div className="flex justify-between items-start">
          <div className="flex items-start">
            <input 
              type="checkbox" 
              className="form-checkbox h-4 w-4 mt-1 mr-2"
              checked={selections.phone_calls.has(call.id)}
              onChange={() => toggleSelection('phone_calls', call.id)}
              id={`call-${call.id}`}
            />
            <label className="cursor-pointer" htmlFor={`call-${call.id}`}>
              <div className="font-medium">{call.contact || call.number || 'Unknown Contact'}</div>
              <div className="text-gray-500 text-sm">
                {new Date(call.timestamp).toLocaleString()} | {call.call_type || 'Call'} | 
                Duration: {durationMins}:{durationSecs.toString().padStart(2, '0')}
              </div>
            </label>
          </div>
          <button 
            className="text-gray-500 hover:text-gray-700"
            onClick={() => toggleExpand('phone_calls', call.id)}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
        
        {isExpanded && (
          <div className="mt-3">
            <hr className="my-2" />
            <div className="mb-2">
              <strong>Contact:</strong> {call.contact || 'Not specified'}
            </div>
            <div className="mb-2">
              <strong>Number:</strong> {call.number || 'Not available'}
            </div>
            <div className="mb-2">
              <strong>Call Type:</strong> {call.call_type || 'Not specified'}
            </div>
            <div className="mb-2">
              <strong>Duration:</strong> {durationMins}:{durationSecs.toString().padStart(2, '0')}
            </div>
            <div className="mb-2">
              <strong>Service:</strong> {call.service || 'Not specified'}
            </div>
          </div>
        )}
      </div>
    );
  };
  
  const renderTimeEntry = (entry) => {
    const isExpanded = expanded[`time_entries-${entry.id}`];
    
    return (
      <div className="border rounded p-3 mb-2 bg-white">
        <div className="flex justify-between items-start">
          <div className="flex items-start">
            <input 
              type="checkbox" 
              className="form-checkbox h-4 w-4 mt-1 mr-2"
              checked={selections.time_entries.has(entry.id)}
              onChange={() => toggleSelection('time_entries', entry.id)}
              id={`time-${entry.id}`}
            />
            <label className="cursor-pointer" htmlFor={`time-${entry.id}`}>
              <div className="font-medium">{entry.activity_category || entry.activity_description || 'Time Entry'}</div>
              <div className="text-gray-500 text-sm">
                {entry.date} | {entry.hours || entry.quantity || 0} hrs | ${entry.price || entry.billable || 0}
              </div>
            </label>
          </div>
          <button 
            className="text-gray-500 hover:text-gray-700"
            onClick={() => toggleExpand('time_entries', entry.id)}
          >
            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        </div>
        
        {isExpanded && (
          <div className="mt-3">
            <hr className="my-2" />
            <div className="mb-2">
              <strong>Activity:</strong> {entry.activity_category || entry.activity_description || 'Not specified'}
            </div>
            <div className="mb-2">
              <strong>Hours:</strong> {entry.hours || entry.quantity || 0}
            </div>
            <div className="mb-2">
              <strong>Rate:</strong> ${entry.rate || 0}/hr
            </div>
            <div className="mb-2">
              <strong>Total:</strong> ${entry.price || entry.billable || 0}
            </div>
            <div className="mt-3 bg-gray-100 p-3 rounded whitespace-pre-wrap">
              {entry.note || entry.description || 'No description available'}
            </div>
          </div>
        )}
      </div>
    );
  };
  
  // Count total selections
  const totalSelected = Object.values(selections).reduce(
    (total, selectionSet) => total + selectionSet.size, 
    0
  );
  
  return (
    <div className="evidence-viewer">
      {/* Master Date Range Selector */}
      <div className="bg-gray-100 p-4 mb-4 border rounded">
        <div className="flex flex-wrap justify-between items-center">
          <div className="w-full md:w-1/2 mb-4 md:mb-0">
            <h5 className="mb-3 flex items-center font-medium">
              <Calendar size={18} className="mr-2" />
              Master Date Range
            </h5>
            <div className="flex flex-wrap gap-2">
              <div className="w-full md:w-5/12">
                <div className="flex items-center">
                  <span className="bg-gray-200 text-gray-700 px-2 py-1 rounded-l text-sm">
                    From
                  </span>
                  <input
                    type="date"
                    name="start"
                    value={dateRange.start}
                    onChange={handleDateChange}
                    className="border border-gray-300 rounded-r py-1 px-2 w-full"
                  />
                </div>
              </div>
              <div className="w-full md:w-5/12">
                <div className="flex items-center">
                  <span className="bg-gray-200 text-gray-700 px-2 py-1 rounded-l text-sm">
                    To
                  </span>
                  <input
                    type="date"
                    name="end"
                    value={dateRange.end}
                    onChange={handleDateChange}
                    className="border border-gray-300 rounded-r py-1 px-2 w-full"
                  />
                </div>
              </div>
              <div className="w-full md:w-2/12">
                <button 
                  className="border border-gray-300 rounded px-3 py-1 hover:bg-gray-200 w-full"
                  onClick={() => setDateRange({ start: '', end: '' })}
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
          <div className="w-full md:w-1/2 flex justify-start md:justify-end">
            <button className="bg-blue-600 text-white px-3 py-2 rounded hover:bg-blue-700 mr-2">
              Export Selected ({totalSelected})
            </button>
            <button className="border border-blue-600 text-blue-600 px-3 py-2 rounded hover:bg-blue-50">
              Generate Time Entries
            </button>
          </div>
        </div>
      </div>
      
      {/* Evidence Tabs */}
      <div className="evidence-tabs mb-4">
        <div className="border-b">
          <ul className="flex flex-wrap -mb-px">
            <li className="mr-2">
              <button
                className={`inline-block p-4 ${activeTab === 'emails' 
                  ? 'border-b-2 border-blue-600 text-blue-600' 
                  : 'border-b-2 border-transparent hover:border-gray-300'}`}
                onClick={() => setActiveTab('emails')}
              >
                Emails ({filteredData.emails.length})
              </button>
            </li>
            <li className="mr-2">
              <button
                className={`inline-block p-4 ${activeTab === 'sms' 
                  ? 'border-b-2 border-blue-600 text-blue-600' 
                  : 'border-b-2 border-transparent hover:border-gray-300'}`}
                onClick={() => setActiveTab('sms')}
              >
                SMS ({filteredData.sms.length})
              </button>
            </li>
            <li className="mr-2">
              <button
                className={`inline-block p-4 ${activeTab === 'docket_entries' 
                  ? 'border-b-2 border-blue-600 text-blue-600' 
                  : 'border-b-2 border-transparent hover:border-gray-300'}`}
                onClick={() => setActiveTab('docket_entries')}
              >
                Docket ({filteredData.docket_entries.length})
              </button>
            </li>
            <li className="mr-2">
              <button
                className={`inline-block p-4 ${activeTab === 'phone_calls' 
                  ? 'border-b-2 border-blue-600 text-blue-600' 
                  : 'border-b-2 border-transparent hover:border-gray-300'}`}
                onClick={() => setActiveTab('phone_calls')}
              >
                Calls ({filteredData.phone_calls.length})
              </button>
            </li>
            <li>
              <button
                className={`inline-block p-4 ${activeTab === 'time_entries' 
                  ? 'border-b-2 border-blue-600 text-blue-600' 
                  : 'border-b-2 border-transparent hover:border-gray-300'}`}
                onClick={() => setActiveTab('time_entries')}
              >
                Time Entries ({filteredData.time_entries.length})
              </button>
            </li>
          </ul>
        </div>
        
        <div className="tab-content mt-4">
          {/* Emails Tab */}
          {activeTab === 'emails' && (
            <div>
              <div className="flex justify-between mb-3 items-center">
                <div className="flex items-center">
                  <input 
                    type="checkbox"
                    id="select-all-emails"
                    className="form-checkbox h-4 w-4 mr-2"
                    checked={selectAll.emails}
                    onChange={() => toggleSelectAll('emails')}
                  />
                  <label htmlFor="select-all-emails" className="cursor-pointer">
                    Select All Emails
                  </label>
                </div>
                <div>
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium">
                    {selections.emails.size} selected
                  </span>
                </div>
              </div>
              
              <div className="evidence-list">
                {filteredData.emails.length > 0 ? (
                  filteredData.emails.map(email => (
                    <div key={email.id}>
                      {renderEmail(email)}
                    </div>
                  ))
                ) : (
                  <div className="bg-blue-50 text-blue-800 p-4 rounded">
                    No emails found in the selected date range.
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* SMS Tab */}
          {activeTab === 'sms' && (
            <div>
              <div className="flex justify-between mb-3 items-center">
                <div className="flex items-center">
                  <input 
                    type="checkbox"
                    id="select-all-sms"
                    className="form-checkbox h-4 w-4 mr-2"
                    checked={selectAll.sms}
                    onChange={() => toggleSelectAll('sms')}
                  />
                  <label htmlFor="select-all-sms" className="cursor-pointer">
                    Select All SMS Messages
                  </label>
                </div>
                <div>
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium">
                    {selections.sms.size} selected
                  </span>
                </div>
              </div>
              
              <div className="evidence-list">
                {filteredData.sms.length > 0 ? (
                  filteredData.sms.map(sms => (
                    <div key={sms.id}>
                      {renderSMS(sms)}
                    </div>
                  ))
                ) : (
                  <div className="bg-blue-50 text-blue-800 p-4 rounded">
                    No SMS messages found in the selected date range.
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Docket Tab */}
          {activeTab === 'docket_entries' && (
            <div>
              <div className="flex justify-between mb-3 items-center">
                <div className="flex items-center">
                  <input 
                    type="checkbox"
                    id="select-all-docket"
                    className="form-checkbox h-4 w-4 mr-2"
                    checked={selectAll.docket_entries}
                    onChange={() => toggleSelectAll('docket_entries')}
                  />
                  <label htmlFor="select-all-docket" className="cursor-pointer">
                    Select All Docket Entries
                  </label>
                </div>
                <div>
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium">
                    {selections.docket_entries.size} selected
                  </span>
                </div>
              </div>
              
              <div className="evidence-list">
                {filteredData.docket_entries.length > 0 ? (
                  filteredData.docket_entries.map(docket => (
                    <div key={docket.id}>
                      {renderDocket(docket)}
                    </div>
                  ))
                ) : (
                  <div className="bg-blue-50 text-blue-800 p-4 rounded">
                    No docket entries found in the selected date range.
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Phone Calls Tab */}
          {activeTab === 'phone_calls' && (
            <div>
              <div className="flex justify-between mb-3 items-center">
                <div className="flex items-center">
                  <input 
                    type="checkbox"
                    id="select-all-calls"
                    className="form-checkbox h-4 w-4 mr-2"
                    checked={selectAll.phone_calls}
                    onChange={() => toggleSelectAll('phone_calls')}
                  />
                  <label htmlFor="select-all-calls" className="cursor-pointer">
                    Select All Phone Calls
                  </label>
                </div>
                <div>
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium">
                    {selections.phone_calls.size} selected
                  </span>
                </div>
              </div>
              
              <div className="evidence-list">
                {filteredData.phone_calls.length > 0 ? (
                  filteredData.phone_calls.map(call => (
                    <div key={call.id}>
                      {renderPhoneCall(call)}
                    </div>
                  ))
                ) : (
                  <div className="bg-blue-50 text-blue-800 p-4 rounded">
                    No phone calls found in the selected date range.
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Time Entries Tab */}
          {activeTab === 'time_entries' && (
            <div>
              <div className="flex justify-between mb-3 items-center">
                <div className="flex items-center">
                  <input 
                    type="checkbox"
                    id="select-all-time-entries"
                    className="form-checkbox h-4 w-4 mr-2"
                    checked={selectAll.time_entries}
                    onChange={() => toggleSelectAll('time_entries')}
                  />
                  <label htmlFor="select-all-time-entries" className="cursor-pointer">
                    Select All Time Entries
                  </label>
                </div>
                <div>
                  <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs font-medium">
                    {selections.time_entries.size} selected
                  </span>
                </div>
              </div>
              
              <div className="evidence-list">
                {filteredData.time_entries.length > 0 ? (
                  filteredData.time_entries.map(entry => (
                    <div key={entry.id}>
                      {renderTimeEntry(entry)}
                    </div>
                  ))
                ) : (
                  <div className="bg-blue-50 text-blue-800 p-4 rounded">
                    No time entries found in the selected date range.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default EvidenceViewer;