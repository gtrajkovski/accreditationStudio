/**
 * AgentProgressTracker - "Certified Authority" Design
 * Stepped progress visualization for streaming agent tasks
 *
 * Usage:
 *   const tracker = new AgentProgressTracker(containerElement);
 *   tracker.update(1, 5, 'Pass 1/5: Regulatory Mapping');
 *   tracker.update(2, 5, 'Pass 2/5: Analyzing Findings');
 *   tracker.complete();
 */

class AgentProgressTracker {
  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;

    this.options = {
      showStepLabels: true,
      animateShimmer: true,
      ...options
    };

    this.currentStep = 0;
    this.totalSteps = 0;
    this.steps = [];
    this.isComplete = false;

    this._render();
  }

  _render() {
    this.container.innerHTML = '';
    this.container.classList.add('progress-tracker');

    this.stepsContainer = document.createElement('div');
    this.stepsContainer.className = 'progress-tracker-steps';
    this.container.appendChild(this.stepsContainer);

    this.labelEl = document.createElement('div');
    this.labelEl.className = 'progress-tracker-label';
    this.container.appendChild(this.labelEl);
  }

  /**
   * Update progress to a new step
   * @param {number} step - Current step (1-indexed)
   * @param {number} total - Total steps
   * @param {string} label - Step label (e.g., "Pass 1/5: Regulatory Mapping")
   */
  update(step, total, label) {
    // Initialize steps if total changed
    if (total !== this.totalSteps) {
      this.totalSteps = total;
      this._initSteps(total);
    }

    this.currentStep = step;
    this.labelEl.textContent = label;

    // Update step indicators
    this.steps.forEach((stepEl, index) => {
      const stepNum = index + 1;
      stepEl.classList.remove('pending', 'active', 'complete');

      if (stepNum < step) {
        stepEl.classList.add('complete');
        stepEl.innerHTML = this._getCheckIcon();
      } else if (stepNum === step) {
        stepEl.classList.add('active');
        stepEl.innerHTML = `<span class="step-number">${stepNum}</span>`;
      } else {
        stepEl.classList.add('pending');
        stepEl.innerHTML = `<span class="step-number">${stepNum}</span>`;
      }
    });

    // Update shimmer bar
    this._updateShimmer(step, total);
  }

  /**
   * Mark the entire task as complete
   */
  complete() {
    this.isComplete = true;
    this.labelEl.textContent = 'Complete';
    this.labelEl.classList.add('complete');

    // Mark all steps as complete
    this.steps.forEach(stepEl => {
      stepEl.classList.remove('pending', 'active');
      stepEl.classList.add('complete');
      stepEl.innerHTML = this._getCheckIcon();
    });

    // Remove shimmer
    const shimmer = this.container.querySelector('.progress-tracker-shimmer');
    if (shimmer) {
      shimmer.remove();
    }

    // Add success indicator
    this.container.classList.add('progress-tracker-complete');
  }

  /**
   * Reset the tracker
   */
  reset() {
    this.currentStep = 0;
    this.totalSteps = 0;
    this.steps = [];
    this.isComplete = false;
    this.container.classList.remove('progress-tracker-complete');
    this._render();
  }

  _initSteps(total) {
    this.stepsContainer.innerHTML = '';
    this.steps = [];

    for (let i = 0; i < total; i++) {
      const step = document.createElement('div');
      step.className = 'progress-step pending';
      step.innerHTML = `<span class="step-number">${i + 1}</span>`;
      this.stepsContainer.appendChild(step);
      this.steps.push(step);

      // Add connector line (except after last step)
      if (i < total - 1) {
        const connector = document.createElement('div');
        connector.className = 'progress-connector';
        this.stepsContainer.appendChild(connector);
      }
    }
  }

  _updateShimmer(step, total) {
    let shimmer = this.container.querySelector('.progress-tracker-shimmer');

    if (!shimmer && this.options.animateShimmer) {
      shimmer = document.createElement('div');
      shimmer.className = 'progress-tracker-shimmer';
      this.container.appendChild(shimmer);
    }

    if (shimmer) {
      const progress = ((step - 1) / total) * 100;
      shimmer.style.setProperty('--shimmer-progress', `${progress}%`);
    }
  }

  _getCheckIcon() {
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
      <polyline points="20 6 9 17 4 12"/>
    </svg>`;
  }
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AgentProgressTracker;
}
