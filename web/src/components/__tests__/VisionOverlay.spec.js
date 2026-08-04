import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import VisionOverlay from '../VisionOverlay.vue'

describe('VisionOverlay', () => {
  it('renders bbox, class and confidence in source-frame coordinates', () => {
    const wrapper = mount(VisionOverlay, {
      props: {
        videoSrc: '/demo.mp4',
        streamStatus: 'live',
        frameWidth: 1920,
        frameHeight: 1080,
        detections: [
          {
            class_name: 'Person',
            confidence: 0.82,
            bbox: [100, 200, 260, 520],
          },
        ],
      },
    })

    expect(wrapper.get('svg').attributes('viewBox')).toBe('0 0 1920 1080')
    const box = wrapper.get('[data-testid="detection-box"]')
    expect(box.attributes('x')).toBe('100')
    expect(box.attributes('y')).toBe('200')
    expect(box.attributes('width')).toBe('160')
    expect(box.attributes('height')).toBe('320')
    expect(wrapper.text()).toContain('Person 82%')
  })

  it('shows stopped state and ignores invalid bbox values', () => {
    const wrapper = mount(VisionOverlay, {
      props: {
        streamStatus: 'stopped',
        detections: [
          { class_name: 'Car', confidence: 0.9, bbox: [20, 20, 10, 40] },
        ],
      },
    })

    expect(wrapper.text()).toContain('Stream stopped')
    expect(wrapper.find('[data-testid="detection-box"]').exists()).toBe(false)
  })
})
