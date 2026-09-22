// Single source of truth for default scoring weights
// Must match backend/models/job.py ScoreWeights defaults

export const DEFAULT_WEIGHTS = {
  keywords_weight: 0.30,
  skills_weight: 0.25,
  salary_weight: 0.20,
  location_weight: 0.15,
  experience_weight: 0.10,
}

// For WeightSliders component (0-100 integer format)
export const DEFAULT_WEIGHTS_PERCENT = [30, 25, 20, 15, 10]

// Labels for display
export const WEIGHT_LABELS = [
  { idx: 0, key: 'keywords', label: 'Keywords' },
  { idx: 1, key: 'skills', label: 'Skills' },
  { idx: 2, key: 'salary', label: 'Salary' },
  { idx: 3, key: 'location', label: 'Location' },
  { idx: 4, key: 'experience', label: 'Experience' }
]
