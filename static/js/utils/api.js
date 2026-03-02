/**
 * AccreditAI - API Utilities
 *
 * Provides a simple wrapper for fetch API with error handling and SSE support.
 */

const API = {
  /**
   * Make an HTTP request.
   * @param {string} url - The URL to fetch
   * @param {Object} options - Fetch options
   * @returns {Promise<any>} - The response data
   */
  async request(url, options = {}) {
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json',
      },
    };

    const mergedOptions = {
      ...defaultOptions,
      ...options,
      headers: {
        ...defaultOptions.headers,
        ...options.headers,
      },
    };

    if (mergedOptions.body && typeof mergedOptions.body === 'object') {
      mergedOptions.body = JSON.stringify(mergedOptions.body);
    }

    try {
      const response = await fetch(url, mergedOptions);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error ${response.status}`);
      }

      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      }

      return await response.text();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  },

  /**
   * GET request.
   */
  get(url, options = {}) {
    return this.request(url, { ...options, method: 'GET' });
  },

  /**
   * POST request.
   */
  post(url, body, options = {}) {
    return this.request(url, { ...options, method: 'POST', body });
  },

  /**
   * PUT request.
   */
  put(url, body, options = {}) {
    return this.request(url, { ...options, method: 'PUT', body });
  },

  /**
   * DELETE request.
   */
  delete(url, options = {}) {
    return this.request(url, { ...options, method: 'DELETE' });
  },

  /**
   * Connect to an SSE stream.
   * @param {string} url - The SSE endpoint URL
   * @param {Object} handlers - Event handlers { onMessage, onError, onComplete }
   * @returns {EventSource} - The EventSource instance
   */
  connectSSE(url, handlers = {}) {
    const { onMessage, onError, onComplete } = handlers;

    const eventSource = new EventSource(url);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'stream_complete' || data.type === 'done') {
          eventSource.close();
          if (onComplete) onComplete(data);
          return;
        }

        if (data.type === 'error') {
          eventSource.close();
          if (onError) onError(new Error(data.error));
          return;
        }

        if (onMessage) onMessage(data);
      } catch (e) {
        console.error('Error parsing SSE data:', e);
      }
    };

    eventSource.onerror = (error) => {
      eventSource.close();
      if (onError) onError(error);
    };

    return eventSource;
  },

  /**
   * Stream a POST request via SSE.
   * @param {string} url - The SSE endpoint URL
   * @param {Object} body - The request body
   * @param {Object} handlers - Event handlers { onMessage, onError, onComplete }
   * @returns {Promise<void>}
   */
  async streamPost(url, body, handlers = {}) {
    const { onChunk, onMessage, onError, onComplete } = handlers;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `HTTP error ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          if (onComplete) onComplete();
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim()) continue;

          // Parse SSE format
          const eventMatch = line.match(/^event: (.+)$/m);
          const dataMatch = line.match(/^data: (.+)$/m);

          if (dataMatch) {
            try {
              const data = JSON.parse(dataMatch[1]);

              if (data.type === 'chunk' && onChunk) {
                onChunk(data.text);
              } else if (data.type === 'done') {
                if (onComplete) onComplete(data);
              } else if (data.type === 'error') {
                if (onError) onError(new Error(data.error));
              } else if (onMessage) {
                onMessage(data);
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
    } catch (error) {
      console.error('Stream request failed:', error);
      if (onError) onError(error);
      throw error;
    }
  },
};

// Expose globally
window.API = API;
