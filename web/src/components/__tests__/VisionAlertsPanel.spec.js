import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../../services/visionSocket.js', () => ({
  connectVision: vi.fn(),
  disconnectVision: vi.fn(),
  onVisionAlert: vi.fn(() => vi.fn()),
  onVisionDetection: vi.fn(() => vi.fn()),
  onVisionError: vi.fn(() => vi.fn()),
  onVisionStatus: vi.fn(() => vi.fn()),
}))

import VisionAlertsPanel from '../VisionAlertsPanel.vue'


describe('VisionAlertsPanel', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('shows UTC, GPS, confidence and snapshot link', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    const wrapper = mount(VisionAlertsPanel)
    await wrapper.setData({
      alerts: [{
        event_id: '123e4567-e89b-12d3-a456-426614174000',
        timestamp: '2026-08-04T10:00:00.000Z',
        class_name: 'Person',
        confidence: 0.85,
        latitude: 51.1694,
        longitude: 71.4491,
      }],
    })

    expect(wrapper.text()).toContain('Person')
    expect(wrapper.text()).toContain('85%')
    expect(wrapper.text()).toContain('51.16940, 71.44910')
    expect(wrapper.text()).toContain('2026-08-04T10:00:00.000Z')
    expect(wrapper.get('a').attributes('href')).toContain(
      '/api/vision/snapshots/123e4567-e89b-12d3-a456-426614174000.jpg'
    )
  })

  it('refuses alerts without coordinates', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }))
    const wrapper = mount(VisionAlertsPanel)

    wrapper.vm.pushAlert({ event_id: 'bad', latitude: null, longitude: null })
    await wrapper.vm.$nextTick()

    expect(wrapper.vm.alerts).toEqual([])
    expect(wrapper.text()).toContain('Rejected event without GPS')
  })
})
