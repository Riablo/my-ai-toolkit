import axios from 'axios';
import { ConfigManager } from '../config/index.js';
import { attachProxyAgent } from '../utils/proxy.js';

function normalizeShareUrl(rawUrl) {
  return rawUrl
    .trim()
    .replace(/^['"]+|['"]+$/g, '')
    .replace(/&amp;/gi, '&')
    .replace(/&#38;/gi, '&');
}

export class Cloud115Service {
  constructor() {
    const axiosConfig = {
      baseURL: 'https://webapi.115.com',
      timeout: 30000,
      proxy: false,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/6.8.0(0x16080000) NetType/WIFI MiniProgramEnv/Mac MacWechat/WMPF MacWechat/3.8.9(0x13080910) XWEB/1227',
        Accept: '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        Origin: '',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        Referer: 'https://servicewechat.com/wx2c744c010a61b0fa/94/page-frame.html',
      },
    };
    attachProxyAgent(axiosConfig, axiosConfig.baseURL);
    this.api = axios.create(axiosConfig);
    this.cookie = '';

    this.api.interceptors.request.use((config) => {
      if (this.cookie) {
        config.headers.cookie = this.cookie;
      }
      return config;
    });

    this.loadCookie();
  }

  loadCookie() {
    const config = ConfigManager.load();
    this.cookie = config.cloud115.cookie;
  }

  setCookie(cookie) {
    this.cookie = cookie.trim();
    const config = ConfigManager.load();
    ConfigManager.save({
      cloud115: {
        ...config.cloud115,
        cookie: this.cookie,
      },
    });
  }

  hasCookie() {
    return Boolean(this.cookie);
  }

  parseShareUrl(url) {
    const normalizedUrl = normalizeShareUrl(url);

    try {
      const parsedUrl = new URL(normalizedUrl);
      const hostname = parsedUrl.hostname.replace(/^www\./i, '').toLowerCase();
      const isSupportedHost = ['115.com', '115cdn.com', 'anxia.com'].includes(hostname);
      const pathMatch = parsedUrl.pathname.match(/^\/s\/([^/?#]+)/);

      if (!isSupportedHost || !pathMatch) {
        throw new Error('无效的115分享链接');
      }

      const receiveCode = parsedUrl.searchParams.get('password')?.trim() || undefined;
      return {
        shareCode: pathMatch[1],
        receiveCode,
      };
    } catch (error) {
      const match = normalizedUrl.match(
        /(?:www\.)?(?:115|115cdn|anxia)\.com\/s\/([^?#]+)(?:\?password=([A-Za-z0-9]+))?/i,
      );
      if (!match) {
        throw new Error('无效的115分享链接');
      }

      return {
        shareCode: match[1],
        receiveCode: match[2],
      };
    }
  }

  async getShareInfo(shareCode, receiveCode = '') {
    const response = await this.api.get('/share/snap', {
      params: {
        share_code: shareCode,
        receive_code: receiveCode,
        offset: 0,
        limit: 50,
        cid: '',
      },
    });

    if (response.data?.state && response.data.data?.list) {
      return response.data.data.list.map((item) => ({
        fileId: item.cid,
        fileName: item.n,
        fileSize: item.s,
      }));
    }

    throw new Error(response.data?.error || '获取分享信息失败');
  }

  async getFolderList(parentCid = '0') {
    const response = await this.api.get('/files', {
      params: {
        aid: 1,
        cid: parentCid,
        o: 'user_ptime',
        asc: 1,
        offset: 0,
        show_dir: 1,
        limit: 50,
        type: 0,
        format: 'json',
      },
    });

    if (response.data?.state) {
      return response.data.data
        .filter((item) => item.cid && item.ns)
        .map((folder) => ({
          cid: folder.cid,
          name: folder.n,
        }));
    }

    throw new Error(response.data?.error || '获取文件夹列表失败');
  }

  async saveFile(shareCode, fileId, receiveCode = '', folderId = '0') {
    const params = new URLSearchParams({
      cid: folderId,
      share_code: shareCode,
      receive_code: receiveCode,
      file_id: fileId,
    });

    const response = await this.api.post('/share/receive', params.toString());

    if (response.data?.state) {
      return {
        success: true,
        message: '转存成功',
      };
    }

    return {
      success: false,
      message: response.data?.error || '转存失败',
    };
  }

  async createFolder(name, parentCid = '0') {
    const params = new URLSearchParams({
      pid: parentCid,
      file_name: name,
    });

    const response = await this.api.post('/files/add', params.toString());

    if (response.data?.state) {
      return response.data.cid;
    }

    throw new Error(response.data?.error || '创建文件夹失败');
  }

  async ensureTransferFolder() {
    try {
      const folders = await this.getFolderList('0');
      const transferFolder = folders.find((folder) => folder.name === '转存');

      if (transferFolder) {
        return transferFolder.cid;
      }

      return await this.createFolder('转存', '0');
    } catch (error) {
      console.error('确保转存文件夹存在失败:', error);
      return '0';
    }
  }
}
