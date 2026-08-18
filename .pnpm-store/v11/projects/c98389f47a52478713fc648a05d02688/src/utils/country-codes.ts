export interface CountryDialCode {
  iso: string
  name: string
  dialCode: string
}

export const DEFAULT_COUNTRY_ISO = 'CN'

export const countryDialCodes: CountryDialCode[] = [
  { iso: 'CN', name: '中国大陆', dialCode: '+86' },
  { iso: 'HK', name: '中国香港', dialCode: '+852' },
  { iso: 'MO', name: '中国澳门', dialCode: '+853' },
  { iso: 'TW', name: '中国台湾', dialCode: '+886' },
  { iso: 'US', name: '美国', dialCode: '+1' },
  { iso: 'CA', name: '加拿大', dialCode: '+1' },
  { iso: 'JP', name: '日本', dialCode: '+81' },
  { iso: 'KR', name: '韩国', dialCode: '+82' },
  { iso: 'SG', name: '新加坡', dialCode: '+65' },
  { iso: 'MY', name: '马来西亚', dialCode: '+60' },
  { iso: 'TH', name: '泰国', dialCode: '+66' },
  { iso: 'VN', name: '越南', dialCode: '+84' },
  { iso: 'PH', name: '菲律宾', dialCode: '+63' },
  { iso: 'ID', name: '印度尼西亚', dialCode: '+62' },
  { iso: 'IN', name: '印度', dialCode: '+91' },
  { iso: 'AU', name: '澳大利亚', dialCode: '+61' },
  { iso: 'NZ', name: '新西兰', dialCode: '+64' },
  { iso: 'GB', name: '英国', dialCode: '+44' },
  { iso: 'FR', name: '法国', dialCode: '+33' },
  { iso: 'DE', name: '德国', dialCode: '+49' },
  { iso: 'IT', name: '意大利', dialCode: '+39' },
  { iso: 'ES', name: '西班牙', dialCode: '+34' },
  { iso: 'PT', name: '葡萄牙', dialCode: '+351' },
  { iso: 'NL', name: '荷兰', dialCode: '+31' },
  { iso: 'BE', name: '比利时', dialCode: '+32' },
  { iso: 'CH', name: '瑞士', dialCode: '+41' },
  { iso: 'AT', name: '奥地利', dialCode: '+43' },
  { iso: 'SE', name: '瑞典', dialCode: '+46' },
  { iso: 'NO', name: '挪威', dialCode: '+47' },
  { iso: 'DK', name: '丹麦', dialCode: '+45' },
  { iso: 'FI', name: '芬兰', dialCode: '+358' },
  { iso: 'IE', name: '爱尔兰', dialCode: '+353' },
  { iso: 'PL', name: '波兰', dialCode: '+48' },
  { iso: 'CZ', name: '捷克', dialCode: '+420' },
  { iso: 'HU', name: '匈牙利', dialCode: '+36' },
  { iso: 'GR', name: '希腊', dialCode: '+30' },
  { iso: 'RO', name: '罗马尼亚', dialCode: '+40' },
  { iso: 'RU', name: '俄罗斯', dialCode: '+7' },
  { iso: 'UA', name: '乌克兰', dialCode: '+380' },
  { iso: 'TR', name: '土耳其', dialCode: '+90' },
  { iso: 'AE', name: '阿联酋', dialCode: '+971' },
  { iso: 'SA', name: '沙特阿拉伯', dialCode: '+966' },
  { iso: 'IL', name: '以色列', dialCode: '+972' },
  { iso: 'BR', name: '巴西', dialCode: '+55' },
  { iso: 'MX', name: '墨西哥', dialCode: '+52' },
  { iso: 'AR', name: '阿根廷', dialCode: '+54' },
  { iso: 'CL', name: '智利', dialCode: '+56' },
  { iso: 'CO', name: '哥伦比亚', dialCode: '+57' },
  { iso: 'ZA', name: '南非', dialCode: '+27' },
  { iso: 'EG', name: '埃及', dialCode: '+20' },
  { iso: 'NG', name: '尼日利亚', dialCode: '+234' },
  { iso: 'KE', name: '肯尼亚', dialCode: '+254' },
]

export function countryDialCode(iso: string): CountryDialCode | undefined {
  return countryDialCodes.find((country) => country.iso === iso.toUpperCase())
}
