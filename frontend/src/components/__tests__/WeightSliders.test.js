// Validates: Requirements 8.3, 8.4
import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import WeightSliders from '../WeightSliders.vue'

const DEFAULTS = [30, 25, 20, 15, 10]

async function openPanel(wrapper) {
  await wrapper.find('button.toggle-btn').trigger('click')
  await flushPromises()
}

function getWeightValues(wrapper) {
  const sliders = wrapper.findAll('input[type="range"]')
  return sliders.map(s => parseInt(s.element.value, 10))
}

describe('WeightSliders', () => {
  it('reset restores default weights', async () => {
    const wrapper = mount(WeightSliders)
    await openPanel(wrapper)
    
    // Reduce keywords slider first
    const keywordsSlider = wrapper.findAll('input[type="range"]')[0]
    keywordsSlider.element.value = '10'
    await keywordsSlider.trigger('input')
    await flushPromises()

    // Now reset link should appear
    const resetLink = wrapper.find('a.reset-link')
    expect(resetLink.exists()).toBe(true)
    await resetLink.trigger('click')
    await flushPromises()
    
    const weights = getWeightValues(wrapper)
    expect(weights).toEqual(DEFAULTS)
  })

  it('slider adjustment is independent but locked at 100%', async () => {
    const wrapper = mount(WeightSliders)
    await openPanel(wrapper)

    const keywordsSlider = wrapper.findAll('input[type="range"]')[0]
    const salarySlider = wrapper.findAll('input[type="range"]')[2]
    
    // Reduce keywords to 10
    keywordsSlider.element.value = '10'
    await keywordsSlider.trigger('input')
    await flushPromises()
    
    const beforeSalary = getWeightValues(wrapper)
    
    // Increase salary to 30
    salarySlider.element.value = '30'
    await salarySlider.trigger('input')
    await flushPromises()
    
    const afterSalary = getWeightValues(wrapper)
    
    // Keywords should remain changed
    expect(afterSalary[0]).toBe(10)
    // Skills, location, experience should remain unchanged
    expect(afterSalary[1]).toBe(beforeSalary[1])
    expect(afterSalary[3]).toBe(beforeSalary[3])
    expect(afterSalary[4]).toBe(beforeSalary[4])
    // Salary should be updated
    expect(afterSalary[2]).toBe(30)
  })

  it('emits correct weight values on change', async () => {
    const wrapper = mount(WeightSliders)
    await openPanel(wrapper)

    const keywordsSlider = wrapper.findAll('input[type="range"]')[0]
    keywordsSlider.element.value = '20'
    await keywordsSlider.trigger('input')
    await flushPromises()

    const emitted = wrapper.emitted('update:weights')
    expect(emitted).toBeTruthy()
    expect(emitted.length).toBeGreaterThan(0)
    expect(emitted[emitted.length - 1][0].keywords_weight).toBeCloseTo(0.20, 2)
  })
})
