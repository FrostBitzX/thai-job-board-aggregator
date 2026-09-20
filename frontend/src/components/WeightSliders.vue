<script setup>
import { ref, computed } from 'vue'

const emit = defineEmits(['update:weights'])

const DEFAULTS = { keywords: 30, skills: 25, salary: 20, location: 15, experience: 10 }
const LABELS = ['keywords', 'skills', 'salary', 'location', 'experience']

const weights = ref({ ...DEFAULTS })
const open = ref(false)

function onSliderInput(changed, rawValue) {
  const newVal = Math.round(Number(rawValue))
  const oldVal = weights.value[changed]
  const delta = newVal - oldVal

  if (delta === 0) return

  // Other sliders that can absorb the delta (non-zero, or we're giving back)
  const others = LABELS.filter(k => k !== changed)
  const absorbers = delta > 0
    ? others.filter(k => weights.value[k] > 0)   // taking from non-zero
    : others                                        // giving back to all

  if (absorbers.length === 0) {
    // Only one non-zero slider — no effect
    return
  }

  const totalAbsorber = absorbers.reduce((s, k) => s + weights.value[k], 0)

  // If shrinking below 0, clamp the moved slider
  const clampedNew = Math.max(0, Math.min(100, newVal))
  const actualDelta = clampedNew - oldVal

  if (actualDelta === 0) return

  const next = { ...weights.value, [changed]: clampedNew }

  if (totalAbsorber === 0) {
    // Can't distribute — revert
    return
  }

  // Distribute -actualDelta proportionally across absorbers
  let remaining = -actualDelta
  absorbers.forEach((k, i) => {
    if (i === absorbers.length - 1) {
      // Last absorber gets the remainder to avoid rounding drift
      next[k] = Math.max(0, weights.value[k] + remaining)
    } else {
      const share = Math.round((-actualDelta) * (weights.value[k] / totalAbsorber))
      next[k] = Math.max(0, weights.value[k] + share)
      remaining -= share
    }
  })

  // Final guard: clamp all and re-pin total to 100
  LABELS.forEach(k => { next[k] = Math.max(0, Math.min(100, next[k])) })
  const total = LABELS.reduce((s, k) => s + next[k], 0)
  if (total !== 100) {
    // Pin the moved slider to absorb the rounding residual
    next[changed] = clampedNew + (100 - total)
  }

  weights.value = next
  emitWeights()
}

function reset() {
  weights.value = { ...DEFAULTS }
  emitWeights()
}

function emitWeights() {
  emit('update:weights', {
    keywords_weight: weights.value.keywords / 100,
    skills_weight: weights.value.skills / 100,
    salary_weight: weights.value.salary / 100,
    location_weight: weights.value.location / 100,
    experience_weight: weights.value.experience / 100,
  })
}

const sliders = computed(() =>
  LABELS.map(key => ({ key, label: key.charAt(0).toUpperCase() + key.slice(1) }))
)
</script>

<template>
  <div class="weight-sliders">
    <button type="button" class="toggle-btn" @click="open = !open" :aria-expanded="open.toString()">
      Adjust Scoring Weights
      <span class="chevron" :class="{ rotated: open }" aria-hidden="true">▾</span>
    </button>

    <div v-if="open" class="sliders-panel">
      <div v-for="s in sliders" :key="s.key" class="slider-row">
        <label :for="`weight-${s.key}`" class="slider-label">{{ s.label }}</label>
        <input
          :id="`weight-${s.key}`"
          type="range"
          min="0"
          max="100"
          step="1"
          :value="weights[s.key]"
          @input="onSliderInput(s.key, $event.target.value)"
          class="slider"
        />
        <span class="slider-pct">{{ weights[s.key] }}%</span>
      </div>

      <button type="button" class="reset-btn" @click="reset">Reset to defaults</button>
    </div>
  </div>
</template>

<style scoped>
.weight-sliders {
  max-width: 720px;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 1px solid #ccc;
  border-radius: 4px;
  padding: 7px 14px;
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  color: #333;
}

.toggle-btn:hover {
  background: #f5f5f5;
}

.chevron {
  display: inline-block;
  transition: transform 0.2s;
}

.chevron.rotated {
  transform: rotate(-180deg);
}

.sliders-panel {
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.slider-label {
  width: 90px;
  font-size: 0.875rem;
  font-weight: 600;
  flex-shrink: 0;
}

.slider {
  flex: 1;
  accent-color: #3b82f6;
  cursor: pointer;
}

.slider-pct {
  width: 38px;
  text-align: right;
  font-size: 0.875rem;
  font-variant-numeric: tabular-nums;
  color: #444;
}

.reset-btn {
  align-self: flex-start;
  margin-top: 4px;
  padding: 6px 14px;
  background: none;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.82rem;
  cursor: pointer;
  color: #555;
}

.reset-btn:hover {
  background: #f5f5f5;
  border-color: #999;
}
</style>
