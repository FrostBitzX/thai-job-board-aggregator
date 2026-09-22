<script setup>
import { reactive } from 'vue'

const emit = defineEmits(['submit'])

const form = reactive({
  keywords: '',
  industry: '',
  required_skills: '',
  experience_min_years: '',
  experience_max_years: '',
  salary_min: '',
  salary_max: '',
  location: '',
  work_arrangement: '',
  company: '',
  result_limit: 100,
  source: 'jobsdb',
})

function handleSubmit() {
  const criteria = {
    keywords: form.keywords.trim(),
    industry: form.industry.trim() || null,
    required_skills: form.required_skills
      .split(',')
      .map(s => s.trim())
      .filter(Boolean),
    experience_min_years: form.experience_min_years !== '' ? Number(form.experience_min_years) : null,
    experience_max_years: form.experience_max_years !== '' ? Number(form.experience_max_years) : null,
    salary_min: form.salary_min !== '' ? Number(form.salary_min) : null,
    salary_max: form.salary_max !== '' ? Number(form.salary_max) : null,
    location: form.location.trim() || null,
    work_arrangement: form.work_arrangement || null,
    company: form.company.trim() || null,
    page_size: Math.min(Number(form.result_limit) || 100, 500),
    source: form.source,
    score_weights: {
      keywords_weight: 0.30,
      skills_weight: 0.25,
      salary_weight: 0.20,
      location_weight: 0.15,
      experience_weight: 0.10,
    },
  }
  emit('submit', criteria)
}
</script>

<template>
  <form class="search-form" @submit.prevent="handleSubmit">
    <div class="form-group required">
      <label for="keywords">Keywords</label>
      <input
        id="keywords"
        v-model="form.keywords"
        type="text"
        placeholder="e.g. backend developer"
        required
      />
    </div>

    <div class="form-row">
      <div class="form-group">
        <label for="industry">Industry</label>
        <input id="industry" v-model="form.industry" type="text" placeholder="e.g. Technology" />
      </div>

      <div class="form-group">
        <label for="company">Company</label>
        <input id="company" v-model="form.company" type="text" placeholder="e.g. Agoda" />
      </div>
    </div>

    <div class="form-group">
      <label for="required_skills">Required Skills <span class="hint">(comma-separated)</span></label>
      <input
        id="required_skills"
        v-model="form.required_skills"
        type="text"
        placeholder="e.g. python, docker, kubernetes"
      />
    </div>

    <div class="form-row">
      <div class="form-group">
        <label for="experience_min_years">Experience Min (years)</label>
        <input
          id="experience_min_years"
          v-model="form.experience_min_years"
          type="number"
          min="0"
          step="0.5"
          placeholder="e.g. 2"
        />
      </div>

      <div class="form-group">
        <label for="experience_max_years">Experience Max (years)</label>
        <input
          id="experience_max_years"
          v-model="form.experience_max_years"
          type="number"
          min="0"
          step="0.5"
          placeholder="e.g. 5"
        />
      </div>
    </div>

    <p class="field-hint">e.g. Min: 0, Max: 2 for entry-level; Min: 3 for 3+ years</p>

    <div class="form-row">
      <div class="form-group">
        <label for="salary_min">Salary Min (THB)</label>
        <input
          id="salary_min"
          v-model="form.salary_min"
          type="number"
          min="0"
          placeholder="e.g. 30000"
        />
      </div>

      <div class="form-group">
        <label for="salary_max">Salary Max (THB)</label>
        <input
          id="salary_max"
          v-model="form.salary_max"
          type="number"
          min="0"
          placeholder="e.g. 80000"
        />
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label for="location">Location</label>
        <input id="location" v-model="form.location" type="text" placeholder="e.g. Bangkok" />
      </div>

      <div class="form-group">
        <label for="work_arrangement">Work Arrangement</label>
        <select id="work_arrangement" v-model="form.work_arrangement">
          <option value="">Any</option>
          <option value="Onsite">Onsite</option>
          <option value="Remote">Remote</option>
          <option value="Hybrid">Hybrid</option>
        </select>
      </div>
    </div>

    <div class="form-row">
      <div class="form-group">
        <label for="result_limit">Result Limit</label>
        <input
          id="result_limit"
          v-model.number="form.result_limit"
          type="number"
          min="1"
          max="500"
          placeholder="100"
        />
      </div>

      <div class="form-group">
        <label for="source">Source</label>
        <select id="source" v-model="form.source">
          <option value="jobsdb">JobsDB</option>
        </select>
      </div>
    </div>

    <button type="submit" class="submit-btn">Search</button>
  </form>
</template>

<style scoped>
.search-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 720px;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-row .form-group {
  flex: 1;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 600;
}

.form-group.required label::after {
  content: ' *';
  color: #e53e3e;
}

.hint {
  font-weight: 400;
  color: #666;
}

.field-hint {
  margin: -8px 0 0;
  font-size: 0.78rem;
  color: #666;
}

.form-group input,
.form-group select {
  padding: 8px 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 0.9rem;
  background: #fff;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.submit-btn {
  align-self: flex-start;
  padding: 10px 28px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
}

.submit-btn:hover {
  background: #2563eb;
}
</style>
