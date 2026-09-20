import axios from 'axios'

/**
 * POST /search — run scrape + score pipeline (or return cached result).
 * @param {Object} criteria - SearchCriteria object
 * @returns {Promise<Object>} SearchResponse data
 */
export async function searchJobs(criteria) {
  const { data } = await axios.post('/search', criteria)
  return data
}

/**
 * GET /export — download results as JSON or Excel.
 * Triggers a browser file download via a temporary Blob URL.
 * @param {string} searchId
 * @param {'json'|'excel'} format
 */
export async function exportResults(searchId, format) {
  const { data } = await axios.get('/export', {
    params: { search_id: searchId, format },
    responseType: 'blob',
  })

  const ext = format === 'excel' ? 'xlsx' : 'json'
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = `jobs-${searchId.slice(0, 8)}.${ext}`
  a.click()
  URL.revokeObjectURL(url)
}
