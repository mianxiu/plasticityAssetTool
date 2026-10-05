import {createSignal} from 'solid-js';
import english from './locales/en.json';
import chinese from './locales/zh-CN.json';

export const LANGUAGE_KEY = 'pat.language';
export const dictionaries = {'zh-CN': chinese, en: english};
function initialLocale() {
  try { return localStorage.getItem(LANGUAGE_KEY) === 'en' ? 'en' : 'zh-CN'; }
  catch { return 'zh-CN'; }
}
export const [locale, updateLocale] = createSignal(initialLocale());
export function setLocale(value) {
  if (!Object.hasOwn(dictionaries, value)) return;
  updateLocale(value);
  try {localStorage.setItem(LANGUAGE_KEY, value);} catch { /* Keep the session preference. */ }
}
window.addEventListener('storage', event => {
  if (event.key === LANGUAGE_KEY) updateLocale(event.newValue === 'en' ? 'en' : 'zh-CN');
});
export function t(key, values = {}) {
  const message = dictionaries[locale()][key] ?? key;
  return message.replace(/\{(\w+)\}/g, (token, name) => Object.hasOwn(values, name) ? String(values[name]) : token);
}
