/**
 * Server-Sent Events client for streaming Kafka topic messages via the Vite execute plugin.
 * Auto-reconnects on connection drops with exponential backoff.
 */

export class KafkaSSEClient {
  /**
   * @param {string} topic - Kafka topic to subscribe to
   * @param {Object} handlers - Event handlers keyed by message type
   * @param {{fromBeginning?: boolean}} options
   */
  constructor(topic, handlers, options = {}) {
    this.topic = topic;
    this.handlers = handlers || {};
    this.options = options;
    this.eventSource = null;
    this.isConnected = false;
    this._closed = false;
    this._reconnectAttempts = 0;
    this._reconnectTimer = null;

    this.connect();
  }

  connect() {
    if (this._closed) return;

    const fromBeginning = this.options.fromBeginning ? '1' : '0';
    const url = `/api/kafka/stream?topic=${encodeURIComponent(this.topic)}&fromBeginning=${fromBeginning}`;

    this.eventSource = new EventSource(url);

    this.eventSource.onopen = () => {
      this.isConnected = true;
      this._reconnectAttempts = 0;
      if (this.handlers.connected) this.handlers.connected();
    };

    this.eventSource.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        const handler = this.handlers[message.type];

        if (handler) handler(message);
        else if (this.handlers.default) this.handlers.default(message);
      } catch (error) {
        if (this.handlers.error) {
          this.handlers.error({ type: 'kafka_error', message: `Parse error: ${error.message}`, data: event.data });
        }
      }
    };

    this.eventSource.onerror = () => {
      this.isConnected = false;
      // Don't permanently close — reconnect with backoff
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
      if (!this._closed) {
        const backoffMs = Math.min(1000 * Math.pow(2, this._reconnectAttempts), 10000);
        this._reconnectAttempts++;
        console.log(`Kafka SSE disconnected (topic: ${this.topic}), reconnecting in ${backoffMs}ms...`);
        this._reconnectTimer = setTimeout(() => this.connect(), backoffMs);
      }
    };
  }

  close() {
    this._closed = true;
    clearTimeout(this._reconnectTimer);
    if (!this.eventSource) return;
    this.eventSource.close();
    this.eventSource = null;
    this.isConnected = false;
  }
}

