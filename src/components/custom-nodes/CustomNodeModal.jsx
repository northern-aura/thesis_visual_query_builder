import React, { useState } from 'react';
import './CustomNodes.css';

const CustomNodeModal = ({ onSave, onClose }) => {
  const [formData, setFormData] = useState({
    label: '',
    icon: 'fa-code',
    color: '#3b82f6',
    params: '',
    pythonClass: '',
    method: 'process'
  });

  const handleSave = () => {
    if (!formData.label || !formData.pythonClass || !formData.method) {
      alert('Please fill in Label, Python Class, and Method fields');
      return;
    }

    // Parse params from textarea (format: id|name|label|type|textarea)
    const paramsArray = formData.params
      .split('\n')
      .filter(line => line.trim())
      .map(line => {
        const parts = line.split('|').map(p => p.trim());
        return {
          id: parts[0],
          name: parts[1],
          label: parts[2],
          type: parts[3] || 'text',
          isTextarea: parts[4] === 'textarea'
        };
      });

    const newNode = {
      id: `custom-${Date.now()}`,
      label: formData.label,
      functionType: 'custom',
      icon: formData.icon,
      color: formData.color,
      params: paramsArray.length > 0 ? paramsArray : undefined,
      pythonClass: formData.pythonClass,
      method: formData.method,
      isCustom: true
    };

    onSave(newNode);

    // Reset form
    setFormData({
      label: '',
      icon: 'fa-code',
      color: '#3b82f6',
      params: '',
      pythonClass: '',
      method: 'process'
    });

    onClose();
  };

  return (
    <div className="custom-node-modal-overlay" onClick={onClose}>
      <div className="custom-node-modal" onClick={(e) => e.stopPropagation()}>
        <div className="custom-node-modal-header">
          <h2>Create Custom Node</h2>
          <button className="close-btn" onClick={onClose}>&times;</button>
        </div>

        <div className="custom-node-form-view">
          <div className="form-group">
            <label>Label *</label>
            <input
              type="text"
              value={formData.label}
              onChange={(e) => setFormData({ ...formData, label: e.target.value })}
              placeholder="e.g., Custom Filter"
            />
          </div>

          <div className="form-group">
            <label>Icon (FontAwesome class) *</label>
            <input
              type="text"
              value={formData.icon}
              onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
              placeholder="e.g., fa-filter, fa-star, fa-code"
            />
            <small>Preview: <i className={`fa ${formData.icon}`}></i></small>
          </div>

          <div className="form-group">
            <label>Color</label>
            <input
              type="color"
              value={formData.color}
              onChange={(e) => setFormData({ ...formData, color: e.target.value })}
            />
          </div>

          <div className="form-group">
            <label>Parameters (one per line: id|name|label|type|textarea)</label>
            <textarea
              value={formData.params}
              onChange={(e) => setFormData({ ...formData, params: e.target.value })}
              placeholder="Example:&#10;threshold|threshold|Threshold Value|number&#10;description|description|Description|text|textarea"
              rows="4"
            />
            <small>Format: id|name|label|type (add |textarea at end for textarea input)</small>
          </div>

          <div className="form-group">
            <label>Python Class Code *</label>
            <textarea
              value={formData.pythonClass}
              onChange={(e) => setFormData({ ...formData, pythonClass: e.target.value })}
              placeholder="class MyCustomNode:&#10;    def process(self, value):&#10;        # Your logic here&#10;        return value"
              rows="8"
            />
          </div>

          <div className="form-group">
            <label>Method Name *</label>
            <input
              type="text"
              value={formData.method}
              onChange={(e) => setFormData({ ...formData, method: e.target.value })}
              placeholder="e.g., process, transform, filter"
            />
            <small>The method to invoke in your Python class</small>
          </div>

          <div className="form-actions">
            <button
              className="save-btn"
              onClick={handleSave}
              disabled={!formData.label || !formData.pythonClass || !formData.method}
            >
              Create Custom Node
            </button>
            <button className="cancel-btn" onClick={onClose}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CustomNodeModal;
