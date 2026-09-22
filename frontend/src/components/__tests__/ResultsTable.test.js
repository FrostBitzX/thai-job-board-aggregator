// Validates: Requirements 9.3, 9.4
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import ResultsTable from '../ResultsTable.vue'

describe('ResultsTable', () => {
  it('shows empty state when jobs array is empty', () => {
    const wrapper = mount(ResultsTable, { props: { jobs: [] } })
    expect(wrapper.find('.empty-state').exists()).toBe(true)
  })

  it('shows cache indicator when cached=true', () => {
    const wrapper = mount(ResultsTable, { props: { jobs: [], cached: true } })
    expect(wrapper.find('[data-testid="cache-indicator"]').exists()).toBe(true)
  })
})
