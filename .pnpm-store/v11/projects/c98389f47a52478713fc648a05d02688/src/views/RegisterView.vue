<template>
  <AuthLayout>
    <header class="form-header">
      <p class="eyebrow">开始使用</p>
      <h2>创建账户</h2>
      <p>创建你的项目与任务时间预算空间。</p>
    </header>

    <form class="form-stack" @submit.prevent="submit">
      <div class="field-grid">
        <label class="field">
          <span>用户名</span>
          <input
            v-model.trim="form.username"
            type="text"
            autocomplete="username"
            minlength="3"
            maxlength="30"
            pattern="[A-Za-z0-9_]+"
            required
            placeholder="learner_01"
          />
          <small>3–30 位字母、数字或下划线</small>
        </label>

        <label class="field">
          <span>显示名称</span>
          <input
            v-model.trim="form.display_name"
            type="text"
            autocomplete="name"
            maxlength="80"
            required
            placeholder="你的名字"
          />
        </label>
      </div>

      <label class="field">
        <span>邮箱</span>
        <input
          v-model.trim="form.email"
          type="email"
          autocomplete="email"
          required
          placeholder="name@example.com"
        />
      </label>

      <label class="field">
        <span>密码</span>
        <input
          v-model="form.password"
          type="password"
          autocomplete="new-password"
          minlength="8"
          maxlength="128"
          required
          placeholder="至少 8 个字符"
        />
      </label>

      <FormMessage :message="errorMessage" />

      <button class="button button--primary" type="submit" :disabled="auth.loading">
        {{ auth.loading ? '创建中…' : '创建账户' }}
      </button>
    </form>

    <p class="form-footer">
      已有账户？
      <RouterLink to="/login">直接登录</RouterLink>
    </p>
  </AuthLayout>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AuthLayout from '@/components/AuthLayout.vue'
import FormMessage from '@/components/FormMessage.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/api-error'

const auth = useAuthStore()
const router = useRouter()
const errorMessage = ref('')
const form = reactive({
  email: '',
  username: '',
  display_name: '',
  password: '',
})

async function submit(): Promise<void> {
  errorMessage.value = ''
  try {
    await auth.register(form)
    await router.replace('/tasks')
  } catch (error) {
    errorMessage.value = getApiErrorMessage(error)
  }
}
</script>
