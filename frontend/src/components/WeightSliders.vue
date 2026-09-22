<script setup>
import { ref, computed } from 'vue'
import { DEFAULT_WEIGHTS_PERCENT, WEIGHT_LABELS } from '@/config/defaults'

const emit = defineEmits(['update:weights'])


const DEFAULTS = DEFAULT_WEIGHTS_PERCENT
const LABELS = WEIGHT_LABELS


const weights = ref([...DEFAULTS])
const open = ref(false)

function onSliderInput(idx, event) {
  const raw = event.target.value
  const current = weights.value[idx]
  const sum = weights.value.reduce((a, b) => a + b, 0)
  const remaining = 100 - sum
  const ceiling = current + remaining
  const next = Math.max(0, Math.min(Math.round(Number(raw)), ceiling))
  
  if (next !== Number(raw)) {
    event.target.value = next
  }
  
  weights.value[idx] = next
  emitWeights()
}

function onNumberInput(idx, event) {
  const raw = event.target.value
  const current = weights.value[idx]

  const sum = weights.value.reduce((a, b) => a + b, 0)
  const remaining = 100 - sum
  
  const ceiling = current + remaining

  const next = Math.max(0, Math.min(Math.round(Number(raw) || 0), ceiling))
  
  weights.value[idx] = next
  emitWeights()
}

function reset() {
  weights.value = [...DEFAULTS]
  emitWeights()
}

function emitWeights() {
  emit('update:weights', {
    keywords_weight: weights.value[0] / 100,
    skills_weight: weights.value[1] / 100,
    salary_weight: weights.value[2] / 100,
    location_weight: weights.value[3] / 100,
    experience_weight: weights.value[4] / 100,
  })
}

const totalWeight = computed(() => {
  return weights.value.reduce((sum, val) => sum + val, 0)
})

const isDefault = computed(() => {
  return weights.value.every((val, idx) => val === DEFAULTS[idx])
})

const isOverLimit = computed(() => totalWeight.value > 100)
</script>

<template>
  <div class="weight-sliders">
    <button type="button" class="toggle-btn" @click="open = !open" :aria-expanded="open.toString()">
      <span>Adjust Scoring Weights</span>
      <span class="chevron" :class="{ rotated: open }">▾</span>
    </button>

    <div v-if="open" class="sliders-panel">
      <div class="panel-header">
        <div class="total-info">
          <span class="total-label">Total:</span>
          <span class="total-value" :class="{ 'over-limit': isOverLimit }">
            {{ totalWeight }}%
          </span>
          <span v-if="isOverLimit" class="lock-notice">Over 100% - reduce weights to increase others</span>
          <span v-else-if="totalWeight >= 100" class="lock-notice">At 100% - reduce weights to increase others</span>
        </div>
      </div>

      <div class="sliders-list">
        <div v-for="item in LABELS" :key="item.key" class="slider-row">
          <label :for="`weight-${item.key}`" class="slider-label">{{ item.label }}</label>
          
          <div class="slider-control">
            <input
              :id="`weight-${item.key}`"
              type="range"
              min="0"
              max="100"
              step="1"
              :value="weights[item.idx]"
              @input="onSliderInput(item.idx, $event)"
              class="slider"
            />
            <input 
              type="number" 
              :value="weights[item.idx]"
              @change="onNumberInput(item.idx, $event)"
              min="0"
              max="100"
              step="1"
              class="slider-number"
            />
            <span class="pct">%</span>
          </div>
        </div>
      </div>

      <div class="panel-footer">
        <a 
          v-if="!isDefault"
          href="#" 
          class="reset-link" 
          @click.prevent="reset"
        >
          Reset to default
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.weight-sliders {
  max-width: 100%;
  margin: 16px 0;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: white;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 10px 16px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  color: #374151;
  transition: all 0.2s;
}

.toggle-btn:hover {
  background: #f9fafb;
  border-color: #9ca3af;
}

.chevron {
  display: inline-block;
  margin-left: auto;
  transition: transform 0.2s;
  color: #6b7280;
}

.chevron.rotated {
  transform: rotate(-180deg);
}

.sliders-panel {
  margin-top: 12px;
  padding: 20px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
}

.panel-header {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e5e7eb;
}

.total-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.total-label {
  font-size: 0.875rem;
  color: #6b7280;
}

.total-value {
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  font-variant-numeric: tabular-nums;
}

.total-value.over-limit {
  color: #dc2626;
}

.lock-notice {
  font-size: 0.75rem;
  color: #dc2626;
  margin-left: 4px;
}

.sliders-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.slider-label {
  min-width: 90px;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
}

.slider-control {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: #e5e7eb;
  outline: none;
  -webkit-appearance: none;
  appearance: none;
  cursor: pointer;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  transition: all 0.2s;
}

.slider::-webkit-slider-thumb:hover {
  background: #2563eb;
  transform: scale(1.1);
}

.slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.slider::-moz-range-thumb:hover {
  background: #2563eb;
  transform: scale(1.1);
}

.slider-number {
  width: 50px;
  padding: 4px 8px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 0.875rem;
  text-align: center;
  font-variant-numeric: tabular-nums;
  color: #374151;
}

.slider-number:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
}

.pct {
  font-size: 0.875rem;
  color: #6b7280;
  width: 16px;
}

.panel-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #e5e7eb;
}

.reset-link {
  font-size: 0.875rem;
  color: #3b82f6;
  text-decoration: underline;
  cursor: pointer;
  display: inline-block;
}

.reset-link:hover {
  color: #2563eb;
}

@media (max-width: 768px) {
  .slider-row {
    flex-direction: column;
    align-items: stretch;
    gap: 8px;
  }
  
  .slider-label {
    min-width: auto;
  }
}
</style>
