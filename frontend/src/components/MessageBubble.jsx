import React, { useState } from 'react';
import { Bot } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';

const MessageBubble = ({ msg, idx, onExecute, globalLoading }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [localLoading, setLocalLoading] = useState(false);

  const handleExecute = async () => {
    setLocalLoading(true);
    await onExecute(idx);
    setLocalLoading(false);
  };

  const toggleDetails = () => {
    setIsExpanded(!isExpanded);
  };

  const isAssistant = msg.role === 'assistant';
  const showApproval = isAssistant && ['pending_approval', 'error'].includes(msg.status);
  const isExecuting = msg.status === 'executing';

  return (
    <div className={`message-wrapper ${msg.role}`}>
      <div className={`message-bubble ${msg.role}`}>
        <div className="message-header">
          {msg.role === 'user' ? 'You' : 'Koala'}
        </div>
        <div className="message-content">
          <MarkdownRenderer content={msg.content} />
        </div>
        
        {msg.subtasks && msg.subtasks.length > 0 && (
          <div className="orchestration-section">
            <button 
              className="details-toggle-btn"
              onClick={toggleDetails}
            >
              {isExpanded ? 'Hide Orchestration Details' : 'Show Orchestration Details'}
            </button>
            
            {isExpanded && (
              <div className="subtasks-container animate-in">
                <div className="subtasks-label">
                  {msg.status === 'pending_approval' ? 'Proposed Execution Plan:' : 'Orchestration Workflow:'}
                </div>
                {msg.subtasks.map((task, tidx) => (
                  <div key={tidx} className={`subtask-card ${task.result ? 'completed' : ''}`}>
                    <div className="subtask-card-header">
                      <span className={`status-dot ${task.result ? 'done' : (msg.status === 'executing' ? 'active' : 'idle')}`}></span>
                      <strong>Step {task.id}</strong>
                      <span className={`model-tag ${task.assigned_model.includes('3.3') ? 'expert' : 'advanced'}`}>
                        {task.assigned_model}
                      </span>
                    </div>
                    <div className="subtask-desc">{task.description}</div>
                    {task.result && (
                      <div className="subtask-result animate-in">
                        <div className="result-label">Subtask Output:</div>
                        <div className="result-text">
                          <MarkdownRenderer content={task.result} />
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {showApproval && (
          <div className="plan-approval-actions">
            <button 
              className="execute-btn" 
              onClick={handleExecute}
              disabled={globalLoading || localLoading}
            >
              {localLoading ? 'Wait...' : 'Confirm & Execute Orchestration'}
            </button>
            <div className="refine-tip">
              Or type your feedback below to refine this plan...
            </div>
          </div>
        )}

        {isExecuting && (
          <div className="distributing-status">
            <div className="pulse-loader"></div>
            Agents are distributed and working on subtasks...
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
