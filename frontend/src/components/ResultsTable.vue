<script setup>
const props = defineProps({
  jobs: {
    type: Array,
    default: () => [],
  },
  cached: {
    type: Boolean,
    default: false,
  },
})

function scoreClass(score) {
  if (score >= 0.70) return 'score-green'
  if (score >= 0.40) return 'score-amber'
  return 'score-red'
}

function formatScore(score) {
  return (score * 100).toFixed(1) + '%'
}

function formatDate(isoStr) {
  if (!isoStr) return '—'
  const d = new Date(isoStr)
  return isNaN(d.getTime()) ? isoStr : d.toLocaleDateString()
}

function primaryCategory(categories) {
  return Array.isArray(categories) && categories.length ? categories[0] : '—'
}
</script>

<template>
  <div class="results-table-wrapper">
    <div v-if="cached" data-testid="cache-indicator" class="cache-badge">
      Cached result
    </div>

    <p v-if="jobs.length === 0" class="empty-state">
      No results found. Try adjusting your search criteria.
    </p>

    <div v-else class="table-scroll">
      <table class="results-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Score</th>
            <th>Title</th>
            <th>Company</th>
            <th>Location</th>
            <th>Salary</th>
            <th>Work Arrangement</th>
            <th>Category</th>
            <th>Posted</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in jobs" :key="item.job.id">
            <td class="col-rank">{{ item.rank }}</td>
            <td class="col-score">
              <div class="score-bar-track" :title="formatScore(item.score)">
                <div
                  class="score-bar-fill"
                  :class="scoreClass(item.score)"
                  :style="{ width: (item.score * 100) + '%' }"
                ></div>
              </div>
              <span class="score-label">{{ formatScore(item.score) }}</span>
            </td>
            <td class="col-title">
              <a :href="item.job.url" target="_blank" rel="noopener noreferrer">
                {{ item.job.title }}
              </a>
            </td>
            <td>{{ item.job.company || '—' }}</td>
            <td>{{ item.job.location || '—' }}</td>
            <td>{{ item.job.salary_display || '—' }}</td>
            <td>{{ item.job.work_arrangement || '—' }}</td>
            <td>{{ primaryCategory(item.job.categories) }}</td>
            <td class="col-date">{{ formatDate(item.job.listed_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.results-table-wrapper {
  width: 100%;
}

.cache-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 10px;
  padding: 4px 10px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 4px;
  font-size: 0.8rem;
  color: #1d4ed8;
  font-weight: 600;
}

.empty-state {
  padding: 32px 0;
  text-align: center;
  color: #666;
  font-size: 0.95rem;
}

.table-scroll {
  overflow-x: auto;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}

.results-table th,
.results-table td {
  padding: 9px 12px;
  text-align: left;
  border-bottom: 1px solid #e5e7eb;
  white-space: normal;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.results-table th {
  background: #f9fafb;
  font-weight: 700;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: #374151;
}

.results-table tbody tr:hover {
  background: #f0f7ff;
}

.col-rank {
  width: 52px;
  text-align: center;
  font-weight: 700;
  color: #555;
}

.col-score {
  width: 110px;
}

.score-bar-track {
  width: 70px;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
  display: inline-block;
  vertical-align: middle;
}

.score-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.2s;
}

.score-green  { background: #22c55e; }
.score-amber  { background: #f59e0b; }
.score-red    { background: #ef4444; }

.score-label {
  display: inline-block;
  margin-left: 6px;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  color: #444;
  vertical-align: middle;
}

.col-title a {
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
}

.col-title a:hover {
  text-decoration: underline;
}

.col-title {
  max-width: 300px;
  min-width: 200px;
}

.col-date {
  color: #666;
  font-size: 0.82rem;
}
</style>
