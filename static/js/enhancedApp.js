// static/js/enhancedApp.js
// This file contains all the components without using imports/exports

// Get React hooks from global React object
const { useState, useEffect } = React;

// Simple demo component to verify React is working
const EnhancedUI = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedTab, setSelectedTab] = useState('emails');
  
  // Fetch evidence data when component mounts
  useEffect(() => {
    console.log("Fetching evidence data...");
    fetch('/api/evidence-json/all')
      .then(response => {
        if (!response.ok) {
          throw new Error('Failed to fetch evidence data: ' + response.statusText);
        }
        return response.json();
      })
      .then(data => {
        console.log("Evidence data received:", data);
        setData(data);
        setLoading(false);
      })
      .catch(error => {
        console.error("Error fetching data:", error);
        setError(error.toString());
        setLoading(false);
      });
  }, []);

  // Show loading state
  if (loading) {
    return (
      <div className="text-center p-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading data...</span>
        </div>
        <p className="mt-3">Loading evidence data...</p>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="alert alert-danger">
        <h4>Error Loading Data</h4>
        <p>{error}</p>
        <button className="btn btn-primary mt-2" onClick={() => window.location.reload()}>
          Retry
        </button>
      </div>
    );
  }

  // If we have no data but no error/loading either
  if (!data) {
    return (
      <div className="alert alert-warning">
        <h4>No Evidence Data Available</h4>
        <p>No evidence data was found. Please upload evidence first.</p>
        <a href="/upload" className="btn btn-primary mt-2">
          Upload Evidence
        </a>
      </div>
    );
  }

  // Count items in each category
  const counts = {
    emails: data.emails?.length || 0,
    sms: data.sms?.length || 0,
    docket_entries: data.docket_entries?.length || 0,
    phone_calls: data.phone_calls?.length || 0,
    time_entries: data.time_entries?.length || 0,
  };

  return (
    <div className="container-fluid">
      <div className="alert alert-success mb-4">
        <h4>Enhanced UI is working!</h4>
        <p>This basic version confirms that React is loading correctly with your data.</p>
      </div>

      {/* Evidence Summary */}
      <div className="row mb-4">
        <div className="col-md-12">
          <div className="card">
            <div className="card-header">Evidence Summary</div>
            <div className="card-body">
              <div className="row">
                <div className="col-md-2">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <h5 className="card-title">Emails</h5>
                      <h2>{counts.emails}</h2>
                    </div>
                  </div>
                </div>
                <div className="col-md-2">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <h5 className="card-title">SMS</h5>
                      <h2>{counts.sms}</h2>
                    </div>
                  </div>
                </div>
                <div className="col-md-2">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <h5 className="card-title">Docket</h5>
                      <h2>{counts.docket_entries}</h2>
                    </div>
                  </div>
                </div>
                <div className="col-md-2">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <h5 className="card-title">Calls</h5>
                      <h2>{counts.phone_calls}</h2>
                    </div>
                  </div>
                </div>
                <div className="col-md-2">
                  <div className="card bg-light">
                    <div className="card-body text-center">
                      <h5 className="card-title">Time Entries</h5>
                      <h2>{counts.time_entries}</h2>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs for evidence types */}
      <div className="mb-4">
        <ul className="nav nav-tabs">
          <li className="nav-item">
            <button 
              className={`nav-link ${selectedTab === 'emails' ? 'active' : ''}`}
              onClick={() => setSelectedTab('emails')}
            >
              Emails ({counts.emails})
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${selectedTab === 'sms' ? 'active' : ''}`}
              onClick={() => setSelectedTab('sms')}
            >
              SMS ({counts.sms})
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${selectedTab === 'docket' ? 'active' : ''}`}
              onClick={() => setSelectedTab('docket')}
            >
              Docket ({counts.docket_entries})
            </button>
          </li>
          <li className="nav-item">
            <button 
              className={`nav-link ${selectedTab === 'calls' ? 'active' : ''}`}
              onClick={() => setSelectedTab('calls')}
            >
              Calls ({counts.phone_calls})
            </button>
          </li>
        </ul>
        
        <div className="tab-content border border-top-0 rounded-bottom p-3">
          {/* Email Tab */}
          {selectedTab === 'emails' && (
            <div>
              <h3>Emails</h3>
              {data.emails && data.emails.length > 0 ? (
                data.emails.slice(0, 5).map(email => (
                  <div key={email.id} className="card mb-2">
                    <div className="card-body">
                      <h5 className="card-title">{email.subject || 'No Subject'}</h5>
                      <h6 className="card-subtitle mb-2 text-muted">
                        From: {email.from || 'Unknown'} | To: {email.to || 'Unknown'}
                      </h6>
                      <p className="card-text">{email.body ? email.body.substring(0, 200) + '...' : 'No content'}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="alert alert-info">No emails found.</div>
              )}
              {data.emails && data.emails.length > 5 && (
                <button className="btn btn-sm btn-outline-primary">
                  Show all {data.emails.length} emails
                </button>
              )}
            </div>
          )}
          
          {/* SMS Tab */}
          {selectedTab === 'sms' && (
            <div>
              <h3>SMS Messages</h3>
              {data.sms && data.sms.length > 0 ? (
                data.sms.slice(0, 5).map(sms => (
                  <div key={sms.id} className="card mb-2">
                    <div className="card-body">
                      <h5 className="card-title">{sms.sender_name || 'Unknown Sender'}</h5>
                      <p className="card-text">{sms.text || 'No content'}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="alert alert-info">No SMS messages found.</div>
              )}
            </div>
          )}
          
          {/* Docket Tab */}
          {selectedTab === 'docket' && (
            <div>
              <h3>Docket Entries</h3>
              {data.docket_entries && data.docket_entries.length > 0 ? (
                data.docket_entries.slice(0, 5).map(docket => (
                  <div key={docket.id} className="card mb-2">
                    <div className="card-body">
                      <h5 className="card-title">{docket.event_type || 'Unknown Event'}</h5>
                      <h6 className="card-subtitle mb-2 text-muted">
                        Filed by: {docket.filed_by || 'Unknown'}
                      </h6>
                      <p className="card-text">{docket.memo || 'No details'}</p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="alert alert-info">No docket entries found.</div>
              )}
            </div>
          )}
          
          {/* Calls Tab */}
          {selectedTab === 'calls' && (
            <div>
              <h3>Phone Calls</h3>
              {data.phone_calls && data.phone_calls.length > 0 ? (
                data.phone_calls.slice(0, 5).map(call => (
                  <div key={call.id} className="card mb-2">
                    <div className="card-body">
                      <h5 className="card-title">{call.contact || call.number || 'Unknown'}</h5>
                      <h6 className="card-subtitle mb-2 text-muted">
                        Duration: {Math.floor((call.duration_seconds || 0) / 60)} min
                      </h6>
                      <p className="card-text">
                        Call Type: {call.call_type || 'Unknown'}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <div className="alert alert-info">No phone calls found.</div>
              )}
            </div>
          )}
        </div>
      </div>
      
      <div className="row mt-4">
        <div className="col-md-12">
          <div className="card">
            <div className="card-header">Coming Soon</div>
            <div className="card-body">
              <p>
                The full enhanced UI with evidence selection, AI prompt management, and
                advanced visualizations will be available soon.
              </p>
              <p>
                This basic version confirms that your backend connection is working correctly.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// Initialize the app when the document is ready
document.addEventListener('DOMContentLoaded', function() {
  const appContainer = document.getElementById('react-app');
  if (appContainer) {
    ReactDOM.render(<EnhancedUI />, appContainer);
  } else {
    console.error("Could not find app container element with ID 'react-app'");
  }
});