/**
 * Server-Sent Events client for real-time execution streaming.
 */

export class ExecutionSSEClient {
  /**
   * Create SSE client for execution streaming.
   * @param {string} executionId - Execution ID
   * @param {Object} handlers - Event handlers by message type
   */
  constructor(executionId, handlers) {
    this.executionId = executionId;
    this.handlers = handlers;
    this.eventSource = null;
    this.isConnected = false;

    this.connect();
  }

  connect() {
    // EventSource is built into browsers - no library needed
    this.eventSource = new EventSource(`/api/execute/${this.executionId}/stream`);

    this.eventSource.onopen = () => {
      console.log(`SSE connected for execution ${this.executionId}`);
      this.isConnected = true;

      if (this.handlers.connected) {
        this.handlers.connected();
      }
    };

    this.eventSource.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const handler = this.handlers[message.type];

        if (handler) {
          handler(message);
        } else if (this.handlers.default) {
          this.handlers.default(message);
        }
      } catch (error) {
        console.error('Error parsing SSE message:', error, event.data);

        if (this.handlers.error) {
          this.handlers.error({ message: `Parse error: ${error.message}` });
        }
      }
    };

    this.eventSource.onerror = (error) => {
      console.error('SSE connection error:', error);
      this.isConnected = false;

      if (this.handlers.error) {
        this.handlers.error({ message: 'Connection error' });
      }

      // EventSource automatically attempts to reconnect
      // Close it if we've had an error
      this.close();
    };
  }

  close() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
      this.isConnected = false;
      console.log(`SSE closed for execution ${this.executionId}`);
    }
  }

  getConnectionState() {
    if (!this.eventSource) return 'closed';

    switch (this.eventSource.readyState) {
      case EventSource.CONNECTING:
        return 'connecting';
      case EventSource.OPEN:
        return 'open';
      case EventSource.CLOSED:
        return 'closed';
      default:
        return 'unknown';
    }
  }
}
