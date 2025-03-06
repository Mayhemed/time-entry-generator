// static/js/testApp.js
const { useState, useEffect } = React;

const TestApp = () => {
  const [apiTest, setApiTest] = useState(null);
  const [evidenceTest, setEvidenceTest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    // Test both endpoints
    Promise.all([
      fetch('/api/test').then(res => res.json()),
      fetch('/api/evidence-json/all').then(res => res.json())
    ])
    .then(([testData, evidenceData]) => {
      setApiTest(testData);
      setEvidenceTest(evidenceData);
      setLoading(false);
    })
    .catch(err => {
      console.error("API Error:", err);
      setError(err.toString());
      setLoading(false);
    });
  }, []);
  
  if (loading) {
    return <div>Testing API endpoints...</div>;
  }
  
  if (error) {
    return <div className="alert alert-danger">Error: {error}</div>;
  }
  
  return (
    <div className="p-4">
      <h2>API Connectivity Test</h2>
      
      <div className="card mb-4">
        <div className="card-header">/api/test Endpoint</div>
        <div className="card-body">
          <pre>{JSON.stringify(apiTest, null, 2)}</pre>
        </div>
      </div>
      
      <div className="card">
        <div className="card-header">/api/evidence-json/all Endpoint</div>
        <div className="card-body">
          <pre>{JSON.stringify(evidenceTest, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
};

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
  ReactDOM.render(<TestApp />, document.getElementById('react-app'));
});