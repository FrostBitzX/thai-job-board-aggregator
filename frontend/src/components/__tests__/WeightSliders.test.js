// Validates: Requirements 8.3, 8.4
import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import WeightSliders from '../WeightSliders.vue'

const DEFAULTS = [30, 25, 20, 15, 10]

async function openPanel(wrapper) {
  await wrapper.find('button.toggle-btn').trigger('click')
}

function pctValues(wrapper) {
  return wrapper.findAll('.slider-pct').map(el => parseInt(el.text(), 10))
}

describe('WeightSliders', () => {
  it('reset restores default percentages', async () => {
    const wrapper = mount(WeightSliders)
    await openPanel(wrapper)
    // Move keywords slider so we have something to reset
    const keywordsSlider = wrapper.findAll('input[type="range"]')[0]
    await keywordsSlider.setValue(50)
    await keywordsSlider.trigger('input')

    await wrapper.find('button.reset-btn').trigger('click')
    expect(pctValues(wrapper)).toEqual(DEFAULTS)
  })

  it('slider adjustment keeps total at 100', async () => {
    const wrapper = mount(WeightSliders)
    await openPanel(wrapper)

    const keywordsSlider = wrapper.findAll('input[type="range"]')[0]
    // Simulate native input event with new value
    keywordsSlider.element.value = '50'
    await keywordsSlider.trigger('input')

    const sum = pctValues(wrapper).reduce((a, b) => a + b, 0)
    expect(sum).toBe(100)
  })
})
