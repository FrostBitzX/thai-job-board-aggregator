// Validates: Requirements 9.5
import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import ExportBar from '../ExportBar.vue'

vi.mock('../../../api.js', () => ({
  exportResults: vi.fn(),
}))

describe('ExportBar', () => {
  it('disables both buttons when searchId is null', () => {
    const wrapper = mount(ExportBar, { props: { searchId: null, loading: false } })
    const buttons = wrapper.findAll('button.export-btn')
    expect(buttons).toHaveLength(2)
    buttons.forEach(btn => expect(btn.attributes('disabled')).toBeDefined())
  })

  it('enables both buttons when searchId is set and loading is false', () => {
    const wrapper = mount(ExportBar, { props: { searchId: 'abc123', loading: false } })
    const buttons = wrapper.findAll('button.export-btn')
    expect(buttons).toHaveLength(2)
    buttons.forEach(btn => expect(btn.attributes('disabled')).toBeUndefined())
  })
})
