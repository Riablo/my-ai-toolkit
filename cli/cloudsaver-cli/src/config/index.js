import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const CONFIG_DIR = path.join(os.homedir(), '.config', 'cloudsaver-cli');
const CONFIG_FILE = path.join(CONFIG_DIR, 'config.json');

const LEGACY_CONFIG_DIR = path.join(os.homedir(), '.config', 'cloudsaver');
const LEGACY_CONFIG_FILE = path.join(LEGACY_CONFIG_DIR, 'config.json');
const LEGACY_LOCAL_FILE = path.join(LEGACY_CONFIG_DIR, 'local.json');

const DEFAULT_CONFIG = {
  search: {
    channels: [],
    proxy: {
      enabled: false,
      host: '127.0.0.1',
      port: 7890,
    },
  },
  cloud115: {
    cookie: '',
    defaultFolder: '0',
    defaultFolderName: '根目录',
  },
};

function cloneDefaultConfig() {
  return JSON.parse(JSON.stringify(DEFAULT_CONFIG));
}

function ensureObject(value, sourceLabel) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`配置文件格式不正确: ${sourceLabel}`);
  }
  return value;
}

function readJsonFile(filePath) {
  const raw = fs.readFileSync(filePath, 'utf8');

  try {
    return ensureObject(JSON.parse(raw), filePath);
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(`配置文件不是合法 JSON: ${filePath}`);
    }
    throw error;
  }
}

function mergeConfig(base, patch) {
  const next = cloneDefaultConfig();

  next.search.channels = patch?.search?.channels ?? base.search.channels;
  next.search.proxy = {
    ...base.search.proxy,
    ...(patch?.search?.proxy ?? {}),
  };
  next.cloud115 = {
    ...base.cloud115,
    ...(patch?.cloud115 ?? {}),
  };

  return {
    search: {
      channels: next.search.channels,
      proxy: next.search.proxy,
    },
    cloud115: next.cloud115,
  };
}

function parseBoolean(value, fieldPath) {
  if (typeof value === 'boolean') {
    return value;
  }
  if (value === 'true') {
    return true;
  }
  if (value === 'false') {
    return false;
  }
  throw new Error(`配置项 ${fieldPath} 必须是布尔值`);
}

function parsePort(value, fieldPath) {
  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`配置项 ${fieldPath} 必须是 1-65535 之间的整数`);
  }
  return port;
}

function normalizeChannels(rawChannels) {
  if (rawChannels == null) {
    return [];
  }
  if (!Array.isArray(rawChannels)) {
    throw new Error('配置项 search.channels 必须是数组');
  }

  return rawChannels.map((channel, index) => {
    if (!channel || typeof channel !== 'object' || Array.isArray(channel)) {
      throw new Error(`配置项 search.channels[${index}] 格式不正确`);
    }

    const id = String(channel.id ?? '').trim();
    const name = String(channel.name ?? id).trim();
    if (!id) {
      throw new Error(`配置项 search.channels[${index}].id 不能为空`);
    }

    return {
      id,
      name: name || id,
    };
  });
}

function normalizeProxy(rawProxy) {
  if (rawProxy == null) {
    return { ...DEFAULT_CONFIG.search.proxy };
  }
  if (!rawProxy || typeof rawProxy !== 'object' || Array.isArray(rawProxy)) {
    throw new Error('配置项 search.proxy 格式不正确');
  }

  const enabled = rawProxy.enabled == null
    ? DEFAULT_CONFIG.search.proxy.enabled
    : parseBoolean(rawProxy.enabled, 'search.proxy.enabled');

  const host = String(rawProxy.host ?? DEFAULT_CONFIG.search.proxy.host).trim();
  if (!host) {
    throw new Error('配置项 search.proxy.host 不能为空');
  }

  const port = rawProxy.port == null
    ? DEFAULT_CONFIG.search.proxy.port
    : parsePort(rawProxy.port, 'search.proxy.port');

  return { enabled, host, port };
}

function normalizeCloud115(rawCloud115) {
  if (rawCloud115 == null) {
    return { ...DEFAULT_CONFIG.cloud115 };
  }
  if (!rawCloud115 || typeof rawCloud115 !== 'object' || Array.isArray(rawCloud115)) {
    throw new Error('配置项 cloud115 格式不正确');
  }

  const cookie = String(rawCloud115.cookie ?? '').trim();
  const defaultFolder = String(rawCloud115.defaultFolder ?? '0').trim() || '0';
  const defaultFolderName = String(rawCloud115.defaultFolderName ?? '根目录').trim() || '根目录';

  return {
    cookie,
    defaultFolder,
    defaultFolderName,
  };
}

function normalizeConfig(rawConfig, sourceLabel) {
  const raw = ensureObject(rawConfig, sourceLabel);

  return {
    search: {
      channels: normalizeChannels(raw.search?.channels),
      proxy: normalizeProxy(raw.search?.proxy),
    },
    cloud115: normalizeCloud115(raw.cloud115),
  };
}

function ensureConfigDir() {
  fs.mkdirSync(CONFIG_DIR, { recursive: true });
}

function maybeReadLegacyConfig() {
  if (!fs.existsSync(LEGACY_CONFIG_FILE) && !fs.existsSync(LEGACY_LOCAL_FILE)) {
    return null;
  }

  let raw = cloneDefaultConfig();

  if (fs.existsSync(LEGACY_CONFIG_FILE)) {
    raw = mergeConfig(raw, readJsonFile(LEGACY_CONFIG_FILE));
  }

  if (fs.existsSync(LEGACY_LOCAL_FILE)) {
    let legacyLocal = readJsonFile(LEGACY_LOCAL_FILE);

    if (typeof legacyLocal.cookie === 'string' && legacyLocal.cloud115 == null) {
      legacyLocal = {
        cloud115: {
          cookie: legacyLocal.cookie,
        },
      };
    }

    raw = mergeConfig(raw, legacyLocal);
  }

  return raw;
}

export class ConfigManager {
  static load() {
    if (fs.existsSync(CONFIG_FILE)) {
      return normalizeConfig(readJsonFile(CONFIG_FILE), CONFIG_FILE);
    }

    const legacy = maybeReadLegacyConfig();
    if (legacy) {
      return normalizeConfig(legacy, `${LEGACY_CONFIG_DIR}/*`);
    }

    return cloneDefaultConfig();
  }

  static save(partialConfig) {
    const current = this.load();
    const merged = mergeConfig(current, partialConfig ?? {});
    const normalized = normalizeConfig(merged, '内存配置');

    ensureConfigDir();
    fs.writeFileSync(CONFIG_FILE, `${JSON.stringify(normalized, null, 2)}\n`, 'utf8');
    fs.chmodSync(CONFIG_FILE, 0o600);
  }

  static getConfigDir() {
    return CONFIG_DIR;
  }

  static getConfigPath() {
    return CONFIG_FILE;
  }
}
