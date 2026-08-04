import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import VisionPanel from '../VisionPanel.vue'

describe('VisionPanel', () => {
  it('renders camera, model and stream states with metrics', () => {
    const wrapper = mount(VisionPanel, {
      props: {
        cameraStatus: 'connected',
        modelStatus: 'ready',
        streamStatus: 'live',
        modelName: 'yolov8n.pt',
        fps: 12.76,
        latencyMs: 480,
      },
    })

    expect(wrapper.get('[data-testid="camera-status"]').text()).toContain('Connected')
    expect(wrapper.get('[data-testid="model-status"]').text()).toContain('Ready')
    expect(wrapper.get('[data-testid="stream-status"]').text()).toContain('Live')
    expect(wrapper.text()).toContain('yolov8n.pt')
    expect(wrapper.text()).toContain('12.8 FPS')
    expect(wrapper.text()).toContain('480 ms')
  })

  it('marks missing model and stopped stream as unavailable', () => {
    const wrapper = mount(VisionPanel, {
      props: {
        cameraStatus: 'disconnected',
        modelStatus: 'missing',
        streamStatus: 'stopped',
      },
    })

    expect(wrapper.text()).toContain('Disconnected')
    expect(wrapper.text()).toContain('Model missing')
    expect(wrapper.text()).toContain('Stopped')
    expect(wrapper.findAll('.state-row.unavailable')).toHaveLength(3)
  })
})
