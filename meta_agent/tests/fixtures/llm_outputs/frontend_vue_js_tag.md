Here's the Vue 3 notification toast component:

```js
import { ref, onMounted, onUnmounted } from 'vue'

export default {
  name: 'NotificationToast',
  props: {
    message: { type: String, required: true },
    type: { type: String, default: 'info', validator: v => ['info', 'success', 'error', 'warning'].includes(v) },
    duration: { type: Number, default: 3000 },
  },
  setup(props, { emit }) {
    const visible = ref(false)
    let timer = null

    onMounted(() => {
      visible.value = true
      timer = setTimeout(() => {
        visible.value = false
        emit('close')
      }, props.duration)
    })

    onUnmounted(() => {
      if (timer) clearTimeout(timer)
    })

    const close = () => {
      visible.value = false
      emit('close')
    }

    return { visible, close }
  },
  template: `
    <transition name="toast-fade">
      <div v-if="visible" :class="['toast', 'toast--' + type]" role="alert">
        <span>{{ message }}</span>
        <button @click="close" aria-label="Close notification">&times;</button>
      </div>
    </transition>
  `,
}
```

```scss
.toast {
  position: fixed;
  top: 1rem;
  right: 1rem;
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  color: white;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  z-index: 9999;

  &--info { background: #3b82f6; }
  &--success { background: #22c55e; }
  &--error { background: #ef4444; }
  &--warning { background: #f59e0b; }
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.3s, transform 0.3s;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-1rem);
}
```

Uses the Composition API with proper cleanup of the auto-dismiss timer. The SCSS uses BEM-style modifier classes for toast variants.
