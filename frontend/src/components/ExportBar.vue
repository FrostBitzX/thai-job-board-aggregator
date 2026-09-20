<script setup>
import { ref } from 'vue'
import { exportResults } from '../api.js'

const props = defineProps({
  searchId: {
    type: String,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

// Per-button in-flight state so each button gets its own spinner
const exportingJson  = ref(false)
const exportingExcel = ref(false)

async function doExport(format) {
  if (!props.searchId) return
  const flag = format === 'json' ? exportingJson : exportingExcel
  flag.value = true
  try {
    await exportResults(props.searchId, format)
  } finally {
    flag.value = false
  }
}
</script>

<template>
  <div class="export-bar">
    <button
      class="export-btn"
      :disabled="!searchId || loading || exportingJson"
      @click="doExport('json')"
    >
      <span v-if="exportingJson" class="spinner" aria-hidden="true"></span>
      <span>Export JSON</span>
    </button>

    <button
      class="export-btn"
      :disabled="!searchId || loading || exportingExcel"
      @click="doExport('excel')"
    >
      <span v-if="exportingExcel" class="spinner" aria-hidden="true"></span>
      <span>Export Excel</span>
    </button>
  </div>
</template>

<style scoped>
.export-bar {
  display: flex;
  gap: 10px;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 16px;
  border: 1px solid #2563eb;
  border-radius: 5px;
  background: #fff;
  color: #2563eb;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.export-btn:hover:not(:disabled) {
  background: #2563eb;
  color: #fff;
}

.export-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  border-color: #9ca3af;
  color: #9ca3af;
}

/* Simple CSS spinner */
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
