<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-header">
        <h1 class="auth-title">JobPilot</h1>
        <p class="auth-subtitle">{{ isRegister ? "创建账号" : "登录" }}</p>
      </div>

      <form class="auth-form" @submit.prevent="handleSubmit">
        <div class="form-field">
          <label class="form-label" for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            class="form-input"
            type="text"
            placeholder="输入用户名"
            required
            autocomplete="username"
          />
        </div>

        <div v-if="isRegister" class="form-field">
          <label class="form-label" for="email">邮箱（可选）</label>
          <input
            id="email"
            v-model="form.email"
            class="form-input"
            type="email"
            placeholder="your@email.com"
            autocomplete="email"
          />
        </div>

        <div v-if="isRegister" class="form-field">
          <label class="form-label" for="display_name">显示名称（可选）</label>
          <input
            id="display_name"
            v-model="form.display_name"
            class="form-input"
            type="text"
            placeholder="你的名字"
          />
        </div>

        <div class="form-field">
          <label class="form-label" for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            class="form-input"
            type="password"
            placeholder="至少 6 位"
            required
            minlength="6"
            autocomplete="current-password"
          />
        </div>

        <p v-if="errorMsg" class="form-error">{{ errorMsg }}</p>

        <button class="form-submit" type="submit" :disabled="loading">
          {{ loading ? "请稍候..." : isRegister ? "注册" : "登录" }}
        </button>
      </form>

      <div class="auth-switch">
        <span>{{ isRegister ? "已有账号？" : "没有账号？" }}</span>
        <button class="auth-switch-btn" type="button" @click="toggleMode">
          {{ isRegister ? "去登录" : "去注册" }}
        </button>
      </div>

      <div class="auth-dev-hint">
        <p>开发模式下也可以直接进入应用（无需注册）</p>
        <button class="auth-dev-btn" type="button" @click="enterDevMode">
          以 Demo 用户进入 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import { login, register } from "@/api/auth";
import { saveAuthSession } from "@/lib/currentUser";
import axios from "axios";

const router = useRouter();
const isRegister = ref(false);
const loading = ref(false);
const errorMsg = ref("");

const form = reactive({
  username: "",
  password: "",
  email: "",
  display_name: "",
});

function toggleMode() {
  isRegister.value = !isRegister.value;
  errorMsg.value = "";
}

async function handleSubmit() {
  loading.value = true;
  errorMsg.value = "";

  try {
    const resp = isRegister.value
      ? await register({
          username: form.username,
          password: form.password,
          email: form.email || undefined,
          display_name: form.display_name || undefined,
        })
      : await login({ username: form.username, password: form.password });

    saveAuthSession(resp.access_token, resp.user);
    router.push("/");
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.data?.detail) {
      errorMsg.value = err.response.data.detail;
    } else {
      errorMsg.value = "操作失败，请稍后重试";
    }
  } finally {
    loading.value = false;
  }
}

function enterDevMode() {
  router.push("/");
}
</script>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-primary, #f8f9fa);
  padding: 24px;
}

.auth-card {
  width: 100%;
  max-width: 400px;
  background: var(--color-bg-surface, #fff);
  border-radius: 12px;
  padding: 40px 32px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.04);
}

.auth-header {
  text-align: center;
  margin-bottom: 32px;
}

.auth-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary, #111);
  margin: 0 0 8px;
}

.auth-subtitle {
  font-size: 15px;
  color: var(--color-text-secondary, #666);
  margin: 0;
}

.form-field {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary, #555);
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 8px;
  background: var(--color-bg-primary, #f8f9fa);
  color: var(--color-text-primary, #111);
  transition: border-color 0.15s;
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--color-accent, #4f46e5);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.form-error {
  color: var(--color-danger, #dc2626);
  font-size: 13px;
  margin: 0 0 16px;
}

.form-submit {
  width: 100%;
  padding: 11px 0;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  background: var(--color-accent, #4f46e5);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.15s;
}

.form-submit:hover:not(:disabled) {
  opacity: 0.9;
}

.form-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.auth-switch {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: var(--color-text-secondary, #666);
}

.auth-switch-btn {
  background: none;
  border: none;
  color: var(--color-accent, #4f46e5);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  padding: 0;
  margin-left: 4px;
}

.auth-dev-hint {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--color-border, #eee);
  text-align: center;
}

.auth-dev-hint p {
  font-size: 12px;
  color: var(--color-text-muted, #999);
  margin: 0 0 8px;
}

.auth-dev-btn {
  background: none;
  border: 1px solid var(--color-border, #ddd);
  border-radius: 6px;
  padding: 6px 16px;
  font-size: 13px;
  color: var(--color-text-secondary, #666);
  cursor: pointer;
  transition: all 0.15s;
}

.auth-dev-btn:hover {
  background: var(--color-bg-primary, #f8f9fa);
  border-color: var(--color-text-secondary, #999);
}
</style>
