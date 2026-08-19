import axios from 'axios'

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>
}

const messageTranslations: Record<string, string> = {
  'Authentication is required': '登录状态已失效，请重新登录。',
  'Email or password is incorrect': '邮箱或密码不正确。',
  'Invalid login credentials': '邮箱、手机号或密码不正确。',
  'User already registered': '该邮箱或手机号已经注册。',
  'Email not confirmed': '邮箱尚未确认，请检查 Supabase 认证设置。',
  'Phone not confirmed': '手机号尚未确认，请检查 Supabase 认证设置。',
  'Phone provider is disabled': 'Supabase 尚未启用手机号登录。',
  'Signup is disabled': '当前暂不允许创建新账号。',
  'Password should be at least 6 characters': '密码长度至少为 6 个字符。',
  'Unable to validate email address: invalid format': '邮箱格式不正确。',
  'Database error saving new user': '账号资料保存失败，用户名可能已被使用，请更换后重试。',
  'Email or username is already registered': '邮箱或用户名已被注册。',
  'Account is disabled': '该账户已被停用。',
  'User not found': '未找到该用户。',
  'Username is already in use': '该用户名已被使用。',
  'Username may only contain letters, numbers and underscores': '用户名只能包含字母、数字和下划线。',
  'Username cannot be null': '用户名不能为空。',
  'Display name cannot be null': '显示名称不能为空。',
  'Display name cannot be blank': '显示名称不能为空。',
  'Timezone cannot be null': '时区不能为空。',
  'Timezone must be a valid IANA timezone name': '请选择有效的时区。',
  'Task not found': '未找到该任务。',
  'Task title cannot be null': '任务名称不能为空。',
  'Task title cannot be blank': '任务名称不能为空。',
  'A task cannot depend on itself': '任务不能依赖自身。',
  'Dependency task not found': '未找到所选的依赖任务。',
  'Task dependencies cannot contain a cycle': '任务依赖不能形成循环。',
  'Only executable tasks can be timed or added to a daily plan': '只有可执行任务才能计时或添加到今日任务。',
  'Projects must stay at the top level': '项目必须位于最顶层。',
  'A task cannot be its own parent': '任务不能将自身设为上级。',
  'Task hierarchy cannot contain a cycle': '任务层级不能形成循环。',
  'Existing task hierarchy is invalid': '当前任务层级无效，请刷新后重试。',
  'A fixed budget requires a time limit': '固定预算必须设置时间上限。',
  'Executable tasks cannot contain project or module defaults': '可执行任务不能设置项目或模块默认值。',
  'Projects and modules derive task status, time and recurrence': '项目和模块的状态、时间与重复规则由下级任务汇总。',
  'Executable tasks cannot define container defaults': '可执行任务不能设置容器默认值。',
  'Only projects and modules can apply defaults': '只有项目和模块可以应用默认设置。',
  'Finish the active timer before deleting its task': '请先结束当前计时，再删除对应任务。',
  'Daily plan not found': '未找到今日任务计划。',
  'Daily plan item not found': '未找到该今日任务。',
  'A daily plan already exists for this date': '该日期已经存在今日任务计划。',
  'Finish the active timer before deleting this daily item': '请先结束当前计时，再删除该今日任务。',
  'Standalone daily items require a title': '临时事项必须填写名称。',
  'Title cannot be null': '名称不能为空。',
  'Title cannot be blank': '名称不能为空。',
  'Field cannot be null': '必填内容不能为空。',
  'Notification not found': '未找到该通知。',
  'Partnership not found': '未找到该伙伴关系。',
  'You cannot invite yourself': '不能邀请自己成为伙伴。',
  'This user is unavailable': '该用户当前不可用。',
  'A partnership or invitation already exists': '伙伴关系或邀请已经存在。',
  'Only the invitation recipient can respond': '只有邀请接收者可以处理该邀请。',
  'This invitation has already been answered': '该邀请已经处理过。',
  'You cannot block yourself': '不能屏蔽自己。',
  'This user is already blocked': '该用户已被屏蔽。',
  'Block not found': '未找到该屏蔽记录。',
  'This partner is unavailable': '该伙伴当前不可用。',
  'An accepted partnership is required': '需要先建立伙伴关系。',
  'This plan is already shared with the partner': '该计划已经分享给此伙伴。',
  'Share not found': '未找到该分享记录。',
  'Another active timer already exists or the session id is unavailable': '已有任务正在计时，请先暂停或结束当前计时。',
  'Completed sessions cannot be changed': '已完成的计时记录不能修改。',
  'Session duration cannot decrease': '计时时长不能减少。',
  'A session cannot be moved to another task': '计时记录不能移动到其他任务。',
  'A session cannot be moved to another daily plan item': '计时记录不能移动到其他今日任务。',
  'A session cannot change its originating client': '计时记录不能更改其来源设备。',
  'A session cannot change its start time': '计时记录不能更改开始时间。',
  'Session task must match the daily plan item task': '计时任务与今日任务不一致。',
  'Session timestamps must include a timezone': '计时时间必须包含时区信息。',
  'A session must reference a task or daily plan item': '计时记录必须关联任务或今日任务。',
  'Running sessions require last_resumed_at and no ended_at': '进行中的计时记录状态不完整，请重新开始计时。',
  'Paused sessions cannot have active or ending timestamps': '暂停的计时记录状态不正确，请刷新后重试。',
  'Completed sessions require ended_at and no last_resumed_at': '已完成的计时记录状态不完整，请刷新后重试。',
  'Session cannot end before it starts': '计时结束时间不能早于开始时间。',
  'Session cannot resume before it starts': '计时恢复时间不能早于开始时间。',
  'Client update time cannot precede session start': '计时更新时间不能早于开始时间。',
  'date_to cannot precede date_from': '结束日期不能早于开始日期。',
  'Analytics range cannot exceed 366 days': '统计日期范围不能超过 366 天。',
  'Task store is not initialized': '任务数据尚未准备完成，请刷新页面后重试。',
  'Daily plan store is not initialized': '今日任务数据尚未准备完成，请刷新页面后重试。',
  'Daily plan is not loaded': '今日任务尚未加载完成，请刷新页面后重试。',
  'Timer store is not initialized': '计时数据尚未准备完成，请刷新页面后重试。',
  'Internal Server Error': '服务器内部错误，请检查数据库配置或稍后重试。',
  'Server error': '服务器处理异常，请稍后重试。',
}

const storageErrorTranslations: Record<string, string> = {
  DataCloneError: '本地缓存数据格式异常，请刷新页面后重试。',
  QuotaExceededError: '浏览器本地存储空间不足，请清理空间后重试。',
  InvalidStateError: '本地数据暂时不可用，请刷新页面后重试。',
  TransactionInactiveError: '本地保存已中断，请重试。',
  AbortError: '本地保存未完成，请重试。',
}

function translateMessage(message: string): string | null {
  const normalized = message.trim().replace(/^Value error,\s*/i, '')
  if (!normalized) return null
  const translated = messageTranslations[normalized]
  if (translated) return translated
  if (/nodes require a parent/i.test(normalized)) return '模块或任务必须设置上级。'
  if (/nodes must be placed under/i.test(normalized)) return '模块只能放在项目下，任务只能放在模块下。'
  if (/Cannot change session from/i.test(normalized)) return '当前计时状态不允许此操作。'
  if (/valid email address/i.test(normalized)) return '请输入有效的邮箱地址。'
  if (/Field required/i.test(normalized)) return '请填写所有必填内容。'
  if (/String should have at least/i.test(normalized)) return '输入内容长度不足。'
  if (/String should have at most/i.test(normalized)) return '输入内容长度超过限制。'
  if (/Internal Server Error/i.test(normalized)) return '服务器内部错误，请检查数据库配置或稍后重试。'
  if (/[\u3400-\u9fff]/.test(normalized)) return normalized
  return null
}

function statusMessage(status?: number): string {
  if (status === 401) return '登录状态已失效，请重新登录。'
  if (status === 403) return '当前账户没有执行此操作的权限。'
  if (status === 404) return '未找到所需内容，可能已被删除。'
  if (status === 409) return '当前数据状态发生冲突，请刷新后重试。'
  if (status === 422) return '输入内容不正确，请检查后重试。'
  if (status === 500) return '服务器内部错误，请检查后端数据库连接配置。'
  if (status && [502, 503, 504].includes(status)) {
    return '后端服务未启动或正在重启，请启动本地服务后再试。'
  }
  return '请求失败，请稍后重试。'
}

export function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    if (error instanceof DOMException) {
      const translatedStorageError = storageErrorTranslations[error.name]
      if (translatedStorageError) return translatedStorageError
    }
    if (error instanceof Error) {
      return translateMessage(error.message) ?? '操作未完成，请刷新页面后重试。'
    }
    return '发生未知错误，请稍后重试。'
  }

  if (!error.response) {
    return '无法连接服务器，请检查网络或后端服务。'
  }

  const detail = error.response.data?.detail
  if (typeof detail === 'string') {
    return translateMessage(detail) ?? statusMessage(error.response.status)
  }
  if (Array.isArray(detail)) {
    const translated = detail.map((item) =>
      item.msg ? (translateMessage(item.msg) ?? '输入内容不正确') : '输入内容不正确',
    )
    return [...new Set(translated)].join('；')
  }
  return statusMessage(error.response.status)
}
