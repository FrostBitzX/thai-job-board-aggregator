<script setup>
import { ref } from 'vue'
import SearchForm from './components/SearchForm.vue'
import WeightSliders from './components/WeightSliders.vue'
import ResultsTable from './components/ResultsTable.vue'
import ExportBar from './components/ExportBar.vue'
import { searchJobs } from './api.js'
import { DEFAULT_WEIGHTS } from './config/defaults'

const jobs      = ref([])
const searchId  = ref(null)
const loading   = ref(false)
const error     = ref(null)   // { message, retryable } | null
const cached    = ref(false)

// Holds the last submitted criteria so "Try Again" can replay it
const lastCriteria = ref(null)

// Tracks the latest weights from WeightSliders; merged into criteria on submit
const currentWeights = ref({ ...DEFAULT_WEIGHTS })

function onWeightsUpdate(weights) {
  currentWeights.value = weights
}

async function runSearch(criteria) {
  // Merge the latest weight slider values into the criteria
  const payload = { ...criteria, score_weights: { ...currentWeights.value } }
  lastCriteria.value = payload
  loading.value = true
  error.value   = null

  try {
    const response = await searchJobs(payload)
    jobs.value     = response.jobs ?? []
    searchId.value = response.search_id ?? null
    cached.value   = response.cached ?? false
  } catch (e) {
    // Axios throws for non-2xx; extract ErrorResponse from response body if present
    const errData = e?.response?.data
    error.value = {
      message:   errData?.message ?? e?.message ?? 'An unexpected error occurred.',
      retryable: errData?.retryable ?? false,
    }
    jobs.value     = []
    searchId.value = null
    cached.value   = false
  } finally {
    loading.value = false
  }
}

function onSubmit(criteria) {
  runSearch(criteria)
}

function onRetry() {
  if (lastCriteria.value) runSearch(lastCriteria.value)
}
</script>

<template>
  <div class="app-shell">
    <!-- Loading overlay (Req 8.5) -->
    <div v-if="loading" class="loading-overlay" role="status" aria-label="Searching…">
      <div class="spinner"></div>
      <span>Searching…</span>
    </div>

    <header class="app-header">
      <h1>Thai Job Board Aggregator</h1>
    </header>

    <main class="app-main">
      <!-- Error banner (Req 8.6) -->
      <div v-if="error" class="error-banner" role="alert">
        <span class="error-msg">{{ error.message }}</span>
        <button v-if="error.retryable" class="retry-btn" @click="onRetry">Try Again</button>
      </div>

      <section class="search-section">
        <SearchForm @submit="onSubmit" />
        <WeightSliders @update:weights="onWeightsUpdate" />
      </section>

      <section class="results-section">
        <div class="results-header">
          <ExportBar :search-id="searchId" :loading="loading" />
        </div>
        <!-- ResultsTable always rendered; empty state is handled inside the component -->
        <ResultsTable :jobs="jobs" :cached="cached" />
      </section>
    </main>
  </div>
</template>

<style>
/* Global resets — no scoped so they apply everywhere */
*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  font-size: 16px;
  background: #f8fafc;
  color: #1a1a1a;
}

button { font-family: inherit; }
</style>

<style scoped>
.app-shell {
  min-height: 100vh;
  position: relative;
}

/* Loading overlay (Req 8.5) */
.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.75);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 14px;
  z-index: 100;
  font-size: 1rem;
  color: #3b82f6;
  font-weight: 600;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #bfdbfe;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.app-header {
  background: #1e3a5f;
  color: #fff;
  padding: 16px 32px;
}

.app-header h1 {
  margin: 0;
  font-size: 1.3rem;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.app-main {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Error banner (Req 8.6) */
.error-banner {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #b91c1c;
  font-size: 0.9rem;
}

.error-msg {
  flex: 1;
}

.retry-btn {
  padding: 6px 16px;
  background: #b91c1c;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
}

.retry-btn:hover {
  background: #991b1b;
}

.search-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.results-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.results-header {
  display: flex;
  justify-content: flex-end;
}
</style>
