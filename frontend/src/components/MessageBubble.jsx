import React, { useState } from 'react';
import { Bot, ArrowRight } from 'lucide-react';
import MarkdownRenderer from './MarkdownRenderer';

const MessageBubble = ({ msg, idx, onExecute, globalLoading, onShowDetails }) => {
  const isAssistant = msg.role === 'assistant';
  const isPendingApproval = isAssistant && msg.status === 'pending_approval';
  const isExecuting = isAssistant && msg.status === 'executing';
  const isCompleted = isAssistant && msg.status === 'completed';
  const isError = isAssistant && msg.status === 'error';

  const handleExecute = () => onExecute(idx);

  return (
    <div className={`message-wrapper ${msg.role}`}>
      <div className={`message-bubble ${msg.role}`}>
        <div className="message-header">
          {msg.role === 'user' ? 'You' : 'Koala'}
        </div>
        
        {/* Render content: only if not currently executing, or if it has actual text to show */}
        {(!isExecuting || msg.isSynthesizing) && msg.content && (
          <div className="message-content">
            <MarkdownRenderer content={msg.content} />
          </div>
        )}

        {/* 1. Subtask Verification Step (Pending Approval): stays in the main chat window */}
        {isPendingApproval && msg.subtasks && msg.subtasks.length > 0 && (
          <div className="orchestration-section animate-in">
            <div className="subtasks-container" style={{ borderTop: 'none', marginTop: '0.5rem', paddingTop: 0 }}>
              <div className="subtasks-label">Proposed Execution Plan (Verification Required):</div>
              {msg.subtasks.map((task, tidx) => (
                <div key={tidx} className="subtask-card">
                  <div className="subtask-card-header">
                    <span className="status-dot idle"></span>
                    <strong>Step {task.id}</strong>
                    <span className={`model-tag ${task.assigned_model.includes('3.3') || task.assigned_model.includes('120b') ? 'expert' : 'advanced'}`}>
                      {task.assigned_model}
                    </span>
                  </div>
                  <div className="subtask-desc">{task.description}</div>
                </div>
              ))}
            </div>

            <div className="plan-approval-actions">
              <button 
                className="execute-btn" 
                onClick={handleExecute}
                disabled={globalLoading}
              >
                Confirm & Execute Orchestration
              </button>
              <div className="refine-tip">
                Or type your feedback below to refine this plan...
              </div>
            </div>
          </div>
        )}

        {/* 2. Subtasks Executing Step: Show executing banner in main chat window with a "Show details" button */}
        {isExecuting && (
          <div className="orchestration-section animate-in">
            <div className="main-chat-executing-box">
              <div className="distributing-status" style={{ marginTop: 0 }}>
                <div className="pulse-loader"></div>
                {msg.isSynthesizing 
                  ? 'Synthesizing and formatting final output...' 
                  : 'Orchestrator subtasks are being executed...'}
              </div>
              <button 
                className="show-details-link-btn"
                onClick={() => onShowDetails(idx)}
                type="button"
              >
                Show details <ArrowRight size={14} style={{ marginLeft: '2px' }} />
              </button>
            </div>
          </div>
        )}

        {/* 3. Completed or Error Step with subtasks: show link to view execution dashboard in sidebar */}
        {(isCompleted || isError) && msg.subtasks && msg.subtasks.length > 0 && (
          <div className="orchestration-section animate-in" style={{ marginTop: '0.5rem' }}>
            <button 
              className="show-details-link-btn"
              onClick={() => onShowDetails(idx)}
              type="button"
            >
              Show execution workflow results <ArrowRight size={14} style={{ marginLeft: '2px' }} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageBubble;
