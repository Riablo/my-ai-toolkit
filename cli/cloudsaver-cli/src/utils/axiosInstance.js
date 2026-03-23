import axios from 'axios';
import { ConfigManager } from '../config/index.js';
import { attachProxyAgent } from './proxy.js';

export function createAxiosInstance(baseURL, headers = {}, useProxy = false, proxyConfig) {
  const config = {
    baseURL,
    timeout: 30000,
    proxy: false,
    headers: {
      'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
      ...headers,
    },
  };

  if (useProxy && proxyConfig) {
    const proxyUrl = `http://${proxyConfig.host}:${proxyConfig.port}`;
    attachProxyAgent(config, baseURL, proxyUrl);
  } else {
    attachProxyAgent(config, baseURL);
  }

  return axios.create(config);
}

export function createTelegramAxios(proxyEnabled) {
  const config = ConfigManager.load();
  const proxy = config.search.proxy;

  return createAxiosInstance(
    'https://t.me/s',
    {
      Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      'Cache-Control': 'max-age=0',
    },
    proxyEnabled ?? proxy?.enabled,
    proxy?.enabled ? proxy : undefined,
  );
}
