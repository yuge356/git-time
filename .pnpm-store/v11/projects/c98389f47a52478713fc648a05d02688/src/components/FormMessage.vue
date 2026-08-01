<template>
  <p v-if="message" :class="['form-message', `form-message--${type}`]" role="alert">
    {{ message }}
  </p>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    message?: string
    type?: 'error' | 'success'
  }>(),
  {
    message: '',
    type: 'error',
  },
)
</script>

