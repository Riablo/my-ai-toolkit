import { HttpsProxyAgent } from 'https-proxy-agent';

const DEFAULT_PORTS = {
  http: 80,
  https: 443,
};

function getEnv(name) {
  return process.env[name] || process.env[name.toUpperCase()] || '';
}

function normalizePort(url) {
  if (url.port) {
    const port = Number.parseInt(url.port, 10);
    if (Number.isInteger(port)) {
      return port;
    }
  }

  return DEFAULT_PORTS[url.protocol.replace(/:$/, '')] || 0;
}

function hostnameMatches(hostname, pattern) {
  if (!pattern) {
    return false;
  }

  if (pattern === '*') {
    return true;
  }

  let token = pattern;
  if (token.startsWith('*')) {
    token = token.slice(1);
  }

  if (token.startsWith('.')) {
    return hostname.endsWith(token) || hostname === token.slice(1);
  }

  return hostname === token;
}

function shouldBypassProxy(targetUrl) {
  const noProxy = getEnv('no_proxy') || getEnv('npm_config_no_proxy');
  if (!noProxy) {
    return false;
  }

  const raw = noProxy.trim().toLowerCase();
  if (!raw) {
    return false;
  }
  if (raw === '*') {
    return true;
  }

  const hostname = targetUrl.hostname.toLowerCase();
  const port = normalizePort(targetUrl);

  return raw
    .split(/[,\s]+/)
    .filter(Boolean)
    .some((entry) => {
      const token = entry.toLowerCase();
      const parts = token.split(':');
      const hostPattern = parts[0];
      const portPattern = parts.length > 1 ? Number.parseInt(parts[1], 10) : null;

      if (portPattern != null && portPattern !== port) {
        return false;
      }

      return hostnameMatches(hostname, hostPattern);
    });
}

export function getProxyUrlForBaseURL(baseURL) {
  const targetUrl = new URL(baseURL);
  if (shouldBypassProxy(targetUrl)) {
    return null;
  }

  const protocol = targetUrl.protocol === 'https:' ? 'https' : 'http';
  const rawProxy = getEnv(`npm_config_${protocol}_proxy`)
    || getEnv(`${protocol}_proxy`)
    || getEnv('npm_config_proxy')
    || getEnv('all_proxy');

  if (!rawProxy) {
    return null;
  }

  return rawProxy.includes('://') ? rawProxy : `${protocol}://${rawProxy}`;
}

export function attachProxyAgent(config, baseURL, explicitProxyUrl = null) {
  const proxyUrl = explicitProxyUrl || getProxyUrlForBaseURL(baseURL);
  if (!proxyUrl) {
    return config;
  }

  const agent = new HttpsProxyAgent(proxyUrl);
  config.httpsAgent = agent;
  config.httpAgent = agent;
  return config;
}
