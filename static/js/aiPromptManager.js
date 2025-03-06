import React, { useState, useEffect } from 'react';
import { Save, Plus, Edit, Trash, PlayCircle, ChevronDown, ChevronUp } from 'lucide-react';

const AiPromptManager = ({ onSubmitPrompt, initialPrompts = [] }) => {
  // State for prompts
  const [savedPrompts, setSavedPrompts] = useState(initialPrompts);
  const [activePrompt, setActivePrompt] = useState(null);
  const [currentPrompt, setCurrentPrompt] = useState({
    id: '',
    name: '',
    template: '',
    systemPrompt: '',
    description: '',
    goal: 'time_entries',
    tags: []
  });
  const [editMode, setEditMode] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Goals options
  const goalOptions = [
    { value: 'time_entries', label: 'Generate Time Entries' },
    { value: 'project_timeline', label: 'Extract Project Timeline' },
    { value: 'evidence_summary', label: 'Summarize Evidence' },
    { value: 'key_themes', label: 'Identify Key Themes' },
    { value: 'case_narrative', label: 'Create Case Narrative' },
    { value: 'custom', label: 'Custom Output' }
  ];

  // Handle form changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setCurrentPrompt(prev => ({
      ...prev,
      [name]: value
    }));
  };

  // Load a saved prompt
  const loadPrompt = (promptId) => {
    const prompt = savedPrompts.find(p => p.id === promptId);
    if (prompt) {
      setCurrentPrompt(prompt);
      setActivePrompt(promptId);
      setEditMode(false);
    }
  };

  // Create a new prompt
  const createNewPrompt = () => {
    const newPrompt = {
      id: `prompt_${Date.now()}`,
      name: 'New Prompt',
      template: '',
      systemPrompt: 'You are a helpful assistant tasked with analyzing legal evidence and generating structured output.',
      description: '',
      goal: 'time_entries',
      tags: []
    };
    setCurrentPrompt(newPrompt);
    setActivePrompt(null);
    setEditMode(true);
  };

  // Save the current prompt
  const savePrompt = () => {
    // Validate the prompt
    if (!currentPrompt.name || !currentPrompt.template) {
      alert('Please provide a name and prompt template');
      return;
    }

    const updatedPrompts = [...savedPrompts];
    const existingIndex = updatedPrompts.findIndex(p => p.id === currentPrompt.id);

    if (existingIndex >= 0) {
      // Update existing prompt
      updatedPrompts[existingIndex] = currentPrompt;
    } else {
      // Add new prompt
      updatedPrompts.push(currentPrompt);
    }

    setSavedPrompts(updatedPrompts);
    setActivePrompt(currentPrompt.id);
    setEditMode(false);

    // Save to localStorage or backend
    localStorage.setItem('aiPrompts', JSON.stringify(updatedPrompts));
  };

  // Delete a prompt
  const deletePrompt = (promptId) => {
    if (confirm('Are you sure you want to delete this prompt?')) {
      const updatedPrompts = savedPrompts.filter(p => p.id !== promptId);
      setSavedPrompts(updatedPrompts);
      
      if (activePrompt === promptId) {
        setActivePrompt(null);
        setCurrentPrompt({
          id: '',
          name: '',
          template: '',
          systemPrompt: '',
          description: '',
          goal: 'time_entries',
          tags: []
        });
      }

      // Save to localStorage or backend
      localStorage.setItem('aiPrompts', JSON.stringify(updatedPrompts));
    }
  };

  // Run the current prompt
  const runPrompt = () => {
    if (onSubmitPrompt) {
      onSubmitPrompt(currentPrompt);
    }
  };

  // Load saved prompts from localStorage on component mount
  useEffect(() => {
    const storedPrompts = localStorage.getItem('aiPrompts');
    if (storedPrompts) {
      try {
        const parsedPrompts = JSON.parse(storedPrompts);
        setSavedPrompts(parsedPrompts);
        
        // If prompts exist and none is active, set the first one active
        if (parsedPrompts.length > 0 && !activePrompt) {
          setActivePrompt(parsedPrompts[0].id);
          setCurrentPrompt(parsedPrompts[0]);
        }
      } catch (error) {
        console.error('Error parsing saved prompts:', error);
      }
    }
  }, []);

  return (
    <div className="ai-prompt-manager p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold">AI Prompt Manager</h2>
        <div className="space-x-2">
          <button 
            className="bg-blue-600 text-white px-3 py-2 rounded hover:bg-blue-700 flex items-center"
            onClick={createNewPrompt}
          >
            <Plus size={16} className="mr-1" />
            New Prompt
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Saved Prompts Sidebar */}
        <div className="bg-gray-50 border rounded p-4">
          <h3 className="font-medium mb-3">Saved Prompts</h3>
          {savedPrompts.length > 0 ? (
            <ul className="space-y-2">
              {savedPrompts.map(prompt => (
                <li 
                  key={prompt.id} 
                  className={`p-2 rounded cursor-pointer border ${
                    activePrompt === prompt.id ? 'bg-blue-50 border-blue-300' : 'hover:bg-gray-100 border-gray-200'
                  }`}
                  onClick={() => loadPrompt(prompt.id)}
                >
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-medium">{prompt.name}</div>
                      <div className="text-xs text-gray-500">
                        {goalOptions.find(g => g.value === prompt.goal)?.label || 'Custom Goal'}
                      </div>
                    </div>
                    <div className="flex space-x-1">
                      <button 
                        className="text-gray-400 hover:text-blue-600" 
                        onClick={(e) => {
                          e.stopPropagation();
                          loadPrompt(prompt.id);
                          setEditMode(true);
                        }}
                      >
                        <Edit size={14} />
                      </button>
                      <button 
                        className="text-gray-400 hover:text-red-600" 
                        onClick={(e) => {
                          e.stopPropagation();
                          deletePrompt(prompt.id);
                        }}
                      >
                        <Trash size={14} />
                      </button>
                    </div>
                  </div>
                  {prompt.description && (
                    <div className="text-sm text-gray-600 mt-1">{prompt.description}</div>
                  )}
                  {prompt.tags && prompt.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {prompt.tags.map(tag => (
                        <span 
                          key={tag} 
                          className="bg-gray-200 text-gray-700 px-2 py-0.5 rounded-full text-xs"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <div className="text-gray-500 text-center py-4">
              No saved prompts. Create one to get started.
            </div>
          )}
        </div>

        {/* Current Prompt Editor */}
        <div className="md:col-span-2 border rounded p-4">
          {editMode ? (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prompt Name
                </label>
                <input 
                  type="text"
                  name="name"
                  value={currentPrompt.name}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter prompt name..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <input 
                  type="text"
                  name="description"
                  value={currentPrompt.description}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="What does this prompt do?"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Goal
                </label>
                <select 
                  name="goal"
                  value={currentPrompt.goal}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {goalOptions.map(option => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prompt Template
                </label>
                <textarea 
                  name="template"
                  value={currentPrompt.template}
                  onChange={handleChange}
                  className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter your prompt template... Use {start_date} and {end_date} as placeholders for dynamic values."
                  rows={8}
                />
              </div>
              
              <div>
                <button 
                  className="flex items-center text-gray-700 hover:text-gray-900 text-sm"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                >
                  {showAdvanced ? (
                    <>
                      <ChevronUp size={16} className="mr-1" />
                      Hide Advanced Options
                    </>
                  ) : (
                    <>
                      <ChevronDown size={16} className="mr-1" />
                      Show Advanced Options
                    </>
                  )}
                </button>
                
                {showAdvanced && (
                  <div className="mt-3 space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        System Prompt
                      </label>
                      <textarea 
                        name="systemPrompt"
                        value={currentPrompt.systemPrompt}
                        onChange={handleChange}
                        className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="Enter system prompt for the AI..."
                        rows={4}
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Tags (comma separated)
                      </label>
                      <input 
                        type="text"
                        name="tags"
                        value={currentPrompt.tags.join(', ')}
                        onChange={(e) => {
                          const tagsString = e.target.value;
                          const tagsArray = tagsString.split(',').map(tag => tag.trim()).filter(Boolean);
                          setCurrentPrompt(prev => ({
                            ...prev,
                            tags: tagsArray
                          }));
                        }}
                        className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="time entries, legal, billing..."
                      />
                    </div>
                  </div>
                )}
              </div>
              
              <div className="flex justify-end space-x-2 pt-2">
                <button 
                  className="border border-gray-300 rounded px-4 py-2 hover:bg-gray-100"
                  onClick={() => {
                    if (activePrompt) {
                      loadPrompt(activePrompt);
                    } else {
                      setCurrentPrompt({
                        id: '',
                        name: '',
                        template: '',
                        systemPrompt: '',
                        description: '',
                        goal: 'time_entries',
                        tags: []
                      });
                    }
                    setEditMode(false);
                  }}
                >
                  Cancel
                </button>
                <button 
                  className="bg-blue-600 text-white rounded px-4 py-2 hover:bg-blue-700 flex items-center"
                  onClick={savePrompt}
                >
                  <Save size={16} className="mr-1" />
                  Save Prompt
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {currentPrompt.id ? (
                <>
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-medium">{currentPrompt.name}</h3>
                      {currentPrompt.description && (
                        <p className="text-gray-600 mt-1">{currentPrompt.description}</p>
                      )}
                      <div className="text-sm text-gray-500 mt-2">
                        Goal: {goalOptions.find(g => g.value === currentPrompt.goal)?.label || 'Custom Goal'}
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button 
                        className="border border-gray-300 rounded p-2 hover:bg-gray-100"
                        onClick={() => setEditMode(true)}
                      >
                        <Edit size={16} />
                      </button>
                    </div>
                  </div>
                  
                  <div className="mt-4">
                    <h4 className="font-medium mb-2">Prompt Template</h4>
                    <div className="bg-gray-50 p-3 rounded-md border whitespace-pre-wrap">
                      {currentPrompt.template}
                    </div>
                  </div>
                  
                  <div className="pt-4">
                    <button 
                      className="bg-green-600 text-white rounded px-4 py-2 hover:bg-green-700 flex items-center"
                      onClick={runPrompt}
                    >
                      <PlayCircle size={16} className="mr-1" />
                      Run Prompt
                    </button>
                  </div>
                </>
              ) : (
                <div className="text-center py-8">
                  <p className="text-gray-500 mb-4">
                    Select a prompt from the sidebar or create a new one.
                  </p>
                  <button 
                    className="bg-blue-600 text-white px-3 py-2 rounded hover:bg-blue-700 flex items-center mx-auto"
                    onClick={createNewPrompt}
                  >
                    <Plus size={16} className="mr-1" />
                    Create New Prompt
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AiPromptManager;