<template>
  <RouterLink class="brand" to="/" aria-label="DayFlow 首页">
    <span class="brand__logo" aria-hidden="true">
      <svg viewBox="0 0 100 100" role="presentation">
        <rect width="100" height="100" rx="23" fill="#7456f5" />
        <path
          d="M28.5 13 H50 C68 13 82 29.2 82 50 S68 87 50 87 H28.5 C22.7 87 18 82.3 18 76.5 V23.5 C18 17.7 22.7 13 28.5 13 Z"
          fill="#fff"
        />
        <path d="M31.5 26 H50 C61 26 68.5 36.5 68.5 50 S61 74 50 74 H31.5 Z" fill="#7456f5" />
        <g stroke="#fff" stroke-width="3" stroke-linecap="round" fill="none">
          <path d="M50 50 V34" />
          <path d="M50 50 H59" />
        </g>
        <circle cx="50" cy="50" r="3.4" fill="#fff" />
      </svg>
    </span>
    <span class="brand__copy">
      <strong>DayFlow</strong>
    </span>
  </RouterLink>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>
