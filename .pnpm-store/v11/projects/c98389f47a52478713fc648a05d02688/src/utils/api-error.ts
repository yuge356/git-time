import axios from 'axios'

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>
}

export function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return error instanceof Error && error.message
      ? error.message
      : '发生未知错误，请稍后重试。'
  }

  const detail = error.response?.data?.detail
  if (typeof detail === 'string') {
    return detail
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg ?? '输入内容不正确').join('；')
  }
  if (!error.response) {
    return '无法连接服务器，请检查网络或后端服务。'
  }
  if ([502, 503, 504].includes(error.response.status)) {
    return '后端服务未启动或正在重启，请启动本地服务后再试。'
  }
  return '请求失败，请稍后重试。'
}
