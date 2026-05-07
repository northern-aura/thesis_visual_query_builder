/**
 * Backend API client for script execution and management.
 */

const API_BASE = '/api';

export const backendClient = {
  /**
   * Execute a Python script.
   * @param {string} scriptName - Name of the script
   * @param {string} scriptContent - Python script content
   * @param {string} projectName - Project name
   * @returns {Promise<Object>} Execution response with execution_id and stream_url
   */
  async executeScript(scriptName, scriptContent, projectName, options = {}) {
    const response = await fetch(`${API_BASE}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        script_name: scriptName,
        script_content: scriptContent,
        project_name: projectName,
        auto_start_docker: true,
        ...options
      })
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || 'Failed to start execution');
    }

    return response.json();
  },

  /**
   * Get list of executions.
   * @param {number} limit - Maximum number of executions to return
   * @param {string} status - Filter by status (all|completed|failed|running)
   * @returns {Promise<Object>} List of executions
   */
  async getExecutions(limit = 50, status = 'all') {
    const response = await fetch(
      `${API_BASE}/executions?limit=${limit}&status=${status}`
    );

    if (!response.ok) {
      throw new Error('Failed to fetch executions');
    }

    return response.json();
  },

  /**
   * Get execution details.
   * @param {string} executionId - Execution ID
   * @returns {Promise<Object>} Execution details
   */
  async getExecutionDetails(executionId) {
    const response = await fetch(`${API_BASE}/executions/${executionId}`);

    if (!response.ok) {
      throw new Error('Failed to fetch execution details');
    }

    return response.json();
  },

  /**
   * Get execution logs.
   * @param {string} executionId - Execution ID
   * @returns {Promise<Object>} Execution logs
   */
  async getExecutionLogs(executionId) {
    const response = await fetch(`${API_BASE}/executions/${executionId}/logs`);

    if (!response.ok) {
      throw new Error('Failed to fetch execution logs');
    }

    return response.json();
  },

  /**
   * Stop a running execution.
   * @param {string} executionId - Execution ID
   * @returns {Promise<Object>} Stop confirmation
   */
  async stopExecution(executionId) {
    const response = await fetch(`${API_BASE}/executions/${executionId}`, {
      method: 'DELETE'
    });

    if (!response.ok) {
      throw new Error('Failed to stop execution');
    }

    return response.json();
  },

  /**
   * Get Docker containers status.
   * @returns {Promise<Object>} Docker status
   */
  async getDockerStatus() {
    const response = await fetch(`${API_BASE}/docker/status`);

    if (!response.ok) {
      throw new Error('Failed to fetch Docker status');
    }

    return response.json();
  },

  /**
   * Start Docker containers.
   * @returns {Promise<Object>} Start result
   */
  async startDockerContainers() {
    const response = await fetch(`${API_BASE}/docker/start`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error('Failed to start Docker containers');
    }

    return response.json();
  },

  async saveResults(filename, data) {
    const response = await fetch(`${API_BASE}/results/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, data })
    });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Failed to save results');
    }
    return response.json();
  },

  appendResult(filename, line, clear = false) {
    // Fire-and-forget — don't block the message handler
    fetch(`${API_BASE}/results/append`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, line, clear })
    }).catch(() => {});
  },

  // Broker-authoritative count of messages currently on `topic`. Doesn't depend on
  // any consumer subscription, so it's the right signal when the SSE stream is flaky.
  async getTopicOffset(topic) {
    const response = await fetch(`${API_BASE}/kafka/offset?topic=${encodeURIComponent(topic)}`);
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Failed to get topic offset');
    }
    return response.json();
  },

  async clearTopic(topic) {
    const response = await fetch(`${API_BASE}/kafka/clear-topic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic })
    });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Failed to clear topic');
    }
    return response.json();
  },

  async saveMetrics(filename, csvRow, detailData) {
    const response = await fetch(`${API_BASE}/metrics/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, csvRow, detailData })
    });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Failed to save metrics');
    }
    return response.json();
  },

  async runSender({ script, cwd } = {}) {
    const response = await fetch(`${API_BASE}/sender/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ script, cwd })
    });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Failed to run sender');
    }
    return response.json();
  },

  async renderPlots(slug) {
    const response = await fetch(`${API_BASE}/plots/render`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug })
    });
    if (!response.ok) {
      const err = await response.text();
      throw new Error(err || 'Failed to render plots');
    }
    return response.json();
  }
};
